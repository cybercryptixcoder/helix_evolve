"""The dashboard: credentials, run controls, and a live view of a run.

  python -m helix.ui                then open http://127.0.0.1:8765 (it opens by itself)
  python -m helix.ui --port 9000

It only listens on your own machine (127.0.0.1). Credentials are saved to helix/.env,
which is gitignored; the page never receives a saved key back, only its last 4 characters.
Runs are started as separate processes, so closing the dashboard doesn't stop a run,
and reopening it picks the run back up from its folder.
"""
import argparse
import gzip
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

from . import bounds as bounds_mod
from . import llm as llm_mod
from . import metrics, mongo
from .peek import RUNS_DIR, load_state, pid_alive, read_json, read_jsonl, snapshot, tail_text
from .sandbox import REPO_ROOT, evaluate_code, evaluate_file

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
PAGE = HERE / "dashboard.html"
NAME_OK = re.compile(r"^[\w.-]+$")
FILES_OK = {"report.md", "progress.png", "compare.png", "best_program.py", "console.log"}

# key, secret?, default
FIELDS = [
    ("HELIX_PROVIDER", False, "luminal"),
    ("LUMINAL_BASE_URL", False, "https://flash.luminal.cloud/v1"),
    ("LUMINAL_API_KEY", True, ""),
    ("HELIX_FLASH_MODEL", False, "deepseek-ai/DeepSeek-V4.1-Flash"),
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
REFERENCES = {}          # yardsticks in every unit (helix.metrics.references), filled in at startup
HEALTH = {"evaluator": {"ok": None, "detail": "checking..."}}
LOCK = threading.Lock()
RESULTS_DIR = REPO_ROOT / "results"


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
    """A run's folder: helix/runs/<name>, or a published copy in results/<name> (read-only)."""
    if not name or not NAME_OK.match(name):
        raise ValueError("bad run name")
    if (RUNS_DIR / name).is_dir():
        return RUNS_DIR / name
    if (RESULTS_DIR / name / "generations.jsonl").exists():
        return RESULTS_DIR / name
    raise FileNotFoundError(f"no run called {name}")


def list_runs():
    runs = []
    folders = [p for p in RUNS_DIR.glob("*") if p.is_dir()] if RUNS_DIR.exists() else []
    local = {p.name for p in folders}
    published = [p for p in RESULTS_DIR.glob("*") if p.is_dir() and p.name not in local
                 and (p / "generations.jsonl").exists()] if RESULTS_DIR.exists() else []
    for d in sorted(folders + published, key=lambda p: p.stat().st_mtime, reverse=True):
        st = read_json(d / "status.json", {}) or {}
        cfg = read_json(d / "config.json", {}) or {}
        state = st.get("state", "unknown")
        if state == "running" and not process_alive(d.name, st.get("pid")):
            state = "died"
        runs.append({"name": d.name, "state": state, "mode": cfg.get("mode"), "engine": engine_of(cfg),
                     "provider": cfg.get("provider"),
                     "model": cfg.get("flash_model"), "generation": st.get("generation"),
                     "generations": st.get("generations"), "best_score": st.get("best_score"),
                     "published": d.parent == RESULTS_DIR or (RESULTS_DIR / d.name / "generations.jsonl").exists()})
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
    engine = body.get("engine") or "features"
    if engine not in ("features", "programs"):
        raise ValueError("engine must be features or programs")
    args = ["--run-dir", str(RUNS_DIR / name), "--mode", mode]
    if mode != "zero-shot":
        args += ["--engine", engine]
    keys = ["schedule", "generations", "max_minutes", "top_x", "variants", "fresh", "hypotheses", "n", "pro_every", "workers"]
    keys += (["trial_evals", "refit_evals", "accept_margin", "fit_workers"] if engine == "features"
             else ["epsilon", "pool_size", "judge_tune_evals", "tune_evals"])
    for key in keys:
        if body.get(key) not in (None, ""):
            args += [f"--{key.replace('_', '-')}", str(body[key])]
    if engine == "features" and body.get("inspect") is False:
        args.append("--no-inspect")
    if body.get("tune") is not None and mode == "full" and engine == "programs":
        args.append("--tune" if body["tune"] else "--no-tune")
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


def _call_lines(d):
    path = d / "llm_calls.jsonl"
    if path.exists():
        return path.read_bytes().splitlines()
    gz = d / "llm_calls.jsonl.gz"
    if gz.exists():
        with gzip.open(gz, "rb") as f:
            return f.read().splitlines()
    return []


def call_detail(d, line):
    return json.loads(_call_lines(d)[int(line)])


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
    if best and best.get("families"):
        start = _start_families(_programs(d))
        s["best"]["units"] = {"score": best["score"], **metrics.units(best["families"], start)} if start else None
    s["engine"] = engine_of(s["config"])
    heavy = ("diagnostics", "library", "champion")      # per-generation detail comes from generation_detail
    s["generations"] = [{k: v for k, v in g.items() if k not in heavy} for g in s["generations"]]
    s["calls"] = call_list(d)
    s["researcher"] = latest_researcher(d)
    s["console"] = tail_text(d / "console.log", 60)
    s["has_report"] = (d / "report.md").exists()
    s["stop_requested"] = (d / "STOP").exists()
    s["heldout"] = heldout_units(d)
    s["published"] = d.parent == RESULTS_DIR or (RESULTS_DIR / d.name / "generations.jsonl").exists()
    return s


def engine_of(config):
    """features (v2: agents write features, an optimiser fits the weights) or programs (v1). Zero-shot
    controls and runs from before the feature engine are programs."""
    if config.get("mode") == "zero-shot":
        return "programs"
    return config.get("engine") or "programs"


def heldout_units(d):
    """The held-out check (report) in all three units, on the test split, if it has been run."""
    rows = read_json(d / "heldout.json", None)
    if not rows:
        return None
    best = next((r for r in rows if str(r.get("label", "")).startswith("Evolved best")), None)
    zero = next((r for r in rows if r.get("label") == "Code Zero"), None)
    if not best or not zero or not best.get("valid"):
        return None
    return {"label": best["label"], "score": best["test_score"], "code_zero": zero["test_score"],
            **metrics.units(best["test_families"], zero["test_families"], "test")}


# ================================================================ progress in readable units
_CACHE = {}


def _cached(key, path, build):
    """Rebuild only when the file behind it changes (the run keeps appending to its logs)."""
    try:
        stamp = (path.stat().st_mtime, path.stat().st_size)
    except OSError:
        stamp = None
    hit = _CACHE.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    value = build()
    _CACHE[key] = (stamp, value)
    return value


def _programs(d):
    return _cached(("programs", str(d)), d / "programs.jsonl", lambda: {p["id"]: p for p in read_jsonl(d / "programs.jsonl")})


def _features(d):
    """{feature id: its latest record}; a feature is written again whenever its status changes."""
    def build():
        out = {}
        for f in read_jsonl(d / "features.jsonl"):
            out[f["id"]] = f
        return out
    return _cached(("features", str(d)), d / "features.jsonl", build)


def _feature_view(f, code=False):
    keep = ("id", "name", "branch", "generation", "status", "description", "note", "error", "hypothesis_id",
            "parent_ids", "columns", "weights", "importance", "delta_train", "delta_valid")
    return {**{k: f.get(k) for k in keep}, **({"code": f.get("code")} if code else {})}


def _start_families(progs):
    seed = next((p for p in progs.values() if p.get("branch") == "seed" and p.get("families")), None)
    return seed["families"] if seed else metrics.code_zero_families("train")


def _units(p, start):
    if not p or not p.get("valid") or not p.get("families"):
        return {"score": p.get("score") if p else None, "waste": None, "progress": None}
    return {"score": p["score"], **metrics.units(p["families"], start)}


def run_series(name):
    """Per generation: the best program in all three units, each branch's best new program, and minutes."""
    d = run_dir(name)
    progs = _programs(d)
    start = _start_families(progs)
    st = read_json(d / "status.json", {}) or {}
    out, elapsed = [], 0.0
    for g in read_jsonl(d / "generations.jsonl"):
        if g.get("finished_at") and st.get("started"):
            elapsed = (g["finished_at"] - st["started"]) / 60
        else:
            elapsed += (g.get("seconds") or 0) / 60
        row = {"generation": g["generation"], "minutes": round(elapsed, 2), "best_id": g.get("best_id"),
               **_units(progs.get(g.get("best_id")), start)}
        for b in ("deep", "wide", "tune"):
            new = [p for p in progs.values() if p.get("generation") == g["generation"] and p.get("branch") == b
                   and p.get("valid") and not p.get("probe") and p.get("duplicate_of") is None]
            if new:
                top = max(new, key=lambda p: p["score"])
                row[b] = {"id": top["id"], **_units(top, start)}
        out.append(row)
    return {"name": name, "series": out, "start": _units({"valid": True, "families": start,
                                                          "score": -sum(start.values()) / len(start)}, start)
            if start else None}


def _call_index(d):
    """(line number, generation, role, time, light fields) for every call, built once per file change."""
    path = d / "llm_calls.jsonl" if (d / "llm_calls.jsonl").exists() else d / "llm_calls.jsonl.gz"

    def build():
        rows = []
        for no, raw in enumerate(_call_lines(d)):
            try:
                c = json.loads(raw)
            except json.JSONDecodeError:
                continue
            reply = c.get("reply") or ""
            head = reply.split("```", 1)[0].strip()
            if not head and reply.count("```") >= 2:          # a reply that starts with its code or JSON
                head = reply.rsplit("```", 1)[1].strip() or reply.split("```", 2)[1][:200]
            rows.append({"line": no, "generation": c.get("generation"), "role": c.get("role"), "time": c.get("time"),
                         "program": c.get("program"), "hypothesis": c.get("hypothesis"), "feature": c.get("feature"),
                         "branch": c.get("branch"), "seconds": c.get("seconds"),
                         "tokens_out": c.get("tokens_out"), "finish": c.get("finish"), "error": c.get("error"),
                         "has_reasoning": bool(c.get("reasoning")),
                         "preview": " ".join(head.split())[:160]})
        return rows
    return _cached(("calls", str(d)), path, build)


def generation_detail(name, gen):
    """Everything that happened in one generation, grouped by the flowchart's steps."""
    d = run_dir(name)
    gen = int(gen)
    progs = _programs(d)
    start = _start_families(progs)
    gens = read_jsonl(d / "generations.jsonl")
    record = next((g for g in gens if g["generation"] == gen), None)
    before = next((g for g in gens if g["generation"] == gen - 1), None)
    hyps = [h for h in read_jsonl(d / "hypotheses.jsonl") if h.get("generation") == gen]

    def prog_view(p):
        parent = progs.get(p.get("parent_id") or "")
        return {**{k: p.get(k) for k in ("id", "branch", "parent_id", "hypothesis_id", "note", "valid", "score",
                                        "families", "error", "repaired", "duplicate_of", "probe", "code",
                                        "trial", "valid_score", "features")},
                **{"units": _units(p, start)},
                "parent_score": parent.get("score") if parent else None,
                "parent_code": parent.get("code") if parent and p.get("branch") in ("deep", "tune") else None}

    made = [prog_view(p) for p in progs.values() if p.get("generation") == gen]
    calls = [c for c in _call_index(d) if c["generation"] == gen]
    if not calls and record and record.get("finished_at") is None:
        calls = _calls_by_count(d, gens, gen)         # runs from before calls were tagged with their generation
    pool_in = [progs[i] for i in (before or {}).get("pool", []) if i in progs] if before else []
    pool_out = [progs[i] for i in (record or {}).get("pool", []) if i in progs]
    view = lambda ps: [{"id": p["id"], "branch": p.get("branch"), "generation": p.get("generation"),
                        **_units(p, start)} for p in ps]
    cfg = read_json(d / "config.json", {}) or {}
    out = {"generation": gen, "engine": engine_of(cfg), "inspect": cfg.get("inspect", True), "record": record,
           "programs": made, "hypotheses": hyps, "calls": calls, "pool_in": view(pool_in), "pool_out": view(pool_out)}
    if out["engine"] == "features":
        feats = _features(d)

        def lib_view(rec):
            rows = []
            for row in (rec or {}).get("library") or []:
                f = feats.get(row["id"], {})
                rows.append({**row, "generation": f.get("generation"), "description": f.get("description"),
                             "status": f.get("status")})
            return rows
        out["features"] = [_feature_view(f, code=True) for f in feats.values() if f.get("generation") == gen
                           and f.get("branch") != "seed"]
        out["library_in"] = lib_view(before)
        out["library_out"] = lib_view(record)
        out["diagnostics"] = (record or {}).get("diagnostics") or {}
        champ = (record or {}).get("champion") or {}
        out["champion"] = {k: champ.get(k) for k in ("id", "features", "train", "valid", "fams", "vfams", "official")} if champ else None
        prev = (before or {}).get("champion") or {}
        out["champion_in"] = {k: prev.get(k) for k in ("id", "train", "valid", "official")} if prev else None
        if record:
            out["record"] = {k: v for k, v in record.items() if k not in ("diagnostics", "library", "champion")}
    return out


def _calls_by_count(d, gens, gen):
    """Older runs didn't tag calls with a generation. Each generation record holds the running count of
    answered calls when it ended, and a generation's calls all finish before it ends, so slice by that."""
    counts = {g["generation"]: (g.get("llm") or {}).get("calls") for g in gens}
    hi, lo = counts.get(gen), counts.get(gen - 1, 0) if gen > 0 else 0
    if hi is None or lo is None:
        return []
    answered = [c for c in _call_index(d) if not c.get("error")]
    return answered[lo:hi]


def health(name=None):
    """Is each part connected and working? Luminal / the model, MongoDB, the evaluator, the bounds."""
    s = llm_mod.Settings.from_env()
    out = {"evaluator": HEALTH["evaluator"],
           "bounds": {"ok": bool(bounds_mod.family_floor("train")),
                      "detail": "optimal-packing bounds loaded" if bounds_mod.family_floor("train")
                      else "not computed: python -m helix.bounds --compute"}}
    problems = s.problems()
    out["model"] = {"ok": None if not problems else False,
                    "detail": f"{s.provider}: {s.flash_model}" if not problems else f"missing {', '.join(problems)}"}
    mongo_uri = os.environ.get("MONGODB_URI")
    out["mongo"] = {"ok": None, "detail": "not configured (optional)" if not mongo_uri else "configured"}
    if name:
        try:
            d = run_dir(name)
            st = read_json(d / "status.json", {}) or {}
            llm = st.get("llm") or {}
            recent = _call_index(d)[-12:]
            errors = [c for c in recent if c.get("error")]
            if recent:
                last = recent[-1]
                ok = not errors or errors[-1]["line"] < recent[-1]["line"] and not recent[-1].get("error")
                out["model"] = {"ok": ok, "detail": f"last answer {last.get('time')}, {len(errors)} errors in the last "
                                f"{len(recent)} calls" + (f"; {llm['note']}" if llm.get("note") else "")}
            m = st.get("mongo")
            if m and m.get("error"):
                out["mongo"] = {"ok": False, "detail": m["error"]}
            elif m and m.get("enabled"):
                out["mongo"] = {"ok": True, "detail": f"{m.get('written', 0)} records mirrored"
                                + (f", {m['dropped']} dropped" if m.get("dropped") else "")}
            elif m:
                out["mongo"] = {"ok": None, "detail": "off for this run (no MONGODB_URI; optional)"}
        except (FileNotFoundError, ValueError):
            pass
    return out


def check_evaluator():
    code = (REPO_ROOT / "programs" / "code_zero.py").read_text()
    t = time.time()
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluate_code(code, Path(tmp) / "check.py", "quick", 60)
        HEALTH["evaluator"] = {"ok": bool(r.get("valid")), "detail": f"scored Code Zero in {time.time() - t:.1f}s"
                               if r.get("valid") else (r.get("error") or "invalid")[-200:]}
    except Exception as exc:
        HEALTH["evaluator"] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}


def compute_references():
    try:
        version = bounds_mod.version()
        REFERENCES.update(metrics.references("train"))
        REFERENCES["_version"] = version
    except Exception as exc:
        REFERENCES["error"] = {"label": f"{type(exc).__name__}: {exc}"}


def compute_baselines():
    try:   # the yardstick for "gap closed": an offline packer that sees every job in advance
        from .reference import offline_reference
        BASELINES["offline_reference"] = offline_reference("train")["score"]
    except Exception:
        pass
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
            if method == "GET" and p == ["references"]:
                if REFERENCES.get("_version") != bounds_mod.version() and "code_zero" in REFERENCES:
                    threading.Thread(target=compute_references, daemon=True).start()   # bounds changed: refresh
                return self._send(200, {k: v for k, v in REFERENCES.items() if not k.startswith("_")})
            if method == "GET" and p == ["health"]:
                return self._send(200, health(q.get("run", [None])[0]))
            if method == "GET" and p == ["runs"]:
                return self._send(200, {"runs": list_runs(), "active": active_run()})
            if method == "POST" and p == ["runs", "start"]:
                return self._send(200, {"name": start_run(self._body())})
            if len(p) >= 2 and p[0] == "runs":
                name, rest = p[1], p[2:]
                if method == "GET" and not rest:
                    return self._send(200, run_state(name))
                if method == "GET" and rest == ["series"]:
                    return self._send(200, run_series(name))
                if method == "GET" and len(rest) == 2 and rest[0] == "gen":
                    return self._send(200, generation_detail(name, rest[1]))
                if method == "GET" and rest == ["snapshot"]:
                    return self._send(200, snapshot(run_dir(name)), "text/plain")
                if method == "GET" and rest == ["transcript"]:
                    d = run_dir(name)
                    t, calls = d / "transcript.md", d / "llm_calls.jsonl"
                    fresh = t.exists() and (not calls.exists() or t.stat().st_mtime >= calls.stat().st_mtime)
                    if not fresh:
                        from .transcript import write_transcript
                        try:
                            write_transcript(d)
                        except Exception as exc:
                            return self._send(500, {"error": f"transcript export failed: {exc}"})
                    if not t.exists():
                        return self._send(404, {"error": "no records to export yet"})
                    return self._send(200, t.read_text(encoding="utf-8", errors="replace"), "text/markdown")
                if method == "GET" and rest == ["call"]:
                    return self._send(200, call_detail(run_dir(name), q["line"][0]))
                if method == "GET" and len(rest) == 2 and rest[0] == "program":
                    progs = read_jsonl(run_dir(name) / "programs.jsonl")
                    return self._send(200, next(x for x in progs if x["id"] == rest[1]))
                if method == "GET" and len(rest) == 2 and rest[0] == "feature":
                    f = _features(run_dir(name)).get(rest[1])
                    if not f:
                        raise KeyError(f"no feature {rest[1]}")
                    return self._send(200, _feature_view(f, code=True))
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
    threading.Thread(target=check_evaluator, daemon=True).start()
    threading.Thread(target=compute_references, daemon=True).start()
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
