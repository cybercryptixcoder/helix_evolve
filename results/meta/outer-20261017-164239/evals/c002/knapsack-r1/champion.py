# Helix v3 policy: knapsack, gap 0.028%, progress 99.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f007 residual_density_lookahead (deep): Estimated final knapsack value if candidate i is taken now: v_i + (remaining - w_i) * best value density among
def _f007(values, weights, remaining, capacity, taken):
    """Estimated final knapsack value if candidate i is taken now: v_i + (remaining - w_i) * best value density among candidates fitting in the leftover capacity, normalised by its max absolute value."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    dens = values / np.maximum(weights, 1.0)
    resid = remaining - weights
    fits = weights[None, :] <= resid[:, None]
    masked = np.where(fits, dens[None, :], -np.inf)
    best = masked.max(axis=1)
    best = np.where(np.isfinite(best), best, 0.0)
    est = values + resid * best
    scale = np.maximum(np.abs(est).max(), 1e-12)
    return est / scale

# f005 density_fill_mix (wide): Value share v/(v+w), knapsack fill w/remaining, and their product (efficient snug fit).
def _f005(values, weights, remaining, capacity, taken):
    """Value share v/(v+w), knapsack fill w/remaining, and their product (efficient snug fit)."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    rem = float(max(remaining, 1))
    dens = v / np.maximum(v + w, 1.0)          # normalised value-per-weight signal
    fill = w / rem                              # fraction of the residual capacity used
    mix = dens * fill                           # rewards light-but-dense items that fill well
    return np.stack([dens, fill, mix], axis=1)

# f015 stranded_capacity_pair_fit (wide): Residual capacity that taking each candidate would strand (too small to fit any other remaining item, soft and
def _f015(values, weights, remaining, capacity, taken):
    """Residual capacity that taking each candidate would strand (too small to fit any other remaining item, soft and hard), plus whether that residual equals another item's weight exactly."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    k = w.size
    rem = float(max(remaining, 1.0))
    cap = float(max(capacity, 1.0))
    if k == 0:
        return np.zeros((0, 3))
    r = np.clip(rem - w, 0.0, None)          # capacity left if this item is taken
    if k == 1:
        return np.stack([-r / cap, np.zeros(1), np.zeros(1)], axis=1)

    # smallest weight among the *other* candidates
    s = np.sort(w)
    min1, min2 = s[0], s[1]
    other_min = np.maximum(np.where(w <= min1, min2, min1), 1.0)

    terminal = (r < other_min).astype(float)          # nothing else would fit
    col1 = -terminal * r / cap                        # hard stranded-capacity penalty
    col2 = -np.maximum(other_min - r, 0.0) / other_min  # soft "nearly terminal" penalty

    # exact pair tiling: does some *other* item's weight equal the residual?
    eq = np.abs(w[None, :] - r[:, None]) <= 1e-9
    cnt = eq.sum(axis=1)
    self_in = np.abs(w - r) <= 1e-9
    col3 = ((cnt - self_in.astype(int)) > 0).astype(float)

    out = np.stack([col1, col2, col3], axis=1)
    return np.clip(np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)

_TERMS = [(_f007, np.array([26.949488])), (_f005, np.array([10.53203, -3.142871, 8.151416])), (_f015, np.array([0.821199, -0.019688, 0.583672]))]

def priority(values, weights, remaining, capacity, taken):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(values, weights, remaining, capacity, taken), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(values))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
