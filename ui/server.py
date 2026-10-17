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
            running = _run_state(d, st) == "running"
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


def _drop_aborted(ev):
    """A resumed run re-does the generation that was in flight: drop that attempt's events (its model calls stay,
    marked aborted, since they were real spend), so features and plans aren't shown twice."""
    out = []
    for e in ev:
        if e.get("type") == "resume":
            g = e.get("gen", 0)
            out = [x if not (x.get("type") == "call" and (x.get("gen") or 0) > g) else {**x, "aborted": True}
                   for x in out if x.get("type") == "call" or (x.get("gen") or 0) <= g or "gen" not in x]
        out.append(e)
    return out


def run_detail(rel):
    d = _safe(rel)
    ev = _drop_aborted(_events(d))
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
    st["state"] = _run_state(d, st)
    st["resumable"] = st["state"] == "stopped" and (d / "checkpoint.json").exists()
    return {"id": rel, "events": slim, "status": st, "champion": champion}


def call_detail(rel, cid):
    for e in _events(_safe(rel)):
        if e["type"] == "call" and e.get("id") == cid:
            return e
    return None


def _run_state(d, st):
    """running only if the run's process is alive (older runs without a pid: trace written in the last 15 min)."""
    if st.get("state") == "finished":
        return "finished"
    if st.get("state") == "running":
        if st.get("pid"):
            return "running" if _alive(st["pid"]) else "stopped"
        try:
            return "running" if time.time() - (d / "trace.jsonl").stat().st_mtime < 900 else "stopped"
        except OSError:
            return "stopped"
    return "stopped"


def list_meta():
    out = []
    for root in META_ROOTS:
        if not root.exists():
            continue
        for d in sorted(root.glob("*")):
            args = _jload(d / "args.json", {}) if (d / "args.json").exists() else {}
            if args.get("fake_inner") or args.get("fake") or d.name.startswith(("smoke", "_")) or d.name.endswith("test"):
                continue                                          # crash tests, not real runs
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


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _meta_dirs():
    ds = [d for r in META_ROOTS if r.exists() for d in r.glob("*") if (d / "status.json").exists() or (d / "state.json").exists()]
    return sorted(ds, key=lambda d: d.stat().st_mtime, reverse=True)


def _jload(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


_slim = {}
_KEEP = ("type", "t", "role", "gen", "candidate", "new", "old", "gain", "reason")
OUTER_EV = {"outer_start": "oNav", "plan": "oNav", "research": "oRes", "candidate": "oVal", "supervise": "oVal",
            "evaluated": "oEval", "swap": "oInc", "unswap": "oInc"}
OUTER_ROLE = {"outer-navigator": "oNav", "outer-researcher": "oRes", "outer-coder": "oCode", "outer-mutator": "oMut"}
INNER_ROLE = {"navigator": "iNav", "researcher": "iRes", "coder": "iCode", "mutator": "iMut", "prover": "iKeep"}
INNER_EV = {"run_start": "iNav", "gen_start": "iNav", "plan": "iNav", "research": "iRes", "accept": "iKeep",
            "redundant": "iKeep", "retire": "iKeep", "revive": "iKeep", "prove": "iKeep", "gen_end": "iBest",
            "run_end": "iBest", **{k: "iFit" for k in ("feature_done", "bench", "probe", "trial", "refit", "novelty",
                                                       "prediction", "sensitivity", "diagnostics", "combination", "spread", "tree")}}


def _tail(path, keep=400):
    """Parse only the lines added since the last call and keep slim records (no prompts or replies)."""
    path = Path(path)
    st = _slim.setdefault(str(path), {"off": 0, "ev": [], "calls": 0, "swaps": [], "end": None, "t0": None})
    try:
        size = path.stat().st_size
    except OSError:
        return st
    if size < st["off"]:
        st.update(off=0, ev=[], calls=0, swaps=[], end=None, t0=None)
    if size > st["off"]:
        with path.open("rb") as f:
            f.seek(st["off"])
            chunk = f.read()
        nl = chunk.rfind(b"\n")
        for line in (chunk[:nl + 1].splitlines() if nl >= 0 else []):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            r = {k: e[k] for k in _KEEP if k in e}
            st["t0"] = st["t0"] or r.get("t")
            if r.get("type") == "call":
                st["calls"] += 1
            if r.get("type") in ("swap", "unswap"):
                st["swaps"].append(r)
            if r.get("type") == "outer_end":
                st["end"] = r.get("reason") or "generations"
            st["ev"].append(r)
        st["ev"] = st["ev"][-keep:]
        st["off"] += max(0, nl + 1)
    return st


def _node(e, roles, evs):
    return roles.get(e.get("role")) if e.get("type") == "call" else evs.get(e.get("type"))


def meta_live(rel=None):
    """A compact, high-level picture of one meta run (the newest by default), for the live page."""
    runs = _meta_dirs()
    if not runs:
        return {"runs": [], "run": None}
    d = next((x for x in runs if x.name == rel), runs[0])
    st, state, args = _jload(d / "status.json", {}), _jload(d / "state.json", {}), _jload(d / "args.json", {})
    ev = _tail(d / "trace.jsonl")
    running = st.get("state") == "running" and _alive(st.get("pid"))
    cands = [{"id": c["id"], "gen": c.get("gen", 0), "name": c.get("name", ""), "origin": c.get("origin"),
              "parent": c.get("parent"), "verdict": c.get("verdict"), "delta": c.get("delta"),
              "score": (c.get("result") or {}).get("score"), "held": (c.get("result") or {}).get("held_out_score"),
              "worst": (c.get("result") or {}).get("worst"), "noise": (c.get("result") or {}).get("noise"),
              "problems": {p: v.get("score") for p, v in ((c.get("result") or {}).get("problems") or {}).items()},
              "crashes": len((c.get("result") or {}).get("crashes") or [])} for c in state.get("candidates", [])]
    evals = []                              # the inner level: every inner run seen so far, newest evaluation last
    eds = sorted((d / "evals").glob("*"), key=lambda x: x.stat().st_mtime) if (d / "evals").exists() else []
    for ed in eds:
        runs_ = []
        for rd in (sorted(ed.glob("*-r*")) if ed == eds[-1] else []):     # only the newest evaluation is read in detail
            sm = _jload(rd / "summary.json")
            it = _tail(rd / "trace.jsonl", 60)
            last = next((e for e in reversed(it["ev"]) if _node(e, INNER_ROLE, INNER_EV)), None)
            gen = next((e["gen"] for e in reversed(it["ev"]) if "gen" in e), None)
            runs_.append({"run": rd.name, "done": sm is not None, "crash": (rd / "stdout.log").exists() and sm is None,
                          "node": _node(last, INNER_ROLE, INNER_EV) if last else None, "gen": gen, "calls": it["calls"],
                          "ev": [{"n": _node(e, INNER_ROLE, INNER_EV), "t": e["t"]} for e in it["ev"][-20:] if _node(e, INNER_ROLE, INNER_EV)]})
        evals.append({"candidate": ed.name, "finished": (ed / "result.json").exists(), "runs": runs_})
    now = time.time()
    cur = evals[-1] if evals else None
    live_ev = cur and not cur["finished"] and running
    o_events = [{"n": _node(e, OUTER_ROLE, OUTER_EV), "t": e["t"]} for e in ev["ev"] if _node(e, OUTER_ROLE, OUTER_EV)][-25:]
    i_events = sorted((x for r in (cur["runs"] if cur else []) if not r["done"] for x in r["ev"]), key=lambda x: x["t"])[-30:]
    counts = {}
    for r in (cur["runs"] if live_ev else []):
        if not r["done"] and r["node"]:
            counts[r["node"]] = counts.get(r["node"], 0) + 1
    o_node = "oEval" if live_ev else (o_events[-1]["n"] if running and o_events else None)
    calls = ev["calls"] + sum((c.get("result") or {}).get("calls") or 0 for c in state.get("candidates", [])) \
        + sum(r["calls"] for r in (cur["runs"] if live_ev else []))
    flow = {"outer": {"node": o_node, "events": o_events}, "inner": {"counts": counts, "events": i_events}}
    return {"flow": flow, "runs": [x.name for x in runs[:12]], "run": d.name, "running": running, "now": now,
            "status": st, "args": args, "incumbent": state.get("incumbent"), "gen": state.get("gen", st.get("gen", 0)),
            "candidates": cands, "evals": [dict(x, runs=[{k: v for k, v in r.items() if k != "ev"} for r in x["runs"]]) for x in evals[-1:]], "calls": calls,
            "swaps": [{"t": e["t"], "gen": e.get("gen"), "old": e.get("old"), "new": e.get("new"), "gain": e.get("gain"),
                       "kind": e["type"]} for e in ev["swaps"]],
            "ended": ev["end"], "t0": ev["t0"]}


def meta_launch(body):
    def num(k, lo, hi, d, cast=float):
        try:
            return str(cast(min(hi, max(lo, cast(body.get(k, d))))))
        except (TypeError, ValueError):
            return str(d)
    pr = lambda k, d: ",".join(x for x in str(body.get(k, d)).split(",") if x.strip().isalnum())
    env = dict(os.environ, HOURS=num("hours", 0.05, 48, 4), OUTER_GENS=num("outer_generations", 1, 500, 99, int),
               INNER_GENS=num("inner_generations", 1, 30, 5, int), REPEATS=num("repeats", 1, 6, 2, int),
               DEEP=num("deep", 0, 6, 2, int), WIDE=num("wide", 0, 6, 2, int), PARALLEL=num("parallel", 1, 32, 4, int),
               PROBLEMS=pr("problems", "binpack1d,knapsack,tsp,scheduling"), HELD_OUT=pr("held_out", "coloring"),
               PUSH="1" if body.get("push") else "0")
    log = ROOT / "meta_runs" / "_launch.log"
    log.parent.mkdir(exist_ok=True)
    subprocess.Popen(["bash", str(ROOT / "scripts" / "run_meta.sh")], cwd=ROOT, env=env, stdout=open(log, "w"),
                     stderr=subprocess.STDOUT, start_new_session=True)
    return {"started": True}


def meta_stop(rel):
    d = next((x for x in _meta_dirs() if x.name == rel), None)
    pid = _jload(d / "status.json", {}).get("pid") if d else None
    if pid and _alive(pid):
        os.kill(int(pid), 15)               # the launcher's exit hook still publishes what exists
        return {"stopped": True}
    return {"stopped": False}


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
            if u.path == "/api/meta/live":
                return self._send(200, meta_live(q.get("id", [None])[0]))
            if u.path == "/meta":
                return self._send(200, (STATIC / "meta.html").read_bytes(), "text/html")
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
        if u.path == "/api/meta/launch":
            return self._send(200, meta_launch(body))
        if u.path == "/api/meta/stop":
            return self._send(200, meta_stop(body.get("id", "")))
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
