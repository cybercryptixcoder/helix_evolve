# Helix v3 policy: setcover, gap 4.501%, progress 98.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 rarity_weighted_efficiency (wide): Ratio of uncovered elements newly covered to the element's rarest availability among candidates.
def _f004(costs, new_cover, sizes, covers, total):
    """Ratio of uncovered elements newly covered to the element's rarest availability among candidates."""
    k = len(costs)
    # For each uncovered element, how many candidates can cover it (scarcity)
    avail = covers.sum(axis=0).astype(float)  # shape (u,)
    # Weight each covered element by its rarity: 1/avail
    rarity = 1.0 / np.maximum(avail, 1.0)
    # Sum rarity over the elements each candidate covers, normalised by cost
    weighted = covers.astype(float) @ rarity  # shape (k,)
    denom = np.maximum(costs, 1.0)
    score = weighted / denom
    # Normalise to roughly [-1, 1]
    scale = np.max(np.abs(score))
    if scale <= 0 or not np.isfinite(scale):
        return np.zeros(k)
    return score / scale

name: rarity_weighted_efficiency

# f008 rarity_weighted_coverage (deep): Sum over uncovered elements of 1/(number of candidates containing it), normalised by its max.
def _f008(costs, new_cover, sizes, covers, total):
    """Sum over uncovered elements of 1/(number of candidates containing it), normalised by its max."""
    cnt = covers.sum(axis=0).astype(float)
    w = 1.0 / np.maximum(cnt, 1.0)
    v = covers.astype(float) @ w
    return v / (v.max() + 1e-9)

# f016 cost_regret_vs_alternatives (deep): Negative cost of each candidate divided by the sum, over its newly covered elements, of the cheapest candidate
def _f016(costs, new_cover, sizes, covers, total):
    """Negative cost of each candidate divided by the sum, over its newly covered elements, of the cheapest candidate cost covering each such element, normalised by max abs value."""
    costs_f = costs.astype(float)
    big = np.where(covers, costs_f[:, None], np.inf)
    min_c = big.min(axis=0)  # shape (u,): cheapest candidate cost per uncovered element
    alt = covers.astype(float) @ min_c  # sum of cheapest alternatives over new elements
    val = -(costs_f / (alt + 1e-9))
    val = val / (np.max(np.abs(val)) + 1e-12)
    return val

# f022 last_chance_share_coverage (wide): Rarity-weighted coverage where each element's weight is 1/(avail-1) when it has a second coverer, and a large 
def _f022(costs, new_cover, sizes, covers, total):
    """Rarity-weighted coverage where each element's weight is 1/(avail-1) when it has a second coverer, and a large finite weight when it is the last chance (avail=1) — cost-scaled by the candidate's share of covers of that element."""
    cnt = covers.sum(axis=0).astype(float)  # avail per uncovered element
    # weight: high for scarce elements, but distinguish 'last chance' (avail==1) strongly
    w = np.where(cnt <= 1.0, 4.0, 1.0 / np.maximum(cnt - 1.0, 1.0))
    # each candidate's contribution: how much of the element's cover burden it carries
    share = np.where(covers, 1.0 / np.maximum(cnt[None, :], 1.0), 0.0)
    v = share @ w
    v = v - 0.15 * (costs.astype(float) / (np.mean(costs.astype(float)) + 1e-9))
    scale = np.max(np.abs(v))
    if scale <= 0 or not np.isfinite(scale):
        return np.zeros(len(costs))
    return v / scale

# f038 cheapest_burden_share_per_cost (wide): Cheapest-candidate cost per newly covered element, relative to the candidate's cost share: how much of the ele
def _f038(costs, new_cover, sizes, covers, total):
    """Cheapest-candidate cost per newly covered element, relative to the candidate's cost share: how much of the element's cheapest cover burden this candidate carries."""
    k = len(costs)
    costs_f = costs.astype(float)
    # cheapest candidate cost for each uncovered element
    big = np.where(covers, costs_f[:, None], np.inf)
    min_c = big.min(axis=0)  # (u,)
    # how many candidates cover each element
    avail = np.maximum(covers.sum(axis=0).astype(float), 1.0)
    # fraction of the element's cheapest coverage this candidate supplies
    share = np.where(covers, 1.0 / avail[None, :], 0.0)  # (k, u)
    # burden carried: share * cheapest cost, summed over elements
    burden = share @ min_c  # (k,)
    # normalise per element count for scale
    val = burden / np.maximum(costs_f, 1.0)
    val = val - np.mean(val)
    scale = np.max(np.abs(val))
    if scale <= 0 or not np.isfinite(scale):
        return np.zeros(k)
    return val / scale

# f052 raw_new_coverage_share (deep): Newly covered element count per candidate, divided by the max over candidates, plus a tiny tie-break by full s
def _f052(costs, new_cover, sizes, covers, total):
    """Newly covered element count per candidate, divided by the max over candidates, plus a tiny tie-break by full size."""
    v = new_cover.astype(float)
    m = v.max()
    if m <= 0:
        return np.zeros_like(v)
    base = v / m
    # tiny secondary term: among equal new_cover, prefer larger full sets (more overlap absorbed)
    s = sizes.astype(float)
    sm = s.max()
    if sm <= 0:
        return base
    return base + 1e-3 * (s / sm)

_TERMS = [(_f004, np.array([2.329516])), (_f008, np.array([4.532894])), (_f016, np.array([1.173327])), (_f022, np.array([1.137164])), (_f038, np.array([17.295206])), (_f052, np.array([1.774541]))]

def priority(costs, new_cover, sizes, covers, total):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(costs, new_cover, sizes, covers, total), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(costs))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
