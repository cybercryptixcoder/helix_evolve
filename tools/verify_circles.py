"""Independent, exact check of a circle packing (n circles in the unit square, sum of radii).

Every coordinate is read as the exact rational value of its float; the containment and non-overlap conditions are
checked in exact rational arithmetic (squared distances, so no square roots): zero tolerance.

    python tools/verify_circles.py runs/lean/e1_core/floor-s1/best.npy [more.npy ...]
"""
import sys
from fractions import Fraction as F

import numpy as np


def verify(a):
    a = np.asarray(a, dtype=float)
    if a.ndim != 2 or a.shape[1] != 3 or not np.all(np.isfinite(a)):
        return False, "not an (n, 3) array of finite numbers", None
    q = [[F(v) for v in row] for row in a.tolist()]
    for i, (x, y, r) in enumerate(q):
        if not (r > 0 and x - r >= 0 and x + r <= 1 and y - r >= 0 and y + r <= 1):
            return False, f"circle {i} is not inside the square (or has radius <= 0)", None
    for i in range(len(q)):
        for j in range(i + 1, len(q)):
            (xi, yi, ri), (xj, yj, rj) = q[i], q[j]
            if (xi - xj) ** 2 + (yi - yj) ** 2 < (ri + rj) ** 2:
                return False, f"circles {i} and {j} overlap", None
    total = sum(r for _, _, r in q)
    return True, "valid", total


if __name__ == "__main__":
    for path in sys.argv[1:]:
        ok, why, total = verify(np.load(path))
        print(f"{path}: n = {len(np.load(path))}: {why}" + (f"; sum of radii = {float(total):.12f} "
                                                             f"(computed exactly, shown to 12 decimals)" if ok else ""))
