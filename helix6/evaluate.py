"""The v4.6/v6 evaluator: v4.5's (helix5/evaluate.py), with three additions from the trace study (docs/TRACE_STUDY.md).

1. Inconclusive results. In v4 atlas-s1, generations 21-40, 31 of 54 planned experiments returned their start
   unchanged, 20 of them after using the whole budget. One of them (an exact augmented Lagrangian) had run 2 of its 6
   stages, and the Distiller recorded it as a mechanism-level failure. A program that returns its start unchanged
   (to 1e-12) after using at least 90% of its budget is now labelled INCONCLUSIVE: the change may not have had time to
   act. Memories don't count such a result as a failure.
2. The toolkit: the problem's exact scorer is written next to every program as `helix_problem.py`.
3. Per-program budgets: an experiment can be given more than the default 30 s (the planner splits its time).
"""
from __future__ import annotations

import time

import numpy as np

from helix4.evaluate import eval_slot
from helix5.evaluate import BIG_GAIN, GAIN_EPS, gain_label          # noqa: F401  (re-exported)
from helix6.sandbox import run_program
from helix6.toolkits import TOOLKITS

INCONCLUSIVE_CPU = 0.9          # share of the budget used, with the start returned unchanged


def is_inconclusive(delta, cpu, budget):
    return delta is not None and abs(delta) < 1e-12 and isinstance(cpu, (int, float)) and cpu >= INCONCLUSIVE_CPU * budget


def evaluate(problem, code, start, budget, mem_mb=1500, log_lines=8, toolkit=True):
    t0 = time.time()
    kit = TOOLKITS.get(getattr(problem, "NAME", "")) if toolkit else None
    with eval_slot():
        waited = time.time() - t0
        arr, info = run_program(code, budget, start=start, mem_mb=mem_mb, toolkit=kit)
    out = {"valid": False, "score": None, "start_score": None, "delta": None, "feedback": [], "error": "",
           "cpu": info.get("cpu"), "n": None, "construction": None, "waited": round(waited, 1),
           "inconclusive": False, "stopped": info.get("stopped"), "budget": budget}
    h0 = None
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
        s, lines = problem.feedback(h, h0, info, budget)
        if not np.isfinite(s):
            raise ValueError(f"score is {s}")
    except Exception as exc:                                  # noqa: BLE001
        out["error"] = f"the result could not be scored: {type(exc).__name__}: {exc}"[:300]
        out["feedback"] = [f"FAILED: {out['error']}"]
        return out
    cpu = info.get("cpu")
    if out["start_score"] is not None:
        out["delta"] = s - out["start_score"]
        out["inconclusive"] = is_inconclusive(out["delta"], cpu, budget)
        lines[0] += " [INCONCLUSIVE]" if out["inconclusive"] else f" [{gain_label(out['delta'])}]"
        if out["inconclusive"]:
            lines.insert(1, f"INCONCLUSIVE: it returned its start unchanged after using {cpu:.0f} s of its {budget:.0f} s: "
                            "the change may not have had time to act (its stage lines show how far it got). This is "
                            "not evidence that the change fails.")
    if info.get("stopped") == "cpu":
        lines.append(f"it was stopped at the CPU limit ({info.get('cpu_cap', '?')} s); this is the construction it last "
                     f"kept with keep_best (it kept {info.get('kept', '?')} times)")
    if isinstance(cpu, (int, float)) and cpu < 0.6 * budget:
        lines.append(f"it stopped after {cpu:.1f} s of its {budget:.0f} s budget ({100 * (1 - cpu / budget):.0f}% unused)")
    if stages:
        lines.append(f"its stage lines: {' | '.join(stages)}")
    if tail:
        lines.append(f"its last printed lines: {' | '.join(tail)}")
    out.update(valid=True, score=s, feedback=lines, n=int(len(h)), construction=h)
    return out
