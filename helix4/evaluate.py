"""The evaluator: run a program from a start construction, check it, score it, describe the result.

Evaluations are the only CPU-heavy work, so they go through machine-wide slots: at most HELIX4_EVAL_SLOTS programs
run at the same time across every run on the machine (file locks in HELIX4_SLOTS_DIR), and none starts while the
machine has less than HELIX4_EVAL_MIN_MB of memory available.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import time
from pathlib import Path

import numpy as np

from helix4.sandbox import run_program

ROOT = Path(__file__).resolve().parent.parent


def _mem_available_mb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 1 << 30


@contextlib.contextmanager
def eval_slot():
    n = max(1, int(os.environ.get("HELIX4_EVAL_SLOTS", "2")))
    d = Path(os.environ.get("HELIX4_SLOTS_DIR", ROOT / "runs" / "v4" / ".slots"))
    d.mkdir(parents=True, exist_ok=True)
    need = int(os.environ.get("HELIX4_EVAL_MIN_MB", "600"))
    t0 = time.time()
    while True:
        if _mem_available_mb() >= need:
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
        # rough fairness without a shared queue: the longer a program has waited, the more often it checks, so it
        # is usually first to a freed slot (runs otherwise starve at random: one generation took 831 s in a test)
        time.sleep(max(0.05, 0.5 - (time.time() - t0) / 120))


def evaluate(problem, code, start, budget, mem_mb=1500):
    """Returns a dict: valid, score, start_score, delta, feedback (lines), error, cpu, n, construction, waited."""
    t0 = time.time()
    with eval_slot():
        waited = time.time() - t0
        arr, info = run_program(code, budget, start=start, mem_mb=mem_mb)
    out = {"valid": False, "score": None, "start_score": None, "delta": None, "feedback": [], "error": "",
           "cpu": info.get("cpu"), "n": None, "construction": None, "waited": round(waited, 1)}
    if start is not None:
        h0, _ = problem.check(start)
        out["start_score"] = problem.score(h0) if h0 is not None else None
    tail = (info.get("stdout_tail") or "").strip().splitlines()[-4:]
    if not info.get("ok"):
        tb = (info.get("traceback") or "").strip().splitlines()
        out["error"] = info.get("error") or "failed"
        out["feedback"] = [f"FAILED: {out['error']}"] + ([f"traceback (end): {' | '.join(tb[-3:])}"] if tb else []) \
            + ([f"its last printed lines: {' | '.join(tail)}"] if tail else [])
        return out
    h, problem_text = problem.check(arr)
    if h is None:
        out["error"] = f"invalid result: {problem_text}"
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    try:
        s, lines = problem.feedback(h, problem.check(start)[0] if start is not None else None, info, budget)
        if not np.isfinite(s):
            raise ValueError(f"score is {s}")
    except Exception as exc:                                  # noqa: BLE001  (a strange result never crashes the run)
        out["error"] = f"the result could not be scored: {type(exc).__name__}: {exc}"[:300]
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    if tail:
        lines.append(f"its last printed lines: {' | '.join(t[:160] for t in tail)}")
    out.update(valid=True, score=s, feedback=lines, n=int(len(h)), construction=h)
    if out["start_score"] is not None:
        out["delta"] = s - out["start_score"]
    return out
