# p0036 | score -6.7745 | generation 5 | deep branch
# Helix feature policy | p0036, generation 5, 4 features
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math



# f0013 class_match_residual (deep, 1 value): r = (bins - item)/capacity (post-placement residual). Define item class per resource: big = item/capacity > 0.4. For each bin, let m = min(r
def _f0013(item, bins, capacity):
    """Negative penalty for bins that would become stranded (one residual <5%, other >25%) after placing item."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    r = (bins - it) / cap
    m = np.minimum(r[:, 0], r[:, 1])
    M = np.maximum(r[:, 0], r[:, 1])
    cond = (m < 0.05) & (M > 0.25)
    return -(M - m) * cond


# f0031 closing_bin_penalty (deep, 1 value): r = (bins - item)/capacity. tight = min(r[:,0], r[:,1]); loose = max(r[:,0], r[:,1]). Return -(tight + loose)/2 for open bins (last row excl
def _f0031(item, bins, capacity):
    """Negative mean post-placement residual (tight+loose)/2 per bin."""
    r = (bins - item) / capacity
    tight = np.minimum(r[:, 0], r[:, 1])
    loose = np.maximum(r[:, 0], r[:, 1])
    return -(tight + loose) / 2.0


# f0040 big_with_big_room_penalty (deep, 1 value): Active only when max(item)/capacity > 0.4. r = (bins - item)/capacity (post-placement, clipped at 0). Return min(r[:,0], r[:,1]) - max(r[:,0
def _f0040(item, bins, capacity):
    """Active for large jobs: signed residual difference when both resources keep >20% room."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    r = np.clip((bins - it) / cap, 0.0, None)
    r0 = r[:, 0]
    r1 = r[:, 1]
    mn = np.minimum(r0, r1)
    diff = r0 - r1
    s = np.sign(it[0] - it[1])
    active = np.max(it) / cap.max() > 0.4
    gate = (mn > 0.2).astype(float)
    val = diff * s * gate
    if not active:
        val = np.zeros_like(val)
    return val


# f0037 bimodal_small_slot_for_large (deep, 1 value): Active only when max(item)/capacity > 0.4. r = (bins - item)/capacity. tight = min(r[:,0], r[:,1]). Return -tight * (tight > 0.2) + tight * 
def _f0037(item, bins, capacity):
    """Active for large items: reward tight post-placement residual that is very small (bin closes) or very large (room for another large), penalise the middle band."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    r = (bins.astype(float) - it) / cap
    tight = np.minimum(r[:, 0], r[:, 1])
    active = np.max(it / cap) > 0.4
    val = -tight * (tight > 0.2) + tight * (tight <= 0.2)
    return (val * active).astype(float)

_TERMS = [(_f0013, np.array([6.388764217367649])), (_f0031, np.array([2.8527911373843766])), (_f0040, np.array([4.001995366633523])), (_f0037, np.array([-2.6171835726256907]))]


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
