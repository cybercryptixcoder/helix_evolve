# Helix v3 policy: binpack1d, gap 3.296%, progress 42.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f010 complement_pairing (deep): Gaussian reward for residual room near 0 or ~35% of capacity, minus 0.5.
def _f010(item, bins, capacity):
    """Gaussian reward for residual room near 0 or ~35% of capacity, minus 0.5."""
    lo = (bins - item) / capacity
    near_zero = np.exp(-(lo / 0.08) ** 2)
    near_target = np.exp(-((lo - 0.35) / 0.12) ** 2)
    return np.maximum(near_zero, near_target) - 0.5

# f018 comb_pairing (deep): Three-band comb on residual room after placing item: sharp peak at exact fit, dip near 8%, broad peak near 33%
def _f018(item, bins, capacity):
    """Three-band comb on residual room after placing item: sharp peak at exact fit, dip near 8%, broad peak near 33%, new bin neutral."""
    c = float(capacity)
    b = np.asarray(bins, float)
    u = np.clip((b - float(item)) / c, 0.0, 1.0)
    base = -0.35
    val = (np.exp(-(u / 0.025) ** 2)
           - 0.7 * np.exp(-((u - 0.08) / 0.05) ** 2)
           + 0.9 * np.exp(-((u - 0.33) / 0.08) ** 2)
           + base)
    val[-1] = base
    return val

# f019 size_scaled_pair_target (deep): Gaussian reward for residual room near 0 or near the item's own size fraction, minus 0.45.
def _f019(item, bins, capacity):
    """Gaussian reward for residual room near 0 or near the item's own size fraction, minus 0.45."""
    c = float(capacity)
    b = np.asarray(bins, float)
    x = float(item) / c
    u = np.clip((b - float(item)) / c, 0.0, 1.0)
    t = np.clip(x, 0.05, 0.55)
    val = np.exp(-(u / 0.03) ** 2) + 0.9 * np.exp(-((u - t) / 0.09) ** 2) - 0.45
    val[-1] = -0.45
    return val

_TERMS = [(_f010, np.array([4.940753])), (_f018, np.array([3.066397])), (_f019, np.array([2.20046]))]

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
