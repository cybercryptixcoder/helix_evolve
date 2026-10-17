# Helix v3 policy: knapsack, gap 0.002%, progress 100.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 capacity_fill_fraction (wide): Efficiency of each candidate: value per unit weight, scaled to [-1, 1] by the best ratio among candidates.
def _f003(values, weights, remaining, capacity, taken):
    """Efficiency of each candidate: value per unit weight, scaled to [-1, 1] by the best ratio among candidates."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    eff = v / np.maximum(w, 1.0)
    hi = np.max(eff) if eff.size else 0.0
    if hi <= 0:
        return np.zeros_like(eff)
    # relative to best efficiency, centred so it spans [-1, 1]
    return 2.0 * (eff / hi) - 1.0

# f018 density_tail_fill_blend (deep): Blend of normalised density (early) and share-of-remaining fill (late), gated by remaining/capacity.
def _f018(values, weights, remaining, capacity, taken):
    """Blend of normalised density (early) and share-of-remaining fill (late), gated by remaining/capacity."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    cap = max(float(capacity), 1.0)
    rem = max(float(remaining), 1.0)
    eff = v / np.maximum(w, 1.0)
    eff_n = np.clip(eff / max(eff.max(), 1e-9), 0.0, 1.0)
    g = np.clip(1.0 - rem / (0.25 * cap), 0.0, 1.0)
    fill = np.clip(w / rem, 0.0, 1.0)
    return (1.0 - g) * (2.0 * eff_n - 1.0) + g * (2.0 * fill - 1.0)

# f041 exact_residual_reachability_fill (deep): Total fill achievable after taking each candidate: (w + largest reachable pool subset <= rem - w) / rem, gated
def _f041(values, weights, remaining, capacity, taken):
    """Total fill achievable after taking each candidate: (w + largest reachable pool subset <= rem - w) / rem, gated to rem <= 10% of capacity."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=np.int64)
    k = w.size
    rem = int(remaining)
    cap = max(float(capacity), 1.0)
    if k == 0 or rem <= 1 or rem > 0.10 * cap:
        return np.zeros(k)
    R = 1
    for wi in w:
        R |= R << int(wi)
    R &= (1 << (rem + 1)) - 1
    nbytes = max((R.bit_length() + 7) // 8, 1)
    bits = np.unpackbits(np.frombuffer(R.to_bytes(nbytes, 'little'), dtype=np.uint8), bitorder='little')[:rem + 1]
    idx = np.arange(bits.size)
    prev = np.maximum.accumulate(np.where(bits > 0, idx, -1))
    T = np.clip(rem - w, 0, bits.size - 1)
    reach = np.maximum(prev[T].astype(float), 0.0)
    return np.clip((w.astype(float) + reach) / float(rem), 0.0, 1.0)

# f058 value_weighted_residual_reachability (wide): Value-weighted reachability: max value obtainable from the pool after taking each candidate (exact reachable s
def _f058(values, weights, remaining, capacity, taken):
    """Value-weighted reachability: max value obtainable from the pool after taking each candidate (exact reachable subset by value), as share of pool value, gated to rem <= 12% of capacity."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=np.int64)
    k = w.size
    rem = int(remaining)
    cap = max(float(capacity), 1.0)
    if k == 0 or rem <= 1 or rem > 0.12 * cap:
        return np.zeros(k)

    # For the pool, compute for every reachable weight the maximum value achievable.
    # dp[wt] = best value using a subset of the pool with total weight exactly wt
    # Use a bitset-like DP over weight with value tracking (bounded by rem).
    best = np.full(rem + 1, -1.0)
    best[0] = 0.0
    for wi, vi in zip(w, v):
        wi = int(wi)
        if wi > rem:
            continue
        # shift: consider taking this item after each reachable weight
        cand = best[:rem + 1 - wi] + vi
        np.maximum(best[wi:], cand, out=best[wi:])
    # best[wt] = max value with weight <= wt (prefix max)
    reach_val = np.maximum.accumulate(best)

    # For each candidate i, the residual budget is rem - w[i]; the best value we could
    # add after taking i is reach_val over a pool that excludes i. Approximate by using
    # the full pool value (small overcount when i itself is used), but subtract i's own
    # contribution if it exceeds: simply use reach_val[rem - w[i]] and cap.
    T = np.clip(rem - w, 0, rem)
    post_val = reach_val[T]  # includes possibly using item i itself; that's fine as an upper blend
    total_val = reach_val[rem]
    if total_val <= 0:
        return np.zeros(k)
    # candidate's own value plus best achievable fill after it, normalized by total pool value
    return np.clip((v + post_val) / total_val, 0.0, 1.0) * 2.0 - 1.0

_TERMS = [(_f003, np.array([7.196316])), (_f018, np.array([1.175215])), (_f041, np.array([3.007555])), (_f058, np.array([214.396561]))]

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
