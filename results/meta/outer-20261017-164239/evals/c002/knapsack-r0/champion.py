# Helix v3 policy: knapsack, gap 0.034%, progress 99.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 density_slack_tradeoff (wide): Profit density relative to the best candidate available, the fraction of free capacity left after taking the i
def _f001(values, weights, remaining, capacity, taken):
    """Profit density relative to the best candidate available, the fraction of free capacity left after taking the item, and their product."""
    v = values.astype(np.float64)
    w = np.maximum(weights.astype(np.float64), 1.0)
    dens = v / w
    best = dens.max() if dens.size else 1.0
    best = best if best > 0.0 else 1.0
    rel = dens / best                                    # in (0, 1]
    rem = max(float(remaining), 1.0)
    slack = np.clip((rem - w) / rem, 0.0, 1.0)           # fraction of free capacity left behind
    return np.column_stack([rel, slack, rel * slack])

# f024 two_item_completion (wide): Best value from the candidate plus the best single item that still fits in the capacity it leaves, and the fil
def _f024(values, weights, remaining, capacity, taken):
    """Best value from the candidate plus the best single item that still fits in the capacity it leaves, and the filler's share of that two-item total."""
    v = values.astype(np.float64)
    w = weights.astype(np.float64)
    k = v.size
    if k == 0:
        return np.zeros((0, 2))
    rem = float(remaining)
    idx = np.arange(k)
    resid = rem - w                              # free capacity after taking candidate
    fits = resid[:, None] >= w[None, :]          # other items that still fit
    fits &= (idx[:, None] != idx[None, :])       # exclude the candidate itself
    cand = np.where(fits, v[None, :], 0.0)
    best_fill = cand.max(axis=1)                 # 0 if nothing fits
    total = v + best_fill
    mx = total.max()
    if not np.isfinite(mx) or mx <= 0.0:
        return np.zeros((k, 2))
    col1 = total / mx - 0.5                      # how good the best two-item start is
    col2 = best_fill / (total + 1e-9)            # how much of it comes from the follow-up item
    return np.column_stack([col1, col2])

_TERMS = [(_f001, np.array([31.504475, -3.377884, -0.675745])), (_f024, np.array([4.990355, -0.22921]))]

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
