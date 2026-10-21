"""The v4.5/v5 sandbox: v4's (helix4/sandbox.py), with two additions the finished v4 job showed were needed.

1. Anytime results. In v4 a program still running at the CPU limit (1.25 x budget + 10 s) was killed and scored
   nothing. Late in atlas-s1, when the best line had reached N = 42,496 steps, 8 programs died this way, including
   all four children of the record in generation 19: a whole generation of the main line lost. Here every program
   can call `keep_best(h)` (predefined, no import) whenever its best construction improves; at the CPU limit the
   runner stops the program (SIGXCPU) and scores the construction it last kept.
2. Stage lines. Programs print one line per stage ("stage <name>: <before> -> <after>, <s> s"). v4 planners spent
   generations finding out that inherited stages had eaten the budget before the new stage ran (atlas-s1 g12-g16);
   these lines are collected separately from the rest of the output, so they always come back, however long the log.
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

STAGE_PREFIX = "stage"

RUNNER = r'''
import json, os, resource, signal, sys, time, traceback
budget, cpu_cap, mem_mb = float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
resource.setrlimit(resource.RLIMIT_CPU, (cpu_cap, cpu_cap + 4))
try:
    resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
except (ValueError, OSError):
    pass
try:
    os.nice(10)
except OSError:
    pass
import numpy as np


class _CPUStop(BaseException):
    pass


_kept = {"h": None, "n": 0}


def keep_best(h):
    """Remember h as the best construction so far; scored instead of nothing if the program hits the CPU limit."""
    try:
        _kept["h"] = np.array(h, dtype=float, copy=True)
        _kept["n"] += 1
    except Exception:
        pass


def _on_xcpu(signum, frame):
    raise _CPUStop()


signal.signal(signal.SIGXCPU, _on_xcpu)
info = {"ok": False}
t0 = time.time(); c0 = time.process_time()
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    mod.keep_best = keep_best
    spec.loader.exec_module(mod)
    start = np.load(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    out = mod.construct(budget, start)
    out = np.asarray(out, dtype=float)
    np.save(sys.argv[2], out)
    info = {"ok": True}
except _CPUStop:
    signal.signal(signal.SIGXCPU, signal.SIG_IGN)
    if _kept["h"] is not None:
        np.save(sys.argv[2], _kept["h"])
        info = {"ok": True, "stopped": "cpu", "kept": _kept["n"]}
    else:
        info = {"ok": False, "stopped": "cpu",
                "error": f"stopped at the CPU limit ({cpu_cap} s) with nothing kept (call keep_best(h) whenever the best improves)"}
except BaseException as exc:
    signal.signal(signal.SIGXCPU, signal.SIG_IGN)
    tb = traceback.format_exc()
    info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": tb[-2500:]}
info["wall"] = round(time.time() - t0, 2)
info["cpu"] = round(time.process_time() - c0, 2)
print("@@RESULT@@" + json.dumps(info), flush=True)
'''


def cpu_cap_for(budget):
    return int(budget * 1.25 + 10)


def run_program(code: str, budget: float, start=None, mem_mb: int = 1500, workdir=None):
    """Returns (array or None, info dict with ok, error, traceback, wall, cpu, stopped, stdout_tail, stderr_tail,
    stage_lines)."""
    with tempfile.TemporaryDirectory(dir=workdir) as d:
        d = Path(d)
        (d / "candidate.py").write_text(code)
        (d / "runner.py").write_text(RUNNER)
        start_path = "-"
        if start is not None:
            np.save(d / "start.npy", np.asarray(start, dtype=float))
            start_path = str(d / "start.npy")
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
        cpu_cap = cpu_cap_for(budget)
        wall_cap = budget * 2.5 + 30
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(d / "runner.py"), str(d / "candidate.py"), str(d / "out.npy"),
                                str(budget), str(cpu_cap), str(mem_mb), start_path],
                               cwd=d, env=env, capture_output=True, text=True, timeout=wall_cap)
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            return None, {"ok": False, "error": f"timed out after {wall_cap:.0f} s wall clock", "wall": round(time.time() - t0, 1),
                          "stdout_tail": out[-1500:], "stderr_tail": err[-1500:], "stage_lines": stage_lines(out)}
        info = {"ok": False, "error": "the program exited without a result (killed: CPU or memory limit?)"}
        lines = [l for l in out.splitlines() if l.startswith("@@RESULT@@")]
        if lines:
            info = json.loads(lines[-1][len("@@RESULT@@"):])
        elif p.returncode < 0:
            info["error"] = f"killed by signal {-p.returncode} (CPU limit {cpu_cap} s or memory limit {mem_mb} MB)"
        info.setdefault("wall", round(time.time() - t0, 1))
        rest = [l for l in out.splitlines() if not l.startswith("@@RESULT@@")]
        info["stdout_tail"] = "\n".join(rest)[-1500:]
        info["stderr_tail"] = err[-1500:]
        info["stage_lines"] = stage_lines(out)
        info["cpu_cap"] = cpu_cap
        arr = None
        if info.get("ok") and (d / "out.npy").exists():
            try:
                arr = np.load(d / "out.npy", allow_pickle=False)
            except Exception as exc:                          # noqa: BLE001
                info.update(ok=False, error=f"result unreadable: {exc}")
        return arr, info


def stage_lines(out, k=12):
    """The program's 'stage ...' lines (first k/2 and last k/2 if there are more), each clipped."""
    st = [l.strip()[:170] for l in (out or "").splitlines() if l.strip().lower().startswith(STAGE_PREFIX)]
    if len(st) > k:
        st = st[: k // 2] + [f"(... {len(st) - k} more stage lines ...)"] + st[-(k // 2):]
    return st
