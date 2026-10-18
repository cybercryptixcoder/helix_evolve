# Helix v3 policy: knapsack, gap 0.020%, progress 99.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 relative_density_fit_slack (wide): Value density relative to the best density still available (0..1), scaled by fit slack.
def _f001(values, weights, remaining, capacity, taken):
    """Value density relative to the best density still available (0..1), scaled by fit slack."""
    dens = values / np.maximum(weights, 1)
    best = np.max(dens)
    rel = dens / np.maximum(best, 1e-9)
    # how tightly the item fits the remaining capacity (smaller weight = tighter packing)
    fit = 1.0 - weights / np.maximum(remaining, 1)
    return rel * (0.5 + 0.5 * fit)

# f002 value_over_weight_plus_remaining (wide): Value density relative to the capacity-scaled remaining budget: value / (weight + remaining).
def _f002(values, weights, remaining, capacity, taken):
    """Value density relative to the capacity-scaled remaining budget: value / (weight + remaining)."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    rem = float(max(remaining, 1))
    return v / (w + rem)

# f013 value_over_shrunk_weight_budget (wide): Value divided by weight plus the average weight still left in the pool scaled by fill progress.
def _f013(values, weights, remaining, capacity, taken):
    """Value divided by weight plus the average weight still left in the pool scaled by fill progress."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    rem = float(max(remaining, 1))
    cap = float(max(capacity, 1))
    # progress through the knapsack: how much capacity has been consumed
    progress = 1.0 - rem / cap
    # average weight of the remaining pool, and its spread
    mean_w = float(np.mean(w)) if len(w) else 1.0
    std_w = float(np.std(w)) if len(w) else 0.0
    # shrink the penalty toward the pool mean as the knapsack fills; early on, punish heavy items
    penalty = w * (1.0 - 0.5 * progress) + mean_w * progress
    # bonus to items lighter than the pool's typical weight, scaled by spread
    light = (mean_w - w) / (std_w + 1e-6)
    score = v / (penalty + rem * (0.25 + 0.75 * progress) + 1e-9)
    return score + 0.1 * np.tanh(light)

# f027 density_blocking_cost (deep): Total weight of strictly-better-density candidates that picking each candidate would block, normalised by rema
def _f027(values, weights, remaining, capacity, taken):
    """Total weight of strictly-better-density candidates that picking each candidate would block, normalised by remaining capacity."""
    dens = values / np.maximum(weights, 1)
    r = remaining - weights  # residual capacity left after taking each candidate
    # blocked[i] = sum_j w_j * [dens_j > dens_i] * [w_j > r_i]
    better = (dens[None, :] > dens[:, None]).astype(float)  # (k, k)
    too_heavy = (weights[None, :] > r[:, None]).astype(float)  # (k, k)
    blocked = (better * too_heavy * weights[None, :]).sum(axis=1)
    blocked = blocked / max(remaining, 1)
    return np.clip(blocked, 0.0, 1.0)

# f043 one_step_fill_value_lookahead (deep): Value of each candidate plus a density-greedy fill of the residual capacity from the other candidates, normali
def _f043(values, weights, remaining, capacity, taken):
    """Value of each candidate plus a density-greedy fill of the residual capacity from the other candidates, normalised by the max and clipped to [0,1]."""
    k = values.shape[0]
    if k == 0:
        return np.zeros(0)
    v = values.astype(np.float64)
    w = weights.astype(np.float64)
    rem = float(remaining)

    # density order: v/w descending (guard zero weights)
    dens = np.where(w > 0, v / np.where(w > 0, w, 1.0), np.inf)
    order = np.argsort(-dens, kind="stable")
    ws = w[order]
    vs = v[order]
    cw = np.concatenate(([0.0], np.cumsum(ws)))   # cw[j] = weight of first j items
    cv = np.concatenate(([0.0], np.cumsum(vs)))   # cv[j] = value of first j items

    # rank of each candidate in the density order
    rank = np.empty(k, dtype=np.int64)
    rank[order] = np.arange(k)

    def fill(r, skip_rank):
        # value of density-greedy fill of capacity r from all candidates except skip_rank
        r = max(r, 0.0)
        # prefix length over the full sorted list that fits in r
        j = int(np.searchsorted(cw, r, side="right")) - 1
        j = max(j, 0)
        total_w = cw[j]
        total_v = cv[j]
        # if the skipped item is inside the fitted prefix, remove it and try to add the next item
        if skip_rank < j:
            total_w -= ws[skip_rank]
            total_v -= vs[skip_rank]
            # try to extend by one more item (the one at index j) if it fits now
            if j < k and total_w + ws[j] <= r:
                total_w += ws[j]
                total_v += vs[j]
        return total_v

    est = np.empty(k, dtype=np.float64)
    for i in range(k):
        est[i] = v[i] + fill(rem - w[i], rank[i])

    mx = np.max(est)
    if not np.isfinite(mx) or mx <= 0:
        return np.zeros(k)
    out = est / mx
    return np.clip(out, 0.0, 1.0)

_TERMS = [(_f001, np.array([6.170587])), (_f002, np.array([11.745528])), (_f013, np.array([10.187276])), (_f027, np.array([0.426857])), (_f043, np.array([169.816418]))]

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
