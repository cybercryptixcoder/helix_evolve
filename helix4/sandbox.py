"""Run one candidate program in its own process, with CPU, memory and wall-clock limits.

The candidate defines `construct(budget_seconds, start)` (the problem says what it returns). It runs in a fresh
Python process with one thread for numpy/BLAS, low priority, a CPU-time limit, an address-space limit and a
wall-clock timeout. Its result is saved as .npy and read back here; stdout and stderr are kept (tails) for the
evaluator's feedback.
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
    out = np.asarray(out, dtype=float)
    np.save(sys.argv[2], out)
    info = {"ok": True}
except BaseException as exc:
    tb = traceback.format_exc()
    info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "traceback": tb[-2500:]}
info["wall"] = round(time.time() - t0, 2)
info["cpu"] = round(time.process_time() - c0, 2)
print("@@RESULT@@" + json.dumps(info))
'''


def run_program(code: str, budget: float, start=None, mem_mb: int = 1500, workdir=None):
    """Returns (array or None, info dict with ok, error, traceback, wall, cpu, stdout_tail, stderr_tail)."""
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
        cpu_cap = int(budget * 1.25 + 10)
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
                          "stdout_tail": out[-1500:], "stderr_tail": err[-1500:]}
        info = {"ok": False, "error": "the program exited without a result (killed: CPU or memory limit?)"}
        lines = [l for l in out.splitlines() if l.startswith("@@RESULT@@")]
        if lines:
            info = json.loads(lines[-1][len("@@RESULT@@"):])
        elif p.returncode < 0:
            info["error"] = f"killed by signal {-p.returncode} (CPU limit {cpu_cap} s or memory limit {mem_mb} MB)"
        info.setdefault("wall", round(time.time() - t0, 1))
        info["stdout_tail"] = "\n".join(l for l in out.splitlines() if not l.startswith("@@RESULT@@"))[-1500:]
        info["stderr_tail"] = err[-1500:]
        arr = None
        if info.get("ok") and (d / "out.npy").exists():
            try:
                arr = np.load(d / "out.npy", allow_pickle=False)
            except Exception as exc:                          # noqa: BLE001
                info.update(ok=False, error=f"result unreadable: {exc}")
        return arr, info
