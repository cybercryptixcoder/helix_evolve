# Helix v3 policy: knapsack, gap 0.264%, progress 98.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 value_density_ratio (deep): Value-per-weight ratio of each candidate, scaled by the best ratio among candidates.
def _f005(values, weights, remaining, capacity, taken):
    """Value-per-weight ratio of each candidate, scaled by the best ratio among candidates."""
    d = values / np.maximum(weights, 1)
    return d / (d.max() + 1e-9)

# f004 density_excess_value (wide): How well a candidate's value fits the typical value density of the remaining pool: value minus the remaining-p
def _f004(values, weights, remaining, capacity, taken):
    """How well a candidate's value fits the typical value density of the remaining pool: value minus the remaining-pool density times its weight, normalised."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    rem = float(remaining)
    cap = float(capacity) if capacity else 1.0
    rem = max(rem, 1.0)
    # density of the whole remaining candidate pool (value per unit weight)
    pool_w = w.sum()
    pool_v = v.sum()
    density = pool_v / pool_w if pool_w > 0 else 0.0
    # value in excess of what this item's weight would be "worth" at pool density
    excess = v - density * w
    # scale by a robust typical magnitude of the excess
    scale = np.abs(excess).max()
    scale = scale if scale > 0 else 1.0
    return np.tanh(excess / scale)

# f016 density_gap_adaptive_fill (deep): Density z-score (tanh-squashed) plus a flatness-weighted weight-share term, where flatness is the pool density
def _f016(values, weights, remaining, capacity, taken):
    """Density z-score (tanh-squashed) plus a flatness-weighted weight-share term, where flatness is the pool density CV."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    R = float(remaining)
    dens = v / np.maximum(w, 1.0)
    if dens.size == 0:
        return np.zeros(0)
    mean = dens.mean()
    std = dens.std()
    z = (dens - mean) / (std + 1e-9)
    flat = min(std / (abs(mean) + 1e-9), 1.0)
    share = w / max(R, 1.0)
    # weight-share term is only informative when densities are flat; scale it by
    # the flatness so it can actually reorder candidates in the strongly-correlated case
    return np.tanh(0.5 * z) + flat * share

_TERMS = [(_f005, np.array([25.983243])), (_f004, np.array([0.56921])), (_f016, np.array([-1.529787]))]

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
