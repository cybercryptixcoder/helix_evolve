# Helix v3 policy: binpack1d, gap 3.606%, progress 34.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 squared_slack_after_placement (wide): Squared slack after placement, normalized: favours bins that end near-full but penalises tight fits strongly.
def _f002(item, bins, capacity):
    """Squared slack after placement, normalized: favours bins that end near-full but penalises tight fits strongly."""
    b = np.asarray(bins, dtype=float)
    rem = (b - item) / capacity          # remaining room fraction after placing item
    # quadratic closeness to zero: peak when rem ~ 0, mild when very loose, heavy penalty for near-overflow
    return -(rem * rem) - 0.5 * np.clip(rem, 0.0, None) * (rem < 0.15)

# f014 unfillable_residue_penalty (wide): Negative post-placement leftover, but only counted when it would leave a bin below the item's own size fractio
def _f014(item, bins, capacity):
    """Negative post-placement leftover, but only counted when it would leave a bin below the item's own size fraction (creates an unfillable residue), else zero."""
    b = np.asarray(bins, dtype=float)
    rem = (b - item) / capacity
    thr = item / capacity
    # residue is "dangerous" when leftover is positive but smaller than a typical item share
    danger = (rem > 0) & (rem < thr)
    return -rem * danger

# f040 half_item_leftover_band (deep): Negative squared deviation of post-placement leftover from half the item's size fraction, in a smooth band.
def _f040(item, bins, capacity):
    """Negative squared deviation of post-placement leftover from half the item's size fraction, in a smooth band."""
    rem = (bins - item) / capacity
    u = np.maximum(item / capacity, 1e-3)
    score = -(((rem - 0.5 * u) / (0.5 * u + 0.05)) ** 2)
    return score

_TERMS = [(_f002, np.array([6.110503])), (_f014, np.array([19.766659])), (_f040, np.array([0.017385]))]

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
