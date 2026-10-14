# p0037 | score -7.0339 | generation 5 | wide branch
# Helix feature policy | p0037, generation 5, 8 features
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math



# f0008 fullness_vs_item_size (deep, 1 value): s = (item[0]+item[1])/capacity; rem = (bins[:,0]+bins[:,1])/capacity; return -abs(rem - s) (peaks for bins whose total residual just matches
def _f0008(item, bins, capacity):
    """Negative absolute difference between a bin's total remaining fraction and the job's total demand fraction."""
    s = (item[0] + item[1]) / (capacity[0] + capacity[1])
    rem = (bins[:, 0] + bins[:, 1]) / (capacity[0] + capacity[1])
    return -np.abs(rem - s)


# f0016 dual_slack_balance (deep, 1 value): r = (bins - item)/capacity; return np.minimum(r[:,0], r[:,1]) - 0.5*np.abs(r[:,0]-r[:,1]) (peaks for bins that stay balanced and non-tight; 
def _f0016(item, bins, capacity):
    """Post-placement residual balance: min residual minus half the residual gap."""
    r = (bins - item) / capacity
    return np.minimum(r[:, 0], r[:, 1]) - 0.5 * np.abs(r[:, 0] - r[:, 1])


# f0010 gated_fullness_balance_match (wide, 1 value): Like fullness_vs_item_size but only counts bins whose tighter-resource residual is >= the job's need there; peaks when the slack after placi
def _f0010(item, bins, capacity):
    """Like fullness_vs_item_size but only counts bins whose tighter-resource residual is >= the job's need there; peaks when the slack after placing matches the job's own imbalance."""
    jc = item[0] / capacity[0]
    jm = item[1] / capacity[1]
    s = jc + jm
    rc = bins[:, 0] / capacity[0]
    rm = bins[:, 1] / capacity[1]
    rem = rc + rm
    post_c = rc - jc
    post_m = rm - jm
    tighter_post = np.minimum(post_c, post_m)
    tight_need = np.minimum(jc, jm)
    tighter_pre = np.minimum(rc, rm)
    gate = np.exp(-np.abs(tighter_pre - tight_need) / (s + 1e-09))
    base = -np.abs(rem - s)
    balance = -np.abs(post_c - post_m)
    return gate * (base + 0.5 * balance) + 0.5 * -np.abs(tighter_post)


# f0015 empty_bin_penalty_conditional (deep, 1 value): r = (bins - item)/capacity; fit = np.min(r, axis=1); best_existing = np.max(fit[:-1]) if len(bins)>1 else -1; return np.where(fit < 0.05, -1
def _f0015(item, bins, capacity):
    """Penalise bins whose post-placement min-residual is tiny, but only when some existing bin has min-residual > 0.10."""
    r = (bins - item) / capacity
    fit = np.min(r, axis=1)
    if bins.shape[0] > 1:
        best_existing = np.max(fit[:-1])
    else:
        best_existing = -1.0
    gate = 1.0 if best_existing > 0.1 else 0.0
    return np.where(fit < 0.05, -1.0, 0.0) * gate


# f0029 post_placement_imbalance_gate (deep, 1 value): r = (bins - item)/capacity; lo = np.minimum(r[:,0], r[:,1]); hi = np.maximum(r[:,0], r[:,1]); return np.where(lo < 0.15, hi - lo, 0.0) # onl
def _f0029(item, bins, capacity):
    """Post-placement imbalance, gated to bins that become tight in one resource."""
    r = (bins - item) / capacity
    lo = np.minimum(r[:, 0], r[:, 1])
    hi = np.maximum(r[:, 0], r[:, 1])
    return np.where(lo < 0.15, hi - lo, 0.0)


# f0025 per_resource_squared_fullness_gap (wide, 1 value): Fullness match measured per-resource: negative sum of squared per-resource residual gaps, sharpened by a match gate.
def _f0025(item, bins, capacity):
    """Fullness match measured per-resource: negative sum of squared per-resource residual gaps, sharpened by a match gate."""
    jc = item[0] / capacity[0]
    jm = item[1] / capacity[1]
    rc = bins[:, 0] / capacity[0]
    rm = bins[:, 1] / capacity[1]
    dc = rc - jc
    dm = rm - jm
    sq = dc * dc + dm * dm
    post_min = np.minimum(dc, dm)
    gate = np.exp(-np.maximum(-post_min, 0.0) / (jc + jm + 1e-09))
    return gate * -sq + (1.0 - gate) * -sq


# f0034 fullness_match_directional_gate (wide, 1 value): Fullness match with a directional term: reward bins where the job's larger resource demand lands in the bin's larger free resource.
def _f0034(item, bins, capacity):
    """Fullness match with a directional term: reward bins where the job's larger resource demand lands in the bin's larger free resource."""
    jc = item[0] / capacity[0]
    jm = item[1] / capacity[1]
    rc = bins[:, 0] / capacity[0]
    rm = bins[:, 1] / capacity[1]
    s = jc + jm
    rem = rc + rm
    match = -np.abs(rem - s)
    j_diff = jc - jm
    r_diff = rc - rm
    directional = j_diff * r_diff
    gate = np.exp(-np.abs(rem - s) / (s + 1e-09))
    return match + 0.5 * gate * directional


# f0036 dominant_resource_alignment (wide, 1 value): Fraction of the job's demand that would be 'wasted' by pairing its dominant resource with the bin's dominant slack, weighted by how tight th
def _f0036(item, bins, capacity):
    """Fraction of the job's demand that would be 'wasted' by pairing its dominant resource with the bin's dominant slack, weighted by how tight the bin's other side is."""
    jc = item[0] / capacity[0]
    jm = item[1] / capacity[1]
    rc = bins[:, 0] / capacity[0]
    rm = bins[:, 1] / capacity[1]
    job_cpu = jc >= jm
    bin_cpu = rc >= rm
    same = np.where(job_cpu, np.where(bin_cpu, 1.0, 0.0), np.where(bin_cpu, 0.0, 1.0))
    post_c = np.clip(rc - jc, 0.0, None)
    post_m = np.clip(rm - jm, 0.0, None)
    dominant_slack = np.where(bin_cpu, post_c, post_m)
    total_rem = rc + rm + 1e-09
    concentration = np.abs(rc - rm) / total_rem
    align = 2.0 * same - 1.0
    return align * concentration * (1.0 - dominant_slack) + 0.25 * (1.0 - concentration)

_TERMS = [(_f0008, np.array([6.44785973694158])), (_f0016, np.array([1.6103813107800586])), (_f0010, np.array([2.3222571311934037])), (_f0015, np.array([-0.3343997717915806])), (_f0029, np.array([-11.902061123212127])), (_f0025, np.array([-0.04715677503334971])), (_f0034, np.array([0.5607615077107023])), (_f0036, np.array([4.54109464805786]))]


def priority(item, bins, capacity):
    for a in (item, bins, capacity):
        a.setflags(write=False)                    # features may read the inputs, never change them
    k = len(bins)
    total = np.zeros(k)
    for f, w in _TERMS:
        if not w.any():
            continue
        v = np.asarray(f(item, bins, capacity), dtype=float)
        if v.ndim == 1:
            v = v[:, None]
        if v.shape[0] != k:
            v = np.broadcast_to(v.reshape(1, -1)[:, :len(w)], (k, len(w)))
        total += v @ w
    if not np.isfinite(total).all():
        total = np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3)
    # Bins that differ only by floating-point noise count as tied, so the oldest wins whatever the scale.
    return np.round(total, 9)
