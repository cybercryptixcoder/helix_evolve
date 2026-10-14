# p0112 | score -6.2121 | generation 14 | wide branch
# Helix feature policy | p0112, generation 14, 9 features
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math



# f0008 small_job_slack_gain (deep, 1 value): For each bin: before = min(bins[:,0],bins[:,1])/capacity[0]; after = min((bins-item)[:,0],(bins-item)[:,1])/capacity[0] (clip at 0); item_mi
def _f0008(item, bins, capacity):
    """Fraction of the job's tighter-axis demand that closes the bin's tighter-axis slack."""
    cap = float(capacity[0])
    before = np.minimum(bins[:, 0], bins[:, 1]) / cap
    rem = bins - item
    after = np.minimum(np.maximum(rem[:, 0], 0), np.maximum(rem[:, 1], 0)) / cap
    item_min = min(item[0], item[1]) / cap
    return (before - after) / (item_min + 1e-06)


# f0024 bimodal_small_stack_slack (deep, 1 value): item_small = (max(item)/capacity[0] <= 0.2); after = clip(bins - item, 0, None)/capacity; return item_small * (1 - abs(after[:,0] - after[:,
def _f0024(item, bins, capacity):
    """For small jobs only: high when the placement leaves the bin balanced and nearly full."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    item_small = 1.0 if np.max(it) / cap[0] <= 0.2 else 0.0
    after = np.clip(b - it, 0.0, None) / cap
    balance = 1.0 - np.abs(after[:, 0] - after[:, 1])
    fullness = 1.0 - np.minimum(after[:, 0], after[:, 1])
    return item_small * balance * fullness


# f0031 stranded_avoidance_ratio (deep, 1 value): after = clip(bins - item, 0, None)/capacity; tight = minimum(after[:,0], after[:,1]); loose = maximum(after[:,0], after[:,1]); return -(loos
def _f0031(item, bins, capacity):
    """Penalise bins that would become stranded: one axis below 5% while the other stays above 25%."""
    after = np.clip(bins - item, 0, None) / capacity
    tight = np.minimum(after[:, 0], after[:, 1])
    loose = np.maximum(after[:, 0], after[:, 1])
    return -(loose - tight) * (tight < 0.05) * (loose > 0.25)


# f0032 bimodal_big_then_small_reserve (deep, 1 value): item_big = (min(item)/capacity[0] >= 0.3); after = clip(bins - item, 0, None)/capacity; return item_big * (1 - max(after[:,0], after[:,1])) 
def _f0032(item, bins, capacity):
    """For big jobs, reward bins that after placement are both tight and balanced."""
    item_big = min(item[0], item[1]) / capacity[0] >= 0.3
    after = np.clip(bins - item, 0, None) / capacity
    tight = 1.0 - np.maximum(after[:, 0], after[:, 1])
    balanced = 1.0 - np.abs(after[:, 0] - after[:, 1])
    return item_big * tight * balanced


# f0046 tight_axis_second_fit (deep, 1 value): after = clip(bins - item, 0, None)/capacity; item_t = min(item)/capacity[0]; item_l = max(item)/capacity[0]; bin_t = min(bins[:,0],bins[:,1]
def _f0046(item, bins, capacity):
    """Two-axis fit quality: min of tight/loose demand-to-slack ratios, scaled by post-placement tight slack."""
    after = np.clip(bins - item, 0, None) / capacity
    item_t = min(item) / capacity[0]
    item_l = max(item) / capacity[0]
    bin_t = np.minimum(bins[:, 0], bins[:, 1]) / capacity[0]
    bin_l = np.maximum(bins[:, 0], bins[:, 1]) / capacity[0]
    return np.minimum(item_t / (bin_t + 1e-06), item_l / (bin_l + 1e-06)) * (1 - np.minimum(after[:, 0], after[:, 1]))


# f0053 tight_axis_after_fit_count (deep, 1 value): after = clip(bins - item, 0, None)/capacity[0]; item_t = min(item)/capacity[0]; tight = minimum(after[:,0], after[:,1]); frac = tight/(item_
def _f0053(item, bins, capacity):
    """Negative distance of tight-axis residual to an integer multiple of the job's tight dimension."""
    after = np.clip(bins - item, 0, None) / capacity[0]
    item_t = min(item) / capacity[0]
    tight = np.minimum(after[:, 0], after[:, 1])
    frac = tight / (item_t + 1e-06)
    val = -np.abs(frac - np.round(frac)) / (1.0 + tight)
    return np.where(item_t > 0, val, 0.0)


# f0101 large_axis_saturation_gap (deep, 1 value): after = clip(bins - item, 0, None)/capacity; item_t = min(item)/capacity[0]; item_l = max(item)/capacity[0]; room_t = minimum(after[:,0], af
def _f0101(item, bins, capacity):
    """Loose-axis room beyond a tight-sized job, only when the tight axis can no longer take one."""
    after = np.clip(bins - item, 0, None) / capacity
    item_t = min(item) / capacity[0]
    room_t = np.minimum(after[:, 0], after[:, 1])
    room_l = np.maximum(after[:, 0], after[:, 1])
    return (room_l - item_t) * (room_t < item_t)


# f0107 lopsided_strand_penalty (wide, 1 value): For jobs that are lopsided (one axis much bigger), penalise bins that leave the small axis stranded while the big axis stays roomy; scale by
def _f0107(item, bins, capacity):
    """For jobs that are lopsided (one axis much bigger), penalise bins that leave the small axis stranded while the big axis stays roomy; scale by how stranded."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    item_t = np.minimum(it[0], it[1]) / cap[0]
    item_l = np.maximum(it[0], it[1]) / cap[0]
    lopsided = (item_l - item_t) / (item_l + 1e-06)
    after = np.clip(b - it, 0.0, None) / cap
    tight = np.minimum(after[:, 0], after[:, 1])
    loose = np.maximum(after[:, 0], after[:, 1])
    strand = np.clip(1.0 - tight / (item_t + 1e-06), 0.0, 1.0) * (tight < item_t)
    roomy = np.clip((loose - item_l) / (item_l + 1e-06), 0.0, 1.0)
    return -lopsided * strand * roomy


# f0112 large_item_bin_axis_fit_ratio (deep, 1 value): after = clip(bins - item, 0, None)/capacity; item_t = min(item)/capacity[0]; item_l = max(item)/capacity[0]; item_big = (item_t >= 0.3); bef
def _f0112(item, bins, capacity):
    """For large items: ratio of item's large axis to bin's large-axis room, scaled by remaining tight-axis room."""
    after = np.clip(bins - item, 0, None) / capacity
    item_t = min(item) / capacity[0]
    item_l = max(item) / capacity[0]
    item_big = item_t >= 0.3
    before = bins / capacity
    bin_l = np.maximum(before[:, 0], before[:, 1])
    ratio = np.clip(item_l / (bin_l + 1e-06), 0, 2)
    return item_big * ratio * (1 - np.minimum(after[:, 0], after[:, 1]))

_TERMS = [(_f0008, np.array([-0.6713766491359417])), (_f0024, np.array([4.405559270518047])), (_f0031, np.array([18.068572213234294])), (_f0032, np.array([0.5513681515659591])), (_f0046, np.array([8.87839759390958])), (_f0053, np.array([4.223347288454902])), (_f0101, np.array([-22.36737365624814])), (_f0107, np.array([29.600484195569067])), (_f0112, np.array([-1.5231352693285196]))]


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
