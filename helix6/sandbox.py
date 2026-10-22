"""The v4.6/v6 sandbox: v4.5's (helix5/sandbox.py: anytime results with keep_best, stage lines), plus the problem's
exact scorer written next to the candidate as `helix_problem.py`, so programs can `from helix_problem import score`
(helix6/toolkits.py). The runner and its limits are unchanged; each program's budget is passed per call, so the
researcher can give one experiment 60 or 90 s instead of 30 (docs/V6_DESIGN.md)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from helix5.sandbox import RUNNER, cpu_cap_for, stage_lines


def run_program(code: str, budget: float, start=None, mem_mb: int = 1500, workdir=None, toolkit=None):
    """Returns (array or None, info dict with ok, error, traceback, wall, cpu, stopped, stdout_tail, stderr_tail,
    stage_lines)."""
    with tempfile.TemporaryDirectory(dir=workdir) as d:
        d = Path(d)
        (d / "candidate.py").write_text(code)
        (d / "runner.py").write_text(RUNNER)
        if toolkit:
            (d / "helix_problem.py").write_text(toolkit)
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


