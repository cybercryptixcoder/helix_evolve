# Helix v3 policy: binpack1d, gap 3.415%, progress 39.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 exp_fit_matching (wide): Exponential fit-cost: exp(-remaining/item) per bin, large when remaining just fits the item.
def _f002(item, bins, capacity):
    """Exponential fit-cost: exp(-remaining/item) per bin, large when remaining just fits the item."""
    total = bins + item
    x = np.clip(total / max(capacity, 1), 0.0, 1.0)
    r = bins / max(capacity, 1)
    it = item / max(capacity, 1)
    # Free space after placing item, shaped by how "matching" the bin is
    room = (bins - item) / max(capacity, 1)
    return np.exp(-np.abs(room) * 4.0) * (1.0 - r) - 0.5

# f018 headroom_band_50 (deep): Gaussian band on leftover headroom (bins-item)/capacity peaking at 0.5, width 0.15, minus 0.5.
def _f018(item, bins, capacity):
    """Gaussian band on leftover headroom (bins-item)/capacity peaking at 0.5, width 0.15, minus 0.5."""
    leftover = (bins - item) / capacity
    return np.exp(-((leftover - 0.5) ** 2) / (2 * 0.15 ** 2)) - 0.5

# f035 exact_or_twin_fit (deep): Max of a tight-fit Gaussian (leftover ~0) and a same-size-pairing Gaussian (leftover ~ item), minus 0.35.
def _f035(item, bins, capacity):
    """Max of a tight-fit Gaussian (leftover ~0) and a same-size-pairing Gaussian (leftover ~ item), minus 0.35."""
    L = (bins - item) / capacity
    it = item / capacity
    tight = np.exp(-0.5 * (L / 0.05) ** 2)
    twin = 0.8 * np.exp(-0.5 * ((L - it) / 0.10) ** 2)
    return np.maximum(tight, twin) - 0.35

# f040 resonant_multifit_pairs (wide): Tight-fit vs pairing resonance: reward leftovers near 0 or near a multiple of the item size, with width scaled
def _f040(item, bins, capacity):
    """Tight-fit vs pairing resonance: reward leftovers near 0 or near a multiple of the item size, with width scaled by item size."""
    L = (bins - item) / capacity
    it = item / capacity
    # width of the pairing resonance grows with the item (small items pair loosely, large items sharply)
    w = 0.04 + 0.6 * it
    # resonance at leftover ~ m*item for m = 0,1,2 (exact, pair, triple)
    res = np.zeros_like(L)
    for m in range(3):
        mu = m * it
        width = (0.05 if m == 0 else w)
        amp = 1.0 if m == 0 else (0.8 if m == 1 else 0.5)
        res = np.maximum(res, amp * np.exp(-0.5 * ((L - mu) / width) ** 2))
    # scale resonance by how well the bin can host this item at all
    host = np.clip((bins - item) / max(capacity, 1) + 1.0, 0.0, 1.0)
    return res * host - 0.35

# f044 periodic_multiple_match (deep): Periodic multiple match: cosine of post-placement leftover in units of the item size, damped for tiny items.
def _f044(item, bins, capacity):
    """Periodic multiple match: cosine of post-placement leftover in units of the item size, damped for tiny items."""
    i = max(item, 1)
    L = (bins - item) / i
    feasible = bins >= item
    match = 0.5 * (1.0 + np.cos(2.0 * np.pi * L))
    amp = np.clip((item / capacity) / 0.5, 0.0, 1.0)
    val = amp * match - 0.4
    return np.where(feasible, val, -1.0)

_TERMS = [(_f002, np.array([5.49002])), (_f018, np.array([2.845862])), (_f035, np.array([13.491623])), (_f040, np.array([6.022036])), (_f044, np.array([-1.930518]))]

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
