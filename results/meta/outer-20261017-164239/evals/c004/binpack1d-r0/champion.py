# Helix v3 policy: binpack1d, gap 3.921%, progress 27.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 residual_gap_class_flexibility (wide): Fit slack after placing, ranked by how many distinct residual 'gap classes' the bin can still accept (finer re
def _f005(item, bins, capacity):
    """Fit slack after placing, ranked by how many distinct residual 'gap classes' the bin can still accept (finer residual = more future flexibility)."""
    b = np.asarray(bins, dtype=float)
    cap = float(capacity)
    rem = b - float(item)
    fits = rem >= 0
    # residual fraction after placement
    r = np.where(fits, rem / cap, 0.0)
    # count how many of the item's own size could still fit: large residual => coarse packing potential
    # treat the residual as an approximate number of "average items" left; use log to spread classes
    n_left = np.where(fits, rem / max(float(item), 1.0), 0.0)
    # flexibility: prefer bins whose residual is NOT an exact multiple-ish of item (avoids stranding small holes)
    frac = np.abs(n_left - np.round(n_left))
    val = np.where(fits, -np.abs(frac - 0.5) * 2.0 + r, -2.0)
    return np.clip(val, -1.0, 1.0)

# f004 squared_residual_slack_after_placement (wide): Squared relative slack of each bin after placing the item, scaled so a perfect fit is 0 and an empty bin is 1.
def _f004(item, bins, capacity):
    """Squared relative slack of each bin after placing the item, scaled so a perfect fit is 0 and an empty bin is 1."""
    room = bins.astype(float)
    cap = float(capacity)
    after = (room - item) / cap
    after = np.clip(after, 0.0, 1.0)
    # bins that cannot fit the item are less relevant; mark them with the current slack
    fits = room >= item
    val = after * after
    val = np.where(fits, val, 1.0)
    return val

_TERMS = [(_f005, np.array([-3.99953])), (_f004, np.array([-1.896963]))]

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
