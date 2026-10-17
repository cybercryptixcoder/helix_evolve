# Helix v3 policy: binpack1d, gap 3.373%, progress 40.5%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 post_leftover_sweet_spot (wide): Negative squared deviation of post-placement leftover from a target fraction of capacity, plus a term rewardin
def _f003(item, bins, capacity):
    """Negative squared deviation of post-placement leftover from a target fraction of capacity, plus a term rewarding exact-fit-friendly residues."""
    b = np.asarray(bins, dtype=float) / float(capacity)
    x = float(item) / float(capacity)
    post = np.clip(b - x, 0.0, 1.0)
    # prefer leftovers near ~1/3 capacity (classic harmonic-ish sweet spot), smooth
    dev = (post - 0.33) ** 2
    # reward bins whose post-leftover is a "nice" fraction complement (close to x) -> tight packing
    tight = np.abs(post - (b - x) * 0.0)  # placeholder shape
    exact = np.exp(-30.0 * np.abs(post))  # 1 when leftover ~ 0
    return np.tanh(2.0 * exact - 3.0 * dev) - 0.5 * np.tanh(3.0 * np.abs(post - x))

# f015 dead_residue_vs_usable_slot (deep): Exact-fit bonus + room-for-a-twin bonus - dead-band waste penalty scaled by item size.
def _f015(item, bins, capacity):
    """Exact-fit bonus + room-for-a-twin bonus - dead-band waste penalty scaled by item size."""
    b = bins / capacity
    x = item / capacity
    post = np.clip(b - x, 0.0, 1.0)
    exact = np.exp(-50.0 * post)
    usable = (post >= x).astype(float) * (1.0 - exact)
    dead = (post > 1e-3) & (post < x)
    waste = np.where(dead, 1.0 - post / max(x, 1e-9), 0.0)
    w = np.clip(2.0 * x, 0.0, 1.0)
    return exact + 0.6 * usable - 0.9 * waste * w

# f047 smooth_zero_target_ramp (deep): Negative saturating squared deviation of post-placement leftover from a ramp target 0.30*clip(1-x/0.30,0,1), w
def _f047(item, bins, capacity):
    """Negative saturating squared deviation of post-placement leftover from a ramp target 0.30*clip(1-x/0.30,0,1), width 0.18."""
    b = np.asarray(bins, dtype=float) / capacity
    x = item / capacity
    post = np.clip(b - x, 0.0, 1.0)
    t = 0.30 * np.clip(1.0 - x / 0.30, 0.0, 1.0)
    d = (post - t) / 0.18
    return -d * d / (1.0 + d * d)

_TERMS = [(_f003, np.array([2.865005])), (_f015, np.array([0.840728])), (_f047, np.array([0.772652]))]

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
