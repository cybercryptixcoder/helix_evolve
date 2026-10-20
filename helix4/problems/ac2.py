"""The second autocorrelation inequality (C2): a lower bound by construction.

For f >= 0, R(f) = ||f*f||_2^2 / (||f*f||_1 * ||f*f||_inf) <= 1, and the constant C2 = sup R. Any non-negative
step function certifies C2 >= R(f). Records: 0.88922 (Matolcsi-Vinuesa 2010), 0.901564 (Boyer et al. 2025), 0.94136
(2025, 2,399 steps), 0.9610 (AlphaEvolve V2), 0.96258 (ImprovEvolve+E), 0.962643 (EinsteinArena, 2026, 400,000 steps).

A step function with N equal steps of heights h is evaluated exactly (Boyer et al., arXiv:2506.16750): f*f is
piecewise linear with knot values L_j = (h*h)[j-1], L_0 = L_2N = 0, so
  ||f*f||_2^2 = 1/3 sum (L_j^2 + L_j L_{j+1} + L_{j+1}^2),  ||f*f||_1 = (sum h)^2,  ||f*f||_inf = max L_j.
The ratio is invariant to scaling h and to the interval, so only the shape matters.
"""
from __future__ import annotations

import numpy as np

NAME = "ac2"
TITLE = "Second autocorrelation inequality: maximise ||f*f||_2^2 / (||f*f||_1 ||f*f||_inf)"
MAX_N = 200_000
FRONTIER = [   # shown to the human only, never to the agents
    ("constant function (Code Zero)", 2 / 3),
    ("Matolcsi & Vinuesa 2010", 0.88922),
    ("Boyer et al. 2025 (human)", 0.901564),
    ("Jaech & Joseph 2025 (human, published)", 0.94136),
    ("AlphaEvolve V2 (2025)", 0.9610),
    ("ImprovEvolve+E (2026)", 0.96258),
    ("EinsteinArena best (2026)", 0.962643),
]


def autoconv(h):
    n = len(h)
    if n <= 4096:
        return np.convolve(h, h)
    size = 1 << int(np.ceil(np.log2(2 * n - 1)))
    F = np.fft.rfft(h, size)
    return np.fft.irfft(F * F, size)[: 2 * n - 1]


def ratio_parts(h):
    h = np.asarray(h, dtype=float)
    c = np.maximum(autoconv(h), 0.0)
    g = np.concatenate(([0.0], c, [0.0]))
    a, b = g[:-1], g[1:]
    l2 = float(np.sum(a * a + a * b + b * b) / 3.0)
    linf = float(g.max())
    l1 = float(h.sum()) ** 2
    return l2, l1, linf, g


def score(h):
    l2, l1, linf, _ = ratio_parts(h)
    return l2 / (l1 * linf) if l1 > 0 and linf > 0 else 0.0


def check(arr):
    """Returns (heights or None, problem text)."""
    if arr is None:
        return None, "no result"
    a = np.asarray(arr, dtype=float).ravel()
    if a.size < 1:
        return None, "empty array"
    if a.size > MAX_N:
        return None, f"too many steps: {a.size} (at most {MAX_N})"
    if not np.all(np.isfinite(a)):
        return None, "contains NaN or infinity"
    if np.any(a < 0):
        return None, f"{int((a < 0).sum())} negative heights (the function must be non-negative)"
    if a.max() <= 0:
        return None, "all heights are zero"
    return a / a.max(), ""          # R is scale-invariant; normalising keeps huge or tiny heights from overflowing


# ---------------------------------------------------------------------------------------------- for the engine
DESCRIPTION = """## The problem: a lower bound for the second autocorrelation constant

For a non-negative function f, let f*f be its autoconvolution, (f*f)(x) = integral of f(t) f(x - t) dt. The quantity

    R(f) = ||f*f||_2^2 / ( ||f*f||_1 * ||f*f||_inf )

is at most 1 for every f (Hoelder's inequality). The goal is a non-negative f with R(f) as large as possible. Nobody
knows the true maximum: every construction with a higher R is a new, better lower bound. **Higher is better.**

f is given as a step function: a 1-D array h of N >= 1 non-negative heights, one per equal-width step (N is your
choice, up to 200,000). Scaling h, or the width of the interval, doesn't change R; only the shape matters. For such
an f, f*f is piecewise linear, and R is computed exactly from its knot values L = [0, *np.convolve(h, h), 0]:

    ||f*f||_2^2 = sum_j (L_j^2 + L_j L_{j+1} + L_{j+1}^2) / 3
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
- The result is checked (finite, non-negative, not all zero, at most 200,000 steps) and scored with the formula
  above, exactly.
"""

CODE_ZERO = '''import numpy as np


def construct(budget_seconds, start):
    """Code Zero: keep the start if there is one, otherwise a constant function (R = 2/3)."""
    if start is not None:
        return np.asarray(start, dtype=float)
    return np.ones(50)
'''


def feedback(h, start_h, info, budget):
    """Facts about the program's own result, in plain lines (never the record or a hint)."""
    s = score(h)
    l2, l1, linf, g = ratio_parts(h)
    lines = []
    if start_h is not None:
        s0 = score(start_h)
        same = len(start_h) == len(h) and np.allclose(start_h / max(start_h.sum(), 1e-300), h / h.sum(), rtol=0, atol=1e-12)
        lines.append(f"score {s:.6f} (its start scored {s0:.6f}: {s - s0:+.6f})" + ("; the result is the start unchanged" if same else ""))
        lines.append(f"N = {len(h)} steps (start had {len(start_h)})")
    else:
        lines.append(f"score {s:.6f} (no start)")
        lines.append(f"N = {len(h)} steps")
    nz = h > 0
    lines.append(f"{100 * (1 - nz.mean()):.1f}% of heights are zero; largest height / mean height = "
                 f"{h.max() / max(h.mean(), 1e-300):.2f}")
    peak = int(np.argmax(g))
    near = [100 * float((g >= (1 - t) * linf).mean()) for t in (0.001, 0.01, 0.05)]
    lines.append(f"f*f: {near[0]:.2f}% / {near[1]:.2f}% / {near[2]:.2f}% of its knots are within 0.1% / 1% / 5% of "
                 f"its maximum; the maximum is at {peak / max(len(g) - 1, 1):.3f} of the support")
    # scale-free parts: f with unit mass on [0, 1], so ||f*f||_1 = 1 and R = ||f*f||_2^2 / ||f*f||_inf
    n = len(h)
    lines.append(f"with f scaled to unit mass on [0, 1]: ||f*f||_inf = {linf * n / l1:.6f}, "
                 f"||f*f||_2^2 = {l2 * n / l1 ** 2:.6f} (R is the second over the first)")
    lines.append(f"CPU {info.get('cpu', '?')} s of the {budget:.0f} s budget, wall {info.get('wall', '?')} s")
    return s, lines
