"""The third autocorrelation inequality (signed): a real-valued step function f on [-1/4, 1/4], negative values
allowed, with C(f) = max_t |f*f(t)| / (integral f)^2 as SMALL as possible (every f proves C3 <= C(f)).

The maximum of |f*f|, not of f*f: the definition of teorth.github.io/optimizationproblems/constants/1d.html
(Georgiev, Gomez-Serrano, Tao, Wagner 2025, Problem 6.4). For n equal steps with heights h, f*f is piecewise
linear with knots at the steps, so exactly C(f) = 2n * max|np.convolve(h, h)| / (sum h)^2. The loop maximises, so
the score is -C(f); the agents are told so.
"""
from __future__ import annotations

import numpy as np

CODE_ZERO = '''import numpy as np


def construct(budget_seconds, start):
    """Code Zero: keep the start if there is one, otherwise a constant function (C = 2)."""
    if start is not None:
        return np.asarray(start, dtype=float)
    return np.ones(50)
'''


class Problem:
    def __init__(self, max_n=2000):
        self.max_n = int(max_n)
        self.name = "ac3"
        self.code_zero = CODE_ZERO
        self.minimize = True
        self.references = [("Matolcsi & Vinuesa (2010)", 1.4993), ("AlphaEvolve (Georgiev et al. 2025)", 1.4688),
                           ("CERT2026 (300 steps)", 1.4630715826075594), ("AER2026 (600 steps)", 1.459989046905384),
                           ("SCiEL (800 steps, best known)", 1.457854884921989)]
        self.description = f"""## The problem: an upper bound for the third (signed) autocorrelation constant

For a real-valued function f supported on [-1/4, 1/4] (**negative values are allowed**), let f*f be its
autoconvolution. The quantity

    C(f) = max_t |(f*f)(t)| / ( integral of f )^2

is at least some unknown constant C3 for every such f; each f proves C3 <= C(f). Note the absolute value: negative
lobes of f*f count as much as positive ones. The goal is f with **C(f) as small as possible. Lower C is better. The
score is -C (higher score is better).**

f is a step function: a 1-D array h of N real heights, one per equal-width step on [-1/4, 1/4]
(1 <= N <= {self.max_n:,}). Scaling h doesn't change C. It is computed exactly:

    C(f) = 2 N * max(abs(np.convolve(h, h))) / (sum h)^2

## What you write

A Python module defining

    def construct(budget_seconds: float, start) -> numpy array of heights

- `start` is the result of the program you are improving on, or None at the very beginning. Building on it is allowed and expected: improving a good `start` is the main way
  progress is made.
- It runs on one CPU core and must return within `budget_seconds` of CPU time (check `time.process_time()`); it is
  killed a little after that, and a killed program scores nothing. Leave a margin, but use the budget: a
  program that stops early wastes it. A good program keeps improving its construction until close to the end.
- Allowed imports: numpy, scipy, math, random, time, itertools, functools, heapq, collections. No files, no network.
- It may print short progress lines; the last lines are shown back to you.
- The result is checked (finite, sum not zero, at most {self.max_n:,} steps) and scored exactly.
"""

    def check(self, arr):
        if arr is None:
            return None, "no result"
        a = np.asarray(arr, dtype=float).ravel()
        if a.size < 1 or a.size > self.max_n:
            return None, f"{a.size:,} steps (1 to {self.max_n:,} allowed)"
        if not np.all(np.isfinite(a)):
            return None, "heights must be finite"
        s = float(np.sum(a))
        if abs(s) <= 1e-12 * max(1.0, float(np.abs(a).sum())):
            return None, "the heights sum to (almost) zero, so C is unbounded"
        return a / s, ""                       # scaled to sum 1 (C doesn't change)

    def value(self, h):
        return 2 * len(h) * float(np.max(np.abs(np.convolve(h, h)))) / float(np.sum(h)) ** 2

    def score(self, h):
        return -self.value(h)

    def describe(self, h):
        c = np.convolve(h, h)
        m = np.abs(c).max()
        return [f"C = {self.value(h):.9f} (score = -C)",
                f"N = {len(h):,} steps; {100 * float((h < 0).mean()):.1f}% of heights are negative; max f*f = "
                f"{c.max() / m:.4f} and min f*f = {c.min() / m:.4f} of max|f*f|; "
                f"{100 * float((np.abs(c) >= (1 - 1e-3) * m).mean()):.2f}% of knots are within 0.1% of max|f*f|"]
