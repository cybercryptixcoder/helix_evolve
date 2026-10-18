# Helix v3 policy: binpack1d, gap 3.601%, progress 35.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 fit_tightness_ratio (wide): Fit tightness: room left after placing the item, relative to the item, signed to favour snug fits.
def _f001(item, bins, capacity):
    """Fit tightness: room left after placing the item, relative to the item, signed to favour snug fits."""
    room = bins.astype(float)
    after = room - item
    # fraction of the bin that would remain free after placing the item
    waste = after / np.maximum(room, 1.0)
    # how much of the item the bin's free space covers beyond fitting
    tight = item / np.maximum(room, 1.0)
    # combine: prefer bins where the leftover is small and the item fills them
    val = (0.5 - waste) + 0.5 * (tight - 1.0)
    return np.clip(val, -1.0, 1.0)

# f016 stranded_residual_bump (deep): Penalises residual room after placement strictly inside (0, 0.30*capacity) with a bump peaking at -1 mid-band,
def _f016(item, bins, capacity):
    """Penalises residual room after placement strictly inside (0, 0.30*capacity) with a bump peaking at -1 mid-band, zero at 0 and at/above 0.30*capacity."""
    room = bins.astype(float)
    after = room - item
    cap = float(capacity)
    s = 0.30 * cap
    x = np.clip(after / s, 0.0, 1.0)
    bump = -4.0 * x * (1.0 - x)
    return np.where((after > 0.0) & (after < s), bump, 0.0)

_TERMS = [(_f001, np.array([1.993072])), (_f016, np.array([1.572878]))]

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
