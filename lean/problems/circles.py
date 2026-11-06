"""Circle packing: n circles in the unit square, no overlaps, maximise the sum of their radii (n = 26 by default).

The benchmark of AlphaEvolve, OpenEvolve, ShinkaEvolve and ThetaEvolve. Checked with zero tolerance (as AlphaEvolve's
verifier): every circle inside the square, every pair at least the sum of their radii apart, in floating point.
OpenEvolve and ThetaEvolve allow 1e-6 of overlap and ShinkaEvolve 1e-7, which is worth about 1e-5 of score.
"""
from __future__ import annotations

import numpy as np

CODE_ZERO = '''import numpy as np


def construct(budget_seconds, start):
    """Code Zero: keep the start if there is one, otherwise {n} small equal circles on a grid."""
    if start is not None:
        return np.asarray(start, dtype=float)
    k = int(np.ceil(np.sqrt({n})))
    pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:{n}]
    return np.array([[x, y, 0.02] for x, y in pts])
'''


class Problem:
    def __init__(self, n=26):
        self.n = int(n)
        self.name = f"circles{self.n}"
        self.code_zero = CODE_ZERO.replace("{n}", str(self.n))
        self.references = {26: [("AlphaEvolve (May 2025; zero tolerance)", 2.63586276),
                                ("ShinkaEvolve (Sep 2025; exact re-check of its 1e-6-slack result)", 2.63597770931127),
                                ("ThetaEvolve (Nov 2025; 1e-6 slack)", 2.63598308),
                                ("best known (Packomania)", 2.635983084919)],
                           32: [("AlphaEvolve (May 2025)", 2.93794),
                                ("best known (Packomania; FICO Xpress, 2026)", 2.939572771205)]}.get(self.n, [])
        self.description = f"""## The problem: pack {self.n} circles in a unit square

Place {self.n} circles inside the square [0, 1] x [0, 1], with no two overlapping, so that the **sum of their radii
is as large as possible**. The circles may have different sizes. **Higher is better.**

## What you write

A Python module defining

    def construct(budget_seconds: float, start) -> numpy array of shape ({self.n}, 3)

- Row i is (x_i, y_i, r_i): the centre and radius of circle i.
- `start` is the result of the program you are improving on (an array of shape ({self.n}, 3)), or None at the very
  beginning. Building on it is allowed.
- It runs on one CPU core and must return within `budget_seconds` of CPU time (check `time.process_time()`); it is
  killed a little after that, and a killed program scores nothing. Leave a margin, but use the budget.
- Allowed imports: numpy, scipy, math, random, time, itertools, functools, heapq, collections. No files, no network.
- It may print short progress lines; the last lines are shown back to you.
- The result is checked **exactly, with zero tolerance**: every radius > 0; every circle inside the square
  (x - r >= 0, x + r <= 1, y - r >= 0, y + r <= 1); every pair at distance >= r_i + r_j, all in floating point. A
  single violation, however small, makes the result invalid (shrink radii by a tiny amount if you need to be safe).
  The score is the sum of the radii.
"""

    def check(self, arr):
        if arr is None:
            return None, "no result"
        a = np.asarray(arr, dtype=float)
        if a.shape != (self.n, 3):
            return None, f"shape {a.shape}, expected ({self.n}, 3)"
        if not np.all(np.isfinite(a)):
            return None, "contains NaN or infinity"
        x, y, r = a[:, 0], a[:, 1], a[:, 2]
        if np.any(r <= 0):
            return None, f"{int((r <= 0).sum())} radii are not positive"
        out = (x - r < 0) | (x + r > 1) | (y - r < 0) | (y + r > 1)
        if out.any():
            return None, f"{int(out.sum())} circles stick out of the square"
        d = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
        gap = d - (r[:, None] + r[None, :])
        np.fill_diagonal(gap, np.inf)
        if gap.min() < 0:
            i, j = np.unravel_index(np.argmin(gap), gap.shape)
            return None, f"{int((gap < 0).sum()) // 2} overlapping pairs (worst: circles {i} and {j}, by {-gap.min():.3g})"
        return a, ""

    def score(self, a):
        return float(np.sum(a[:, 2]))

    def describe(self, a):
        x, y, r = a[:, 0], a[:, 1], a[:, 2]
        d = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
        gap = d - (r[:, None] + r[None, :])
        np.fill_diagonal(gap, np.inf)
        wall = np.minimum.reduce([x - r, 1 - x - r, y - r, 1 - y - r])
        contacts = int((gap < 1e-9).sum()) // 2
        return [f"radii from {r.min():.4f} to {r.max():.4f} (mean {r.mean():.4f})",
                f"{contacts} touching pairs and {int((wall < 1e-9).sum())} circles touching a wall (within 1e-9); "
                f"smallest gap between circles {gap.min():.2e}"]
