# Helix v3 policy: binpack1d, gap 3.459%, progress 38.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 nice_remainder_fit (wide): Two columns: best-fit tightness (small leftover after placing) and closeness of the leftover to simple capacit
_NICE = np.array([0.0, 0.25, 1.0 / 3.0, 0.5, 2.0 / 3.0, 0.75, 1.0])


def _f005(item, bins, capacity):
    """Two columns: best-fit tightness (small leftover after placing) and closeness of the leftover to simple capacity fractions (0, 1/4, 1/3, 1/2, 2/3, 3/4, 1)."""
    cap = float(max(capacity, 1))
    leftover = np.clip((np.asarray(bins, dtype=float) - float(item)) / cap, 0.0, 1.0)
    # column 0: prefer bins that end up tight (small remaining room)
    col_fit = -leftover
    # column 1: prefer remainders that are "clean" fractions of capacity,
    # so the hole left behind is a plausible item size
    dist = np.min(np.abs(leftover[:, None] - _NICE[None, :]), axis=1)
    col_nice = 1.0 - 2.0 * dist
    return np.stack([col_fit, col_nice], axis=1)

_TERMS = [(_f005, np.array([5.122483, 27.826276]))]

def priority(item, bins, capacity):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(item, bins, capacity), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(bins))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
