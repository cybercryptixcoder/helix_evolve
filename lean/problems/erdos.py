"""Erdos's minimum overlap problem, upper bound: a step function h on [0, 2] with 0 <= h <= 1 and integral 1, with
M(h) = max_k integral h(x) (1 - h(x + k)) dx as SMALL as possible (every h proves the constant is <= M(h)).

Haugland's formulation (2016), as AlphaEvolve and TTT-Discover use it: h and 1 - h live on [0, 2] and are zero
outside it. For n equal steps of width 2/n, the overlap is piecewise linear in k with knots at the steps, so exactly
M = (2/n) * max(np.correlate(h, 1 - h, "full")). The integral must be 1: the mean height 1/2, within 1e-9. The
loop maximises, so the score is -M; the agents are told so.
"""
from __future__ import annotations

import numpy as np

CODE_ZERO = '''import numpy as np


def construct(budget_seconds, start):
    """Code Zero: keep the start if there is one, otherwise h = 1/2 everywhere (M = 1/2, Erdos's first bound)."""
    if start is not None:
        return np.asarray(start, dtype=float)
    return np.full(50, 0.5)
'''


def overlap(h):
    n = len(h)
    g = 1 - h
    if n <= 4096:
        c = np.correlate(h, g, "full")
    else:
        size = 1 << int(np.ceil(np.log2(2 * n - 1)))
        c = np.fft.irfft(np.fft.rfft(h, size) * np.conj(np.fft.rfft(g, size)), size)
        c = np.concatenate([c[size - (n - 1):], c[:n]])
    return c * (2 / n)


class Problem:
    def __init__(self, max_n=2000):
        self.max_n = int(max_n)
        self.name = "erdos"
        self.code_zero = CODE_ZERO
        self.minimize = True
        self.references = [("Haugland (2016)", 0.380927), ("AlphaEvolve (2025)", 0.380924),
                           ("OpenEvolve (TTT-Discover, Table 2)", 0.380965), ("Best of 25,600", 0.380906),
                           ("TTT-Discover (gpt-oss-120b)", 0.380876), ("Atris Labs (best known)", 0.3808585504)]
        self.description = f"""## The problem: an upper bound for Erdos's minimum overlap constant

Split the numbers 1..2n into two sets A and B of n each; M_k counts the solutions of a - b = k. Erdos asked for
the smallest possible max_k M_k, which grows like c n. In the continuous form (Haugland 2016): for a function h on
[0, 2] with 0 <= h <= 1 and integral of h equal to 1 (h is A's density, 1 - h is B's),

    M(h) = max over shifts k of  integral h(x) (1 - h(x + k)) dx      (h and 1 - h are zero outside [0, 2])

and every such h proves c <= M(h). The goal is h with **M(h) as small as possible. Lower M is better. The score is
-M (higher score is better).**

h is a step function: a 1-D array of N heights, one per equal-width step on [0, 2] (1 <= N <= {self.max_n:,}).
Every height must be in [0, 1] and the mean height must be 1/2 within 1e-9 (integral 1); nothing is rescaled
for you. It is computed exactly:

    M(h) = (2 / N) * max(np.correlate(h, 1 - h, "full"))

## What you write

A Python module defining

    def construct(budget_seconds: float, start) -> numpy array of heights

- `start` is the result of the program you are improving on, or None at the very beginning. Building on it is allowed.
- It runs on one CPU core and must return within `budget_seconds` of CPU time (check `time.process_time()`); it is
  killed a little after that, and a killed program scores nothing. Leave a margin, but use the budget.
- Allowed imports: numpy, scipy, math, random, time, itertools, functools, heapq, collections. No files, no network.
- It may print short progress lines; the last lines are shown back to you.
- The result is checked (finite, every height in [0, 1], mean height 1/2 within 1e-9, at most {self.max_n:,} steps) and scored exactly.
"""

    def check(self, arr):
        if arr is None:
            return None, "no result"
        a = np.asarray(arr, dtype=float).ravel()
        if a.size < 1 or a.size > self.max_n:
            return None, f"{a.size:,} steps (1 to {self.max_n:,} allowed)"
        if not np.all(np.isfinite(a)) or a.min() < 0 or a.max() > 1:
            return None, f"every height must be finite and in [0, 1] (got {a.min():.3g} to {a.max():.3g})"
        if abs(float(a.mean()) - 0.5) > 1e-9:
            return None, f"the mean height is {float(a.mean()):.12f}; it must be 1/2 within 1e-9 (integral 1)"
        return a, ""

    def value(self, h):
        return float(np.max(overlap(h)))

    def score(self, h):
        return -self.value(h)

    def describe(self, h):
        c = overlap(h)
        m = c.max()
        k = (int(np.argmax(c)) - (len(h) - 1)) * 2 / len(h)
        return [f"M = {self.value(h):.9f} (score = -M)",
                f"N = {len(h):,} steps; {100 * float((h <= 0).mean()):.1f}% of heights are 0, "
                f"{100 * float((h >= 1).mean()):.1f}% are 1; the worst shift is k = {k:+.4f}; "
                f"{100 * float((c >= m - 1e-4 * m).mean()):.2f}% of shifts are within 0.01% of the worst"]
