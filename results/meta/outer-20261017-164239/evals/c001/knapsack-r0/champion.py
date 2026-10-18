# Helix v3 policy: knapsack, gap 0.042%, progress 99.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 relative_density_log_ratio (wide): Density of the candidate relative to the best density still available (log-ratio, signed).
def _f002(values, weights, remaining, capacity, taken):
    """Density of the candidate relative to the best density still available (log-ratio, signed)."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    dens = v / np.maximum(w, 1.0)
    best = np.max(dens)
    return np.log((dens + 1e-9) / (best + 1e-9)) / 10.0

# f018 stranded_leftover_indicator (deep): Negative stranded leftover (remaining - weight_i) when it is positive and smaller than the smallest other cand
def _f018(values, weights, remaining, capacity, taken):
    """Negative stranded leftover (remaining - weight_i) when it is positive and smaller than the smallest other candidate weight, normalised by capacity."""
    k = weights.shape[0]
    ws = np.sort(weights)
    # smallest weight among the OTHER candidates
    if k == 1:
        m = np.full(k, np.inf)
    else:
        # default: global minimum is the smallest other weight
        m = np.full(k, ws[0], dtype=float)
        # for the candidate(s) holding the unique minimum, use the second smallest
        min_mask = weights == ws[0]
        if np.count_nonzero(min_mask) == 1:
            m[min_mask] = ws[1]
    L = remaining - weights.astype(float)
    stranded = np.where((L > 0) & (L < m), L, 0.0)
    return -stranded / max(capacity, 1)

# f032 smooth_exact_fill_bonus (deep): Exponential decay of the leftover after taking each candidate, in units of the smallest other candidate weight
def _f032(values, weights, remaining, capacity, taken):
    """Exponential decay of the leftover after taking each candidate, in units of the smallest other candidate weight."""
    w = np.asarray(weights, dtype=float)
    k = w.shape[0]
    if k == 1:
        return np.zeros(1)
    rem = max(float(remaining), 1.0)
    order = np.argsort(w, kind="stable")
    s = np.empty(k)
    s[order[0]] = w[order[1]]
    s[order[1:]] = w[order[0]]
    L = rem - w
    return np.exp(-L / np.maximum(s, 1.0))

_TERMS = [(_f002, np.array([5.463197])), (_f018, np.array([67.807309])), (_f032, np.array([0.352753]))]

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
