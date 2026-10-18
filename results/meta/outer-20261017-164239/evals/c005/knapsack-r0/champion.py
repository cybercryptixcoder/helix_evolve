# Helix v3 policy: knapsack, gap 0.033%, progress 99.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 greedy_density_ratio (deep): Value-to-weight density ratio of each candidate, normalised by the max ratio among candidates.
def _f004(values, weights, remaining, capacity, taken):
    """Value-to-weight density ratio of each candidate, normalised by the max ratio among candidates."""
    r = values / np.maximum(weights, 1)
    return r / np.maximum(r.max(), 1e-9)

# f001 density_fit_pressure (wide): Value density discounted by how much of the remaining capacity the item would consume (fit-pressure).
def _f001(values, weights, remaining, capacity, taken):
    """Value density discounted by how much of the remaining capacity the item would consume (fit-pressure)."""
    vals = np.asarray(values, dtype=float)
    wts = np.asarray(weights, dtype=float)
    rem = float(remaining)
    cap = float(capacity) if capacity else 1.0
    # fraction of the *remaining* capacity this item would eat (0..1]
    frac = wts / (rem + 1e-9)
    # density relative to capacity scale
    dens = vals / (wts + 1e-9)
    dens_norm = np.tanh(dens * wts.sum() / (cap + 1e-9) * 0.01)
    return dens_norm * (1.0 - frac)

# f014 density_plus_fill_bonus (deep): Normalised value density plus 0.3 times the fraction of remaining capacity the item would fill.
def _f014(values, weights, remaining, capacity, taken):
    """Normalised value density plus 0.3 times the fraction of remaining capacity the item would fill."""
    dens = values / (weights + 1e-9)
    dens_max = dens.max() if dens.size > 0 else 0.0
    dens_norm = dens / dens_max if dens_max > 0 else np.zeros_like(dens)
    rem = max(remaining, 1)
    return dens_norm + 0.3 * (weights / rem)

# f013 density_vs_postpick_opportunity (wide): Value of the candidate relative to the best value-per-weight achievable by the capacity it leaves behind.
def _f013(values, weights, remaining, capacity, taken):
    """Value of the candidate relative to the best value-per-weight achievable by the capacity it leaves behind."""
    vals = np.asarray(values, dtype=float)
    wts = np.asarray(weights, dtype=float)
    rem = float(remaining)
    cap = float(capacity) if capacity else 1.0
    slack = rem - wts  # capacity left after taking candidate
    # Opportunity density: the maximum density among candidates that would still fit
    # after taking this one, i.e. weights <= slack. Vectorised via masking.
    dens = vals / np.maximum(wts, 1.0)
    # For each candidate j, consider the pool of candidates i with wts[i] <= slack[j].
    # Approximate that pool's best density by a soft max weighted by fit.
    # Build a (k x k) feasibility indicator: candidate i fits after candidate j.
    feasible = (wts[None, :] <= slack[:, None]).astype(float)
    # Weight each feasible density by the fraction of leftover slack it consumes,
    # so that tight leftovers favour small high-density items.
    leftover = np.maximum(slack[:, None] - wts[None, :], 0.0)
    leftover_frac = leftover / (slack[:, None] + 1e-9)
    score = dens[None, :] * (1.0 - leftover_frac) * feasible
    best_after = score.max(axis=1)  # best density still attainable after this pick
    # Compare this candidate's density to that opportunity; positive = good pick now.
    own = dens
    denom = np.maximum(np.maximum(own, best_after), 1e-9)
    out = (own - best_after) / denom
    # Scale by how much slack remains (relative to capacity) so that picks leaving
    # room for follow-ups are not penalised the same as dead-ends.
    scale = np.tanh((slack / (cap + 1e-9)) * 2.0)
    return np.tanh(out) * (0.5 + 0.5 * scale)

# f010 density_median_size_gate (wide): Density priority gated by the item's size relative to the *median* candidate size, i.e. a rank-like fit.
def _f010(values, weights, remaining, capacity, taken):
    """Density priority gated by the item's size relative to the *median* candidate size, i.e. a rank-like fit."""
    vals = np.asarray(values, dtype=float)
    wts = np.asarray(weights, dtype=float)
    rem = float(remaining)
    cap = float(capacity) if capacity else 1.0
    # density relative to the scale of the candidate pool
    dens = vals / np.maximum(wts, 1.0)
    dens_norm = np.tanh(dens * wts.mean() / (cap + 1e-9) * 0.05)
    # gate: how the candidate's weight compares to the typical remaining candidate weight
    med = np.median(wts)
    rel = wts / (med + 1e-9)
    gate = 1.0 / (1.0 + np.maximum(rel - 1.0, 0.0) ** 2)
    # also reward candidates that leave the remaining capacity usable (fractional slack)
    slack = 1.0 - wts / (rem + 1e-9)
    return dens_norm * gate * (0.5 + 0.5 * slack)

name: density_median_size_gate

_TERMS = [(_f004, np.array([7.498378])), (_f001, np.array([11.415796])), (_f014, np.array([18.535037])), (_f013, np.array([-2.511957])), (_f010, np.array([296.622173]))]

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
