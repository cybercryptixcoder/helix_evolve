"""The first autocorrelation inequality: a non-negative step function f on [-1/4, 1/4] with
C(f) = max (f*f) / (integral f)^2 as SMALL as possible (every f proves C1 <= C(f)).

For n equal steps with heights h, f*f is piecewise linear with its maximum at a knot, so exactly
C(f) = 2n * max(np.convolve(h, h)) / (sum h)^2 (TTT-Discover's verifier, arXiv:2601.16175, appendix). The loop
maximises, so the score is -C(f); the agents are told so.
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


def autoconv(h):
    n = len(h)
    if n <= 4096:
        return np.convolve(h, h)
    size = 1 << int(np.ceil(np.log2(2 * n - 1)))
    F = np.fft.rfft(h, size)
    return np.fft.irfft(F * F, size)[: 2 * n - 1]


class Problem:
    def __init__(self, max_n=30_000):
        self.max_n = int(max_n)
        self.name = "ac1"
        self.code_zero = CODE_ZERO
        self.minimize = True
        self.references = [("Best human (TTT-Discover, Table 2)", 1.50973), ("AlphaEvolve (May 2025)", 1.50530),
                           ("OpenEvolve", 1.50719), ("ThetaEvolve", 1.50681), ("Best of 25,600", 1.51004),
                           ("AlphaEvolve V2", 1.50317), ("TTT-Discover (gpt-oss-120b)", 1.50287)]
        self.description = f"""## The problem: an upper bound for the first autocorrelation constant

For a non-negative function f supported on [-1/4, 1/4], let f*f be its autoconvolution. The quantity

    C(f) = max_t (f*f)(t) / ( integral of f )^2

is at least some unknown constant C1 for every such f; each f proves C1 <= C(f). The goal is a non-negative f with
**C(f) as small as possible. Lower C is better. The score is -C (higher score is better).**

f is a step function: a 1-D array h of N non-negative heights, one per equal-width step on [-1/4, 1/4]
(1 <= N <= {self.max_n:,}). Scaling h doesn't change C. It is computed exactly:

    C(f) = 2 N * max(np.convolve(h, h)) / (sum h)^2

## What you write

A Python module defining

    def construct(budget_seconds: float, start) -> numpy array of heights

- `start` is the result of the program you are improving on, or None at the very beginning. Building on it is allowed.
- It runs on one CPU core and must return within `budget_seconds` of CPU time (check `time.process_time()`); it is
  killed a little after that, and a killed program scores nothing. Leave a margin, but use the budget.
- Allowed imports: numpy, scipy, math, random, time, itertools, functools, heapq, collections. No files, no network.
- It may print short progress lines; the last lines are shown back to you.
- The result is checked (finite, non-negative, not all zero, at most {self.max_n:,} steps) and scored exactly.
"""

    def check(self, arr):
        if arr is None:
            return None, "no result"
        a = np.asarray(arr, dtype=float).ravel()
        if a.size < 1 or a.size > self.max_n:
            return None, f"{a.size:,} steps (1 to {self.max_n:,} allowed)"
        if not np.all(np.isfinite(a)) or np.any(a < 0) or a.max() <= 0:
            return None, "heights must be finite, non-negative and not all zero"
        return a / a.max(), ""

    def value(self, h):
        return 2 * len(h) * float(np.max(autoconv(h))) / float(np.sum(h)) ** 2

    def score(self, h):
        return -self.value(h)

    def describe(self, h):
        c = autoconv(h)
        near = 100 * float((c >= (1 - 1e-3) * c.max()).mean())
        return [f"C = {self.value(h):.9f} (score = -C)", f"N = {len(h):,} steps; "
                f"{100 * float((h <= 0).mean()):.1f}% of heights are zero; {near:.2f}% of f*f's knots are within "
                f"0.1% of its maximum"]
