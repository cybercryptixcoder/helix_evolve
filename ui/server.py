"""The Helix dashboard: a small local server and a single-page app.

    python -m ui                 # http://localhost:8765
    python -m ui --port 9000

It reads run folders (runs/, results/v3/), meta runs (meta_runs/, results/meta/) and the problem suite, and can
start new runs. Nothing to build or install: standard library only.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
RUN_ROOTS = [ROOT / "runs", ROOT / "results" / "v3"]
META_ROOTS = [ROOT / "meta_runs", ROOT / "results" / "meta"]
sys.path.insert(0, str(ROOT))

_cache = {}
_lock = threading.Lock()


def _events(run_dir):
    """Trace events, cached by file size (the trace only grows)."""
    p = Path(run_dir) / "trace.jsonl"
    if not p.exists():
        return []
    size = p.stat().st_size
    with _lock:
        hit = _cache.get(str(p))
        if hit and hit[0] == size:
            return hit[1]
    ev = []
    with p.open() as f:
        for line in f:
            try:
                ev.append(json.loads(line))
            except ValueError:
                pass
    with _lock:
        _cache[str(p)] = (size, ev)
    return ev


def _rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def _safe(rel):
    p = (ROOT / unquote(rel)).resolve()
    if ROOT not in p.parents and p != ROOT:
        raise PermissionError(rel)
    return p


def list_runs():
    out = []
    for root in RUN_ROOTS:
        if not root.exists():
            continue
        for d in root.glob("*/*"):
            if not (d / "trace.jsonl").exists():
                continue
            try:
                st = json.loads((d / "status.json").read_text()) if (d / "status.json").exists() else {}
            except ValueError:
                st = {}
            hist = []
            try:
                hist = json.loads((d / "history.json").read_text())
            except (OSError, ValueError):
                pass
            ev = _events(d)
            start = next((e for e in ev if e["type"] == "run_start"), {})
            gens = [e for e in ev if e["type"] == "gen_end"]
            last = gens[-1] if gens else {}
            running = st.get("state") == "running" and time.time() - (d / "trace.jsonl").stat().st_mtime < 900
            out.append({"id": _rel(d), "problem": start.get("problem") or d.parent.name, "title": start.get("title", ""),
                        "label": start.get("label", ""), "started": start.get("t"),
                        "generations": max(0, len(gens) - 1), "target": (start.get("config") or {}).get("generations"),
                        "progress": last.get("progress"), "valid_progress": last.get("valid_progress"),
                        "curve": [g.get("progress") or 0 for g in gens], "calls": last.get("calls"),
                        "state": "running" if running else ("finished" if st.get("state") == "finished" else "stopped"),
                        "phase": st.get("phase") if running else None, "kept": len(last.get("library") or []),
                        "results": "results/" in _rel(d)})
            del hist
    out.sort(key=lambda r: -(r["started"] or 0))
    return out


def run_detail(rel):
    d = _safe(rel)
    ev = _events(d)
    slim = []
    for e in ev:
        if e["type"] == "call":
            slim.append({k: e.get(k) for k in ("type", "id", "gen", "role", "step", "feature", "seconds", "tokens_in",
                                                "tokens_out", "reasoning_tokens", "effort", "error", "t")})
        elif e["type"] == "run_start":
            slim.append({k: v for k, v in e.items() if k != "config"} | {"config": e.get("config")})
        else:
            slim.append(e)
    try:
        st = json.loads((d / "status.json").read_text())
    except (OSError, ValueError):
        st = {}
    try:
        champion = (d / "champion.py").read_text()
    except OSError:
        champion = ""
    return {"id": rel, "events": slim, "status": st, "champion": champion}


def call_detail(rel, cid):
    for e in _events(_safe(rel)):
        if e["type"] == "call" and e.get("id") == cid:
            return e
    return None


def list_meta():
    out = []
    for root in META_ROOTS:
        if not root.exists():
            continue
        for d in sorted(root.glob("*")):
            if (d / "state.json").exists():
                try:
                    s = json.loads((d / "state.json").read_text())
                except ValueError:
                    continue
                ev = _events(d)
                out.append({"id": _rel(d), "kind": "outer", "state": s, "swaps": [e for e in ev if e["type"] in ("swap", "unswap")],
                            "plans": [e for e in ev if e["type"] == "plan"]})
            elif (d / "result.json").exists():
                try:
                    out.append({"id": _rel(d), "kind": "evaluation", "result": json.loads((d / "result.json").read_text())})
                except ValueError:
                    pass
    return out


def suite():
    from helix3.problem import REGISTRY, load_problem
    out = []
    for name in REGISTRY:
        try:
            p = load_problem(name)
            out.append({"name": name, "title": p.title, "families": p.families, "held_out": p.held_out_families,
                        "signature": p.signature, "description": p.description, "metrics": p.metric_notes,
                        "instances": {s: len(p.instances(s)) for s in ("train", "valid", "test")}})
        except Exception as exc:  # noqa: BLE001
            out.append({"name": name, "error": str(exc)[:200]})
    return out


_suite_cache = {}


def launch(body):
    problem = str(body.get("problem", ""))
    gens = int(body.get("generations", 5))
    label = "".join(c for c in str(body.get("label", "")) if c.isalnum() or c in "-_")[:40]
    cmd = [sys.executable, "-m", "helix3.run", problem, "-g", str(max(1, min(gens, 60)))]
    if label:
        cmd += ["--label", label]
    logs = ROOT / "runs" / "_logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = open(logs / f"{time.strftime('%Y%m%d-%H%M%S')}-{problem}.log", "w")
    subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return {"started": True, "command": " ".join(cmd[1:])}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/runs":
                return self._send(200, list_runs())
            if u.path == "/api/run":
                return self._send(200, run_detail(q["id"][0]))
            if u.path == "/api/call":
                c = call_detail(q["id"][0], q["call"][0])
                return self._send(200 if c else 404, c or {"error": "no such call"})
            if u.path == "/api/meta":
                return self._send(200, list_meta())
            if u.path == "/api/suite":
                if "s" not in _suite_cache:
                    _suite_cache["s"] = suite()
                return self._send(200, _suite_cache["s"])
            path = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            f = (STATIC / path).resolve()
            if STATIC not in f.parents or not f.is_file():
                f = STATIC / "index.html"
            return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "text/plain")
        except (KeyError, PermissionError, FileNotFoundError) as exc:
            return self._send(404, {"error": str(exc)})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/api/launch":
            return self._send(200, launch(body))
        return self._send(404, {"error": "unknown"})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("HELIX_UI_PORT", 8765)))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://localhost:{a.port}"
    print(f"Helix dashboard on {url}")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
