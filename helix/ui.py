"""The dashboard: credentials, run controls, and a live view of a run.

  python -m helix.ui                then open http://127.0.0.1:8765 (it opens by itself)
  python -m helix.ui --port 9000

It only listens on your own machine (127.0.0.1). Credentials are saved to helix/.env,
which is gitignored; the page never receives a saved key back, only its last 4 characters.
Runs are started as separate processes, so closing the dashboard doesn't stop a run,
and reopening it picks the run back up from its folder.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import llm as llm_mod
from . import mongo
from .peek import RUNS_DIR, load_state, pid_alive, read_json, read_jsonl, snapshot, tail_text
from .sandbox import REPO_ROOT, evaluate_file

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
PAGE = HERE / "dashboard.html"
NAME_OK = re.compile(r"^[\w.-]+$")
FILES_OK = {"report.md", "progress.png", "compare.png", "best_program.py", "console.log"}

# key, secret?, default
FIELDS = [
    ("HELIX_PROVIDER", False, "luminal"),
    ("LUMINAL_BASE_URL", False, ""),
    ("LUMINAL_API_KEY", True, ""),
    ("HELIX_FLASH_MODEL", False, "deepseek-v4.1-flash"),
    ("HELIX_PRO_MODEL", False, ""),
    ("LUMINAL_EXTRA_BODY", False, ""),
    ("LOCAL_BASE_URL", False, "http://localhost:11434/v1"),
    ("LOCAL_MODEL", False, ""),
    ("MONGODB_URI", True, ""),
    ("MONGODB_DB", False, "helix"),
]
SECRET = {k for k, s, _ in FIELDS if s}

PROCS = {}               # run name -> Popen, for runs started by this dashboard
BASELINES = {}           # program name -> train score, filled in the background at startup
LOCK = threading.Lock()


# ================================================================ settings (helix/.env)
def read_env_file():
    values, order = {}, []
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
                order.append(k.strip())
    return values, order


def current_settings():
    out = {}
    for key, secret, default in FIELDS:
        value = os.environ.get(key, "")
        if secret:
            out[key] = {"secret": True, "set": bool(value), "hint": ("…" + value[-4:]) if len(value) > 6 else ""}
        else:
            out[key] = {"secret": False, "value": value or default}
    return out


def save_settings(new):
    values, order = read_env_file()
    for key, secret, _ in FIELDS:
        if key not in new:
            continue
        v = str(new[key]).strip()
        if secret and v == "":
            continue                       # blank secret = keep the saved one
        if secret and v == "__clear__":
            v = ""
        if key == "LUMINAL_EXTRA_BODY" and v:
            try:                           # reject broken JSON before it breaks a run
                json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Extra request JSON isn't valid JSON ({exc.msg}); nothing was saved") from None
        values[key] = v
        if key not in order:
            order.append(key)
    lines = ["# Written by the Helix dashboard. Gitignored: never commit this file."]
    lines += [f"{k}={values[k]}" for k in order if values.get(k, "") != ""]
    ENV_FILE.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass
    for k in order:                        # child processes inherit the new values
        if values.get(k):
            os.environ[k] = values[k]
        else:
            os.environ.pop(k, None)


# ================================================================ runs
def run_dir(name):
    if not name or not NAME_OK.match(name):
        raise ValueError("bad run name")
    d = RUNS_DIR / name
    if not d.is_dir():
        raise FileNotFoundError(f"no run called {name}")
    return d


def list_runs():
    runs = []
    folders = [p for p in RUNS_DIR.glob("*") if p.is_dir()] if RUNS_DIR.exists() else []
    for d in sorted(folders, key=lambda p: p.stat().st_mtime, reverse=True):
        st = read_json(d / "status.json", {}) or {}
        cfg = read_json(d / "config.json", {}) or {}
        state = st.get("state", "unknown")
        if state == "running" and not process_alive(d.name, st.get("pid")):
            state = "died"
        runs.append({"name": d.name, "state": state, "mode": cfg.get("mode"), "provider": cfg.get("provider"),
                     "model": cfg.get("flash_model"), "generation": st.get("generation"),
                     "generations": st.get("generations"), "best_score": st.get("best_score")})
    return runs


def process_alive(name, pid):
    proc = PROCS.get(name)
    if proc is not None:
        return proc.poll() is None
    return pid_alive(pid)


def active_run():
    with LOCK:
        for name, proc in PROCS.items():
            if proc.poll() is None:
                return name
    return None


def spawn(args, name):
    d = RUNS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    log = open(d / "console.log", "a")
    log.write(f"\n$ python -m helix.run {' '.join(args)}\n")
    log.flush()
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "helix.run", *args], cwd=REPO_ROOT, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    with LOCK:
        PROCS[name] = proc
    return proc


def start_run(body):
    # Several runs may go at once (e.g. the full loop next to a wide-only control); each has its own folder.
    fake = bool(body.get("fake"))
    if not fake:
        missing = llm_mod.Settings.from_env().problems()
        if missing:
            raise RuntimeError(f"missing {', '.join(missing)}: fill them in under Connect and press Save")
    mode = body.get("mode", "full")
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{mode}" + ("-offline" if fake else "")
    if (RUNS_DIR / name).exists():
        raise RuntimeError(f"{name} was started a moment ago; wait a second and press Run again")
    args = ["--run-dir", str(RUNS_DIR / name), "--mode", mode]
    for key in ("schedule", "generations", "max_minutes", "top_x", "variants", "hypotheses", "n",
                "pro_every", "epsilon", "workers"):
        if body.get(key) not in (None, ""):
            args += [f"--{key.replace('_', '-')}", str(body[key])]
    if fake:
        args.append("--fake-llm")
    if "publish" in body:
        args.append("--publish" if body["publish"] else "--no-publish")
    spawn(args, name)
    return name


def resume_run(name, body):
    d = run_dir(name)
    st = read_json(d / "status.json", {}) or {}
    if st.get("state") in ("starting", "running") and process_alive(name, st.get("pid")):
        raise RuntimeError(f"{name} is still going; stop it before resuming it")
    done = st.get("generation") or 0
    extra = int(body.get("more") or 5)
    args = ["--resume", str(d), "--generations", str(done + extra)]
    if body.get("workers"):
        args += ["--workers", str(body["workers"])]
    spawn(args, name)
    return {"name": name, "until_generation": done + extra}


def stop_run(name, force=False):
    d = run_dir(name)
    (d / "STOP").write_text("requested from the dashboard\n")
    if not force:
        return "Stop requested: the run will finish its current generation, save, and exit."
    st = read_json(d / "status.json", {}) or {}
    proc = PROCS.get(name)
    if proc is not None and proc.poll() is None:
        proc.kill()
    elif st.get("pid") and os.name == "posix" and pid_alive(st["pid"]):
        os.kill(st["pid"], signal.SIGTERM)
    st.update(state="stopped", error="killed from the dashboard", finished=time.time(), phase="")
    (d / "status.json").write_text(json.dumps(st, indent=2))
    return "Killed. Everything up to the last finished program is saved; Resume continues from the last full generation."


def call_list(d, n=40):
    """The last n LLM calls, light: enough for a list. Each carries its line number for the detail view."""
    path = d / "llm_calls.jsonl"
    if not path.exists():
        return []
    lines = path.read_bytes().splitlines()
    out = []
    for no in range(max(0, len(lines) - n), len(lines)):
        try:
            c = json.loads(lines[no])
        except json.JSONDecodeError:
            continue
        reply = c.get("reply") or ""
        out.append({"line": no, "time": c.get("time"), "role": c.get("role"), "tier": c.get("tier"),
                    "model": c.get("model"), "seconds": c.get("seconds"), "tokens_in": c.get("tokens_in"),
                    "tokens_out": c.get("tokens_out"), "error": c.get("error"),
                    "has_reasoning": bool(c.get("reasoning")),
                    "preview": " ".join(reply.split("```", 1)[0].split())[:180]})
    return out[::-1]


def call_detail(d, line):
    lines = (d / "llm_calls.jsonl").read_bytes().splitlines()
    return json.loads(lines[int(line)])


def latest_researcher(d):
    path = d / "llm_calls.jsonl"
    if not path.exists():
        return None
    for raw in reversed(path.read_bytes().splitlines()[-200:]):
        try:
            c = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if c.get("role") == "researcher" and c.get("reply"):
            return {k: c.get(k) for k in ("time", "model", "tier", "seconds", "reasoning", "reply")}
    return None


def run_state(name):
    d = run_dir(name)
    s = load_state(d)
    if s["status"].get("state") == "running" and not process_alive(name, s["status"].get("pid")):
        s["status"]["state"] = "died"
    best = s.pop("best")
    s["best"] = {k: best.get(k) for k in ("id", "score", "branch", "generation", "code", "families", "note")} if best else None
    s["calls"] = call_list(d)
    s["researcher"] = latest_researcher(d)
    s["console"] = tail_text(d / "console.log", 60)
    s["has_report"] = (d / "report.md").exists()
    s["stop_requested"] = (d / "STOP").exists()
    return s


def compute_baselines():
    for path in sorted((REPO_ROOT / "programs").glob("*.py")):
        try:
            r = evaluate_file(path, "train", 60)
            if r.get("valid"):
                BASELINES[path.stem] = r["score"]
        except Exception:
            pass


# ================================================================ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "helix-ui"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("json") else ""))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _route(self, method):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        q = parse_qs(url.query)
        try:
            if method == "GET" and not parts:
                return self._send(200, PAGE.read_bytes(), "text/html")
            if parts[:1] != ["api"]:
                return self._send(404, {"error": "not found"})
            p = parts[1:]
            if method == "GET" and p == ["settings"]:
                return self._send(200, current_settings())
            if method == "POST" and p == ["settings"]:
                save_settings(self._body())
                return self._send(200, {"ok": True, "settings": current_settings()})
            if method == "POST" and p == ["check", "llm"]:
                return self._send(200, {"results": llm_mod.check(llm_mod.Settings.from_env())})
            if method == "POST" and p == ["check", "mongo"]:
                return self._send(200, mongo.check())
            if method == "GET" and p == ["baselines"]:
                return self._send(200, BASELINES)
            if method == "GET" and p == ["runs"]:
                return self._send(200, {"runs": list_runs(), "active": active_run()})
            if method == "POST" and p == ["runs", "start"]:
                return self._send(200, {"name": start_run(self._body())})
            if len(p) >= 2 and p[0] == "runs":
                name, rest = p[1], p[2:]
                if method == "GET" and not rest:
                    return self._send(200, run_state(name))
                if method == "GET" and rest == ["snapshot"]:
                    return self._send(200, snapshot(run_dir(name)), "text/plain")
                if method == "GET" and rest == ["call"]:
                    return self._send(200, call_detail(run_dir(name), q["line"][0]))
                if method == "GET" and len(rest) == 2 and rest[0] == "program":
                    progs = read_jsonl(run_dir(name) / "programs.jsonl")
                    return self._send(200, next(x for x in progs if x["id"] == rest[1]))
                if method == "GET" and len(rest) == 2 and rest[0] == "file" and rest[1] in FILES_OK:
                    f = run_dir(name) / rest[1]
                    ctype = "image/png" if f.suffix == ".png" else "text/plain"
                    return self._send(200, f.read_bytes(), ctype) if f.exists() else self._send(404, {"error": "not yet"})
                if method == "POST" and rest == ["stop"]:
                    return self._send(200, {"message": stop_run(name, force=bool(self._body().get("force")))})
                if method == "POST" and rest == ["resume"]:
                    return self._send(200, resume_run(name, self._body()))
                if method == "POST" and rest == ["report"]:
                    from .report import Run, write_report
                    write_report([Run(run_dir(name))])
                    return self._send(200, {"ok": True})
                if method == "POST" and rest == ["publish"]:
                    from .publish import export, push
                    dest = export(run_dir(name), report=not (run_dir(name) / "report.md").exists())
                    msg = f"Copied to {dest.relative_to(REPO_ROOT)}."
                    if self._body().get("push"):
                        ok, log = push(dest)
                        return self._send(200, {"ok": ok, "message": msg + "\n" + log})
                    return self._send(200, {"ok": True, "message": msg + " Commit it, or use Publish & push."})
            return self._send(404, {"error": "not found"})
        except (ValueError, RuntimeError, FileNotFoundError, StopIteration, KeyError, json.JSONDecodeError) as exc:
            return self._send(400, {"error": str(exc) or type(exc).__name__})
        except Exception as exc:
            return self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


def main():
    ap = argparse.ArgumentParser(prog="python -m helix.ui", description="Helix dashboard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    llm_mod.load_env_file()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=compute_baselines, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"Helix dashboard: {url}   (Ctrl+C to close it; runs keep going)", flush=True)
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ndashboard closed")


if __name__ == "__main__":
    main()
