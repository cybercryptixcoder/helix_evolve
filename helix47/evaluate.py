"""v4.7's evaluator: helix4's, plus the alternative construction a program may hand back.

A program's `construct(budget_seconds, start)` returns the heights, as in v4, or a dict
{"best": heights, "alternative": heights}. "best" is scored exactly as in v4. "alternative" is a different
construction the program found (typically a new idea that hasn't beaten the start yet). It is checked and scored
too, so the run can keep it instead of losing it (fix 1 in docs/V47_DESIGN.md).

Runs in its own process with the same limits as v4 (helix4/sandbox.py): one thread, low priority, CPU, memory and
wall-clock caps. Evaluations go through helix4's machine-wide slots.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from helix4.evaluate import eval_slot

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
    start = np.load(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    out = mod.construct(budget, start)
    alt = None
    if isinstance(out, dict):
        if "best" not in out:
            raise ValueError("construct returned a dict without a 'best' entry")
        alt = out.get("alternative")
        out = out["best"]
    np.save(sys.argv[2], np.asarray(out, dtype=float))
    info = {"ok": True}
    if alt is not None:
        try:
            np.save(sys.argv[7], np.asarray(alt, dtype=float))
            info["alternative"] = True
        except Exception as exc:
            info["alternative_error"] = f"{type(exc).__name__}: {exc}"[:200]
except BaseException as exc:
    tb = traceback.format_exc()
    info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": tb[-2500:]}
info["wall"] = round(time.time() - t0, 2)
info["cpu"] = round(time.process_time() - c0, 2)
print("@@RESULT@@" + json.dumps(info))
'''


def run_program(code: str, budget: float, start=None, mem_mb: int = 1500):
    """Returns (array or None, alternative array or None, info)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "candidate.py").write_text(code)
        (d / "runner.py").write_text(RUNNER)
        start_path = "-"
        if start is not None:
            np.save(d / "start.npy", np.asarray(start, dtype=float))
            start_path = str(d / "start.npy")
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
        cpu_cap = int(budget * 1.25 + 10)
        wall_cap = budget * 2.5 + 30
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(d / "runner.py"), str(d / "candidate.py"), str(d / "out.npy"),
                                str(budget), str(cpu_cap), str(mem_mb), start_path, str(d / "alt.npy")],
                               cwd=d, env=env, capture_output=True, text=True, timeout=wall_cap)
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            return None, None, {"ok": False, "error": f"timed out after {wall_cap:.0f} s wall clock",
                                "wall": round(time.time() - t0, 1), "stdout_tail": out[-1500:], "stderr_tail": err[-1500:]}
        info = {"ok": False, "error": "the program exited without a result (killed: CPU or memory limit?)"}
        lines = [l for l in out.splitlines() if l.startswith("@@RESULT@@")]
        if lines:
            info = json.loads(lines[-1][len("@@RESULT@@"):])
        elif p.returncode < 0:
            info["error"] = f"killed by signal {-p.returncode} (CPU limit {cpu_cap} s or memory limit {mem_mb} MB)"
        info.setdefault("wall", round(time.time() - t0, 1))
        info["stdout_tail"] = "\n".join(l for l in out.splitlines() if not l.startswith("@@RESULT@@"))[-1500:]
        info["stderr_tail"] = err[-1500:]
        arr = alt = None
        if info.get("ok") and (d / "out.npy").exists():
            try:
                arr = np.load(d / "out.npy", allow_pickle=False)
            except Exception as exc:                          # noqa: BLE001
                info.update(ok=False, error=f"result unreadable: {exc}")
        if info.get("ok") and info.get("alternative") and (d / "alt.npy").exists():
            try:
                alt = np.load(d / "alt.npy", allow_pickle=False)
            except Exception:                                 # noqa: BLE001  (an unreadable alternative is just dropped)
                alt = None
        return arr, alt, info


def same_shape(a, b, tol=1e-6):
    """True if two constructions are the same function (same length, same normalised heights)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        return False
    sa, sb = a.sum(), b.sum()
    if sa <= 0 or sb <= 0:
        return bool(np.array_equal(a, b))
    return bool(np.max(np.abs(a / sa - b / sb)) <= tol * max(np.max(np.abs(a / sa)), 1e-300))


def evaluate(problem, code, start, budget, mem_mb=1500):
    """helix4.evaluate.evaluate's result dict, plus "alternative": None or {score, construction, n, feedback}."""
    t0 = time.time()
    with eval_slot():
        waited = time.time() - t0
        arr, alt, info = run_program(code, budget, start=start, mem_mb=mem_mb)
    out = {"valid": False, "score": None, "start_score": None, "delta": None, "feedback": [], "error": "",
           "cpu": info.get("cpu"), "n": None, "construction": None, "waited": round(waited, 1), "alternative": None}
    h0 = None
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
        s, lines = problem.feedback(h, h0, info, budget)
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
    if alt is not None:
        ha, _ = problem.check(alt)
        if ha is not None and not same_shape(ha, h) and (h0 is None or not same_shape(ha, h0)):
            try:
                sa, alines = problem.feedback(ha, h0, info, budget)
                if np.isfinite(sa):
                    out["alternative"] = {"score": float(sa), "construction": ha, "n": int(len(ha)),
                                          "feedback": [l for l in alines if not l.startswith("CPU ")]}
            except Exception:                                 # noqa: BLE001
                pass
    return out
