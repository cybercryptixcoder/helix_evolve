"""Run one candidate program in its own process, with CPU, memory and wall-clock limits, and score its result.

The candidate defines `construct(budget_seconds, start)` and returns a NumPy array (the problem says what it holds).
It runs in a fresh Python process: one thread for numpy, low priority, a CPU-time limit, an address-space limit and a
wall-clock timeout. At most HELIX_EVAL_SLOTS programs run at once across every run on the machine (file locks in
HELIX_SLOTS_DIR), so several runs can share a small machine fairly.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

RUNNER = r'''
import json, os, resource, sys, time, traceback
budget, cpu_cap, mem_mb = float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
resource.setrlimit(resource.RLIMIT_CPU, (cpu_cap, cpu_cap + 2))
try:
    resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
except (ValueError, OSError):
    pass
try:
    os.nice(10)
except OSError:
    pass
import numpy as np
info = {"ok": False}
t0 = time.time(); c0 = time.process_time()
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    start = np.load(sys.argv[6]) if sys.argv[6] != "-" else None
    out = np.asarray(mod.construct(budget, start), dtype=float)
    np.save(sys.argv[2], out)
    info = {"ok": True}
except BaseException as exc:
    info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": traceback.format_exc()[-2000:]}
info["wall"] = round(time.time() - t0, 2)
info["cpu"] = round(time.process_time() - c0, 2)
print("@@RESULT@@" + json.dumps(info))
'''


@contextlib.contextmanager
def eval_slot():
    n = max(1, int(os.environ.get("HELIX_EVAL_SLOTS", "2")))
    d = Path(os.environ.get("HELIX_SLOTS_DIR", ROOT / "runs" / ".slots"))
    d.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(n):
            f = open(d / f"slot{i}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                f.close()
                continue
            try:
                yield i
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
            return
        time.sleep(0.2)


def run_program(code, budget, start=None, mem_mb=1500):
    """(array or None, info: ok, error, traceback, cpu, wall, stdout_tail)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "candidate.py").write_text(code)
        (d / "runner.py").write_text(RUNNER)
        start_path = "-"
        if start is not None:
            np.save(d / "start.npy", np.asarray(start, dtype=float))
            start_path = str(d / "start.npy")
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "PYTHONHASHSEED": "0"}
        cpu_cap, wall_cap = int(budget * 1.25 + 10), budget * 2.5 + 30
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(d / "runner.py"), str(d / "candidate.py"), str(d / "out.npy"),
                                str(budget), str(cpu_cap), str(mem_mb), start_path],
                               cwd=d, env=env, capture_output=True, text=True, timeout=wall_cap)
            out = p.stdout
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return None, {"ok": False, "error": f"timed out after {wall_cap:.0f} s wall clock",
                          "wall": round(time.time() - t0, 1), "stdout_tail": out[-1000:]}
        info = {"ok": False, "error": f"no result (killed: CPU limit {cpu_cap} s or memory limit {mem_mb} MB?)"}
        res = [l for l in out.splitlines() if l.startswith("@@RESULT@@")]
        if res:
            info = json.loads(res[-1][len("@@RESULT@@"):])
        info.setdefault("wall", round(time.time() - t0, 1))
        info["stdout_tail"] = "\n".join(l for l in out.splitlines() if not l.startswith("@@RESULT@@"))[-1000:]
        arr = None
        if info.get("ok"):
            try:
                arr = np.load(d / "out.npy", allow_pickle=False)
            except Exception as exc:                                     # noqa: BLE001
                info.update(ok=False, error=f"result unreadable: {exc}")
        return arr, info


def evaluate(problem, code, start, budget, mem_mb=1500):
    """Run, check and score. Returns valid, score, start_score, delta, feedback (lines), error, cpu, construction."""
    with eval_slot():
        arr, info = run_program(code, budget, start, mem_mb)
    out = {"valid": False, "score": None, "start_score": None, "delta": None, "feedback": [], "error": "",
           "cpu": info.get("cpu"), "construction": None}
    if start is not None:
        x0, _ = problem.check(start)
        out["start_score"] = problem.score(x0) if x0 is not None else None
    tail = [t[:160] for t in (info.get("stdout_tail") or "").strip().splitlines()[-3:]]
    if not info.get("ok"):
        tb = (info.get("traceback") or "").strip().splitlines()
        out["error"] = info.get("error") or "failed"
        out["feedback"] = [f"FAILED: {out['error']}"] + ([f"traceback (end): {' | '.join(tb[-3:])}"] if tb else [])
        return out
    x, why = problem.check(arr)
    if x is None:
        out["error"] = f"invalid result: {why}"
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    try:
        s = float(problem.score(x))
        if not np.isfinite(s):
            raise ValueError(f"score is {s}")
        lines = problem.describe(x)
    except Exception as exc:                                             # noqa: BLE001
        out["error"] = f"the result could not be scored: {type(exc).__name__}: {exc}"[:300]
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    head = f"score {s:.9f}" + (f" (its start scored {out['start_score']:.9f}: {s - out['start_score']:+.9f})"
                               if out["start_score"] is not None else " (no start)")
    lines = [head] + lines + [f"CPU {info.get('cpu')} s of {budget:.0f} s"]
    if tail:
        lines.append("its last printed lines: " + " | ".join(tail))
    out.update(valid=True, score=s, feedback=lines, construction=x)
    if out["start_score"] is not None:
        out["delta"] = s - out["start_score"]
    return out
