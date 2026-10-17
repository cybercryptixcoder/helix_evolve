# Helix v3 policy: binpack2d, gap 6.677%, progress 28.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 tightest_fit_worst_leftover (deep): Negative of the larger post-placement leftover fraction (worst-case leftover), per candidate bin.
def _f005(item, bins, capacity):
    """Negative of the larger post-placement leftover fraction (worst-case leftover), per candidate bin."""
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap > 0, cap, 1.0)
    rem = np.clip(np.asarray(bins, dtype=float) - np.asarray(item, dtype=float), 0.0, None) / cap
    return -np.max(rem, axis=1)

# f018 stranding_guard_threshold (deep): Negative indicator that placing the item leaves a stranded bin (<5% one resource, >25% the other).
def _f018(item, bins, capacity):
    """Negative indicator that placing the item leaves a stranded bin (<5% one resource, >25% the other)."""
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap <= 0, 1.0, cap)
    b = np.asarray(bins, dtype=float) / cap
    it = np.asarray(item, dtype=float) / cap
    rem = b - it
    lo = np.minimum(rem[:, 0], rem[:, 1])
    hi = np.maximum(rem[:, 0], rem[:, 1])
    stranded = (lo < 0.05) & (hi > 0.25)
    return -1.0 * stranded.astype(float)

# f034 item_scaled_stranding_guard (deep): Negative product of (post-placement minority below the item's own minority) and (post-placement majority above
def _f034(item, bins, capacity):
    """Negative product of (post-placement minority below the item's own minority) and (post-placement majority above the item's own majority), both scaled by the item's own resource fractions."""
    cap = np.maximum(np.asarray(capacity, dtype=float), 1e-9)
    b = np.asarray(bins, dtype=float) / cap
    it = np.asarray(item, dtype=float) / cap
    L = np.clip(b - it, 0.0, None)
    m = np.min(L, axis=1)
    M = np.max(L, axis=1)
    imin = float(np.min(it))
    imax = float(np.max(it))
    low = np.clip(1.0 - m / max(imin, 1e-3), 0.0, 1.0)
    high = np.clip((M - imax) / max(imax, 1e-3), 0.0, 1.0)
    return -(low * high)

# f040 item_axis_fit_intensity (wide): Post-placement leftover of the resource the item uses more of, relative to that bin's current slack on that re
def _f040(item, bins, capacity):
    """Post-placement leftover of the resource the item uses more of, relative to that bin's current slack on that resource (fit intensity)."""
    cap = np.maximum(np.asarray(capacity, dtype=float), 1e-9)
    b = np.asarray(bins, dtype=float) / cap
    it = np.asarray(item, dtype=float) / cap
    # resource index where the item is relatively larger
    axis = int(np.argmax(it))
    other = 1 - axis
    # candidate must be able to hold the item on both resources
    left_axis = np.clip(b[:, axis] - it[axis], 0.0, None)
    left_other = np.clip(b[:, other] - it[other], 0.0, None)
    feasible = (b[:, axis] >= it[axis] - 1e-9) & (b[:, other] >= it[other] - 1e-9)
    # fraction of the bin's axis slack consumed by the item
    consumed = np.clip(it[axis] / np.maximum(b[:, axis], 1e-3), 0.0, 1.0)
    # penalty if the minor resource becomes a near-empty sliver
    sliver = np.clip(1.0 - left_other / max(float(it[other]), 1e-3), 0.0, 1.0)
    val = consumed * (1.0 - 0.5 * sliver)
    val = np.where(feasible, val, -1.0)
    return -val

_TERMS = [(_f005, np.array([10.164535])), (_f018, np.array([6.078325])), (_f034, np.array([31.63943])), (_f040, np.array([1.096198]))]

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
