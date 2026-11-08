"""The second autocorrelation inequality: a non-negative step function f with R(f) = ||f*f||_2^2 / (||f*f||_1
||f*f||_inf) as large as possible. Computed exactly from the step heights (Boyer et al., arXiv:2506.16750): f*f is
piecewise linear with knots L = [0, h*h, 0]. The step limit `max_n` is enforced exactly.
"""
from __future__ import annotations

import numpy as np

CODE_ZERO = '''import numpy as np


def construct(budget_seconds, start):
    """Code Zero: keep the start if there is one, otherwise a constant function (R = 2/3)."""
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


def parts(h):
    g = np.concatenate(([0.0], np.maximum(autoconv(np.asarray(h, dtype=float)), 0.0), [0.0]))
    a, b = g[:-1], g[1:]
    return float(np.sum(a * a + a * b + b * b) / 3.0), float(np.sum(h)) ** 2, float(g.max()), g


class Problem:
    def __init__(self, max_n=50_000):
        self.max_n = int(max_n)
        self.name = "ac2"
        self.code_zero = CODE_ZERO
        self.references = [("AlphaEvolve (May 2025)", 0.8962), ("Jaech & Joseph (Aug 2025)", 0.941362),
                           ("OpenEvolve (TTT-Discover, Table 2)", 0.9449), ("ThetaEvolve with RL", 0.9469),
                           ("TTT-Discover (Jan 2026)", 0.9591), ("AlphaEvolve V2 (Nov 2025; 50,000 steps)", 0.9610)]
        self.description = f"""## The problem: a lower bound for the second autocorrelation constant

For a non-negative function f, let f*f be its autoconvolution, (f*f)(x) = integral of f(t) f(x - t) dt. The quantity

    R(f) = ||f*f||_2^2 / ( ||f*f||_1 * ||f*f||_inf )

is at most 1 for every f (Hoelder's inequality). The goal is a non-negative f with R(f) as large as possible. Nobody
knows the true maximum: every construction with a higher R is a new, better lower bound. **Higher is better.**

f is given as a step function: a 1-D array h of N >= 1 non-negative heights, one per equal-width step (N is your
choice, up to {self.max_n:,}). Scaling h, or the width of the interval, doesn't change R; only the shape matters. For such
an f, f*f is piecewise linear, and R is computed exactly from its knot values L = [0, *np.convolve(h, h), 0]:

    ||f*f||_2^2 = sum_j (L_j^2 + L_j L_{{j+1}} + L_{{j+1}}^2) / 3
    ||f*f||_1   = (sum h)^2
    ||f*f||_inf = max_j L_j

## What you write

A Python module defining

    def construct(budget_seconds: float, start) -> numpy array of heights

- `start` is the construction of the program you are improving on (a NumPy array of heights), or None at the very
  beginning. Building on it is allowed and expected: improving a good `start` is the main way progress is made.
- It runs on one CPU core and must return within `budget_seconds` of CPU time (use `time.process_time()`); it is
  killed a little after that, and a killed program scores nothing. Leave a margin, but use the budget: a program
  that stops early wastes it. A good program keeps improving its construction until close to the end.
- Allowed imports: numpy, scipy, math, random, time, itertools, functools, heapq, collections. No files, no network.
- It may print short progress lines; the last lines are shown back to you.
- The result is checked (finite, non-negative, not all zero, at most {self.max_n:,} steps) and scored with the formula
  above, exactly.
"""

    def check(self, arr):
        if arr is None:
            return None, "no result"
        a = np.asarray(arr, dtype=float).ravel()
        if a.size < 1:
            return None, "empty array"
        if a.size > self.max_n:
            return None, f"too many steps: {a.size:,} (at most {self.max_n:,})"
        if not np.all(np.isfinite(a)):
            return None, "contains NaN or infinity"
        if np.any(a < 0):
            return None, f"{int((a < 0).sum())} negative heights"
        if a.max() <= 0:
            return None, "all heights are zero"
        return a / a.max(), ""

    def score(self, h):
        l2, l1, linf, _ = parts(h)
        return l2 / (l1 * linf) if l1 > 0 and linf > 0 else 0.0

    def describe(self, h):
        """v4's facts about an AC2 result (helix4/problems/ac2.py feedback), less those the core now gives for every
        problem (the score against the start, the size against the start's, the CPU and wall time)."""
        l2, l1, linf, g = parts(h)
        n = len(h)
        peak = int(np.argmax(g))
        near = [100 * float((g >= (1 - t) * linf).mean()) for t in (0.001, 0.01, 0.05)]
        return [f"N = {n} steps",
                f"{100 * (1 - (h > 0).mean()):.1f}% of heights are zero; largest height / mean height = "
                f"{h.max() / max(h.mean(), 1e-300):.2f}",
                f"f*f: {near[0]:.2f}% / {near[1]:.2f}% / {near[2]:.2f}% of its knots are within 0.1% / 1% / 5% of "
                f"its maximum; the maximum is at {peak / max(len(g) - 1, 1):.3f} of the support",
                f"with f scaled to unit mass on [0, 1]: ||f*f||_inf = {linf * n / l1:.6f}, "
                f"||f*f||_2^2 = {l2 * n / l1 ** 2:.6f} (R is the second over the first)"]
