"""The problem's own exact scorer, importable by every candidate program as `helix_problem`.

v4.5-s3 found 0.919 while optimising a mis-coded score ((A+B)/3 instead of (2A+B)/3; docs/TRACE_STUDY.md section 7):
every program wrote its own scorer, and a wrong one silently steers the search. The toolkit is the evaluator's own
formula and nothing else (no records, no hints): `from helix_problem import score` gives the exact score of any array.
"""

AC2 = '''"""Exact scorer for the second autocorrelation inequality (the evaluator's own formula)."""
import numpy as np


def autoconv(h):
    """np.convolve(h, h), via FFT for long arrays (exact up to floating point)."""
    h = np.asarray(h, dtype=float)
    n = len(h)
    if n <= 4096:
        return np.convolve(h, h)
    size = 1 << int(np.ceil(np.log2(2 * n - 1)))
    F = np.fft.rfft(h, size)
    return np.fft.irfft(F * F, size)[: 2 * n - 1]


def knots(h):
    """The knot values L = [0, *(h*h), 0] of the piecewise-linear f*f."""
    c = np.maximum(autoconv(h), 0.0)
    return np.concatenate(([0.0], c, [0.0]))


def score(h):
    """R(f) = ||f*f||_2^2 / (||f*f||_1 ||f*f||_inf), exactly as the evaluator computes it (0 for invalid input)."""
    h = np.asarray(h, dtype=float).ravel()
    if h.size == 0 or not np.all(np.isfinite(h)) or np.any(h < 0) or h.max() <= 0:
        return 0.0
    h = h / h.max()
    g = knots(h)
    a, b = g[:-1], g[1:]
    l2 = float(np.sum(a * a + a * b + b * b) / 3.0)
    linf = float(g.max())
    l1 = float(h.sum()) ** 2
    return l2 / (l1 * linf) if l1 > 0 and linf > 0 else 0.0
'''

TOOLKITS = {"ac2": AC2}

NOTE = ("- You may also import the problem's exact scorer: `from helix_problem import score` (score(h) returns exactly "
        "the score the evaluator will give; `knots(h)` gives the f*f knot values). Use it instead of writing your own, "
        "so you never optimise a mis-coded score.")
