"""The evaluator for v4.5/v5: v4's, plus what the v4 traces showed the agents need.

- More of the program's own printed output comes back (8 lines, not 4): a v4 Researcher found its biggest
  improvement by reading a program's log ("seed2 reached 0.917612 but the pipeline returned 0.914222").
- Unused budget is stated plainly, since programs that stop early were a recurring waste in v4.
- Gains are labelled by size, so that +0.000001 of polishing isn't reported the same way as +0.03.
- Fresh starts: a program can be run with no start (start=None) to build a construction from scratch.
- From the finished v4 job (docs/V4_ANALYSIS.md): a program stopped at the CPU limit is scored on the construction it
  last kept (keep_best, see helix5/sandbox.py) instead of nothing, and its "stage" lines (where the budget went, what
  each stage gained) come back first, whatever else it printed.
"""
from __future__ import annotations

import time

import numpy as np

from helix4.evaluate import eval_slot
from helix5.sandbox import run_program

GAIN_EPS = 1e-5          # below this, a change in score is treated as no real change (numerical polishing)
BIG_GAIN = 1e-3


def gain_label(delta):
    if delta is None:
        return ""
    if delta >= BIG_GAIN:
        return "big gain"
    if delta >= GAIN_EPS:
        return "gain"
    if delta > -GAIN_EPS:
        return "no real change"
    return "loss"


def evaluate(problem, code, start, budget, mem_mb=1500, log_lines=8):
    t0 = time.time()
    with eval_slot():
        waited = time.time() - t0
        arr, info = run_program(code, budget, start=start, mem_mb=mem_mb)
    out = {"valid": False, "score": None, "start_score": None, "delta": None, "feedback": [], "error": "",
           "cpu": info.get("cpu"), "n": None, "construction": None, "waited": round(waited, 1)}
    if start is not None:
        h0, _ = problem.check(start)
        out["start_score"] = problem.score(h0) if h0 is not None else None
    stages = info.get("stage_lines") or []
    rest = [t[:200] for t in (info.get("stdout_tail") or "").strip().splitlines()
            if not t.strip().lower().startswith("stage")]
    tail = rest[-(4 if stages else log_lines):]
    if not info.get("ok"):
        tb = (info.get("traceback") or "").strip().splitlines()
        out["error"] = info.get("error") or "failed"
        out["feedback"] = [f"FAILED: {out['error']}"] + ([f"traceback (end): {' | '.join(tb[-3:])}"] if tb else []) \
            + ([f"its stage lines: {' | '.join(stages)}"] if stages else []) \
            + ([f"its last printed lines: {' | '.join(tail)}"] if tail else [])
        return out
    h, problem_text = problem.check(arr)
    if h is None:
        out["error"] = f"invalid result: {problem_text}"
        out["feedback"] = [f"FAILED: {out['error']}"] + ([f"its last printed lines: {' | '.join(tail)}"] if tail else [])
        return out
    try:
        s, lines = problem.feedback(h, problem.check(start)[0] if start is not None else None, info, budget)
        if not np.isfinite(s):
            raise ValueError(f"score is {s}")
    except Exception as exc:                                  # noqa: BLE001
        out["error"] = f"the result could not be scored: {type(exc).__name__}: {exc}"[:300]
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    if out["start_score"] is not None:
        out["delta"] = s - out["start_score"]
        lines[0] += f" [{gain_label(out['delta'])}]"
    cpu = info.get("cpu")
    if info.get("stopped") == "cpu":
        lines.append(f"it was stopped at the CPU limit ({info.get('cpu_cap', '?')} s); this is the construction it last "
                     f"kept with keep_best (it kept {info.get('kept', '?')} times)")
    if isinstance(cpu, (int, float)) and cpu < 0.6 * budget:
        lines.append(f"it stopped after {cpu:.1f} s of its {budget:.0f} s budget ({100 * (1 - cpu / budget):.0f}% unused)")
    if stages:
        lines.append(f"its stage lines: {' | '.join(stages)}")
    if tail:
        lines.append(f"its last printed lines: {' | '.join(tail)}")
    out["stopped"] = info.get("stopped")
    out.update(valid=True, score=s, feedback=lines, n=int(len(h)), construction=h)
    return out
