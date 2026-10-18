# Helix v3 policy: knapsack, gap 0.025%, progress 99.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 relative_density_to_best (wide): Value density relative to the best density achievable right now (fraction of current max density).
def _f004(values, weights, remaining, capacity, taken):
    """Value density relative to the best density achievable right now (fraction of current max density)."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    dens = v / np.maximum(w, 1.0)
    best = np.max(dens) if dens.size > 0 else 0.0
    if best <= 0:
        return np.zeros_like(v)
    return dens / best - 0.5

# f001 density_residual_bite (wide): Value density, but scaled by how much of the residual capacity this item would consume.
def _f001(values, weights, remaining, capacity, taken):
    """Value density, but scaled by how much of the residual capacity this item would consume."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    cap = float(capacity) if capacity > 0 else 1.0
    rem = float(remaining) if remaining > 0 else 1.0
    # classic density, normalised to a stable range
    density = v / np.maximum(w, 1.0)
    # how large a bite of the original capacity this item takes
    bite = w / cap
    # fraction of the current residual capacity this item fills
    fill = w / rem
    # density weighted by the residual-space bite: prefer high value gains
    # that also use up a meaningful chunk of what's left, without being tiny
    raw = density * (1.0 - fill)
    # squash into roughly [-1, 1]
    return np.tanh(raw / 100.0)

# f016 late_exact_fit_slack_close (deep): Exact-fit reward: exp(-((rem-w)/rem / 0.05)^2) - 0.5, scaled by fill pressure 1 - rem/cap.
def _f016(values, weights, remaining, capacity, taken):
    """Exact-fit reward: exp(-((rem-w)/rem / 0.05)^2) - 0.5, scaled by fill pressure 1 - rem/cap."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    cap = float(capacity) if capacity > 0 else 1.0
    rem = float(remaining) if remaining > 0 else 1.0
    # fraction of the residual space that would be left over if this item were taken
    rel = (rem - w) / rem
    # sharp: ~1 only when the item nearly exactly consumes what is left
    tight = np.exp(-np.square(rel / 0.05))
    # fill pressure: 0 at the start, ->1 as the knapsack fills
    pressure = 1.0 - rem / cap
    return (tight - 0.5) * pressure

# f024 displaced_best_density_regret_ratio (wide): Regret of taking this item: the best density lost among items that would no longer fit, relative to this item'
def _f024(values, weights, remaining, capacity, taken):
    """Regret of taking this item: the best density lost among items that would no longer fit, relative to this item's own density."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    rem = float(remaining) if remaining > 0 else 1.0
    cap = float(capacity) if capacity > 0 else 1.0
    dens = v / np.maximum(w, 1.0)
    # remaining room after taking each candidate
    room = rem - w
    # for each candidate, the best density among candidates that would be excluded
    # (those whose weight exceeds the remaining room after taking it)
    out = np.empty_like(dens)
    for i in range(len(w)):
        mask = w > room[i]
        if np.any(mask):
            out[i] = np.max(dens[mask])
        else:
            out[i] = 0.0
    # regret: how much better the best displaced item is than this one, relative
    own = dens
    scale = np.maximum(own, 1e-9)
    regret = (out - own) / scale
    # multiply by how tight the situation is (later picks matter more)
    pressure = 1.0 - rem / cap
    return np.tanh(regret * 0.5) * (0.5 + 0.5 * pressure) - 0.25

_TERMS = [(_f004, np.array([12.179006])), (_f001, np.array([22.127724])), (_f016, np.array([0.809074])), (_f024, np.array([2.446251]))]

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
