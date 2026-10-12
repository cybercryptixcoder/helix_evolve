# p0080 | score -6.9861 | generation 10 | deep branch
# Helix feature policy | p0080, generation 10, 7 features
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math



# f0008 tight_fit_small_jobs (deep, 1 value): For each bin, the tightness of fit for the arriving item relative to the bin's remaining space: (item[0]/max(bins[:,0],1) + item[1]/max(bins
def _f0008(item, bins, capacity):
    """Tightness of fit of a small item relative to each bin's remaining space."""
    small = item[0] < 0.2 * capacity[0] and item[1] < 0.2 * capacity[1]
    if not small:
        return np.zeros(bins.shape[0])
    rem = np.maximum(bins, 1)
    tight = 0.5 * (item[0] / rem[:, 0] + item[1] / rem[:, 1])
    return tight


# f0010 tight_fit_small_jobs_scarce_gated (wide, 1 value): Tightness of fit for small jobs, measured on the scarcer resource only and gated on a nearly-full bin.
def _f0010(item, bins, capacity):
    """Tightness of fit for small jobs, measured on the scarcer resource only and gated on a nearly-full bin."""
    small = item[0] < 0.2 * capacity[0] and item[1] < 0.2 * capacity[1]
    if not small:
        return np.zeros(bins.shape[0])
    cap = np.maximum(capacity, 1)
    rem = np.maximum(bins, 1)
    rem_frac = np.clip(bins / cap, 0.0, 1.0)
    item_frac = np.clip(item / cap, 0.0, 1.0)
    slack_after = rem_frac - item_frac[None, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        weight = 1.0 / np.maximum(rem_frac, 1e-06)
    weight = weight / np.maximum(weight.sum(axis=1, keepdims=True), 1e-06)
    tight = np.sum(weight * (item_frac[None, :] / rem_frac), axis=1)
    fullness = 1.0 - np.min(slack_after, axis=1)
    gate = np.clip((fullness - 0.5) / 0.5, 0.0, 1.0)
    return gate * tight


# f0021 same_resource_pairing (deep, 1 value): For each bin, residual r = bins - item (clip at 0). Let hi = argmax(item/capacity). Feature = (r[hi] / capacity[hi]) - (r[1-hi] / capacity[1
def _f0021(item, bins, capacity):
    """Residual imbalance in the item's heavy resource: positive when the bin still has room for another same-heavy-class job."""
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    r = np.clip(bins - it, 0.0, None)
    hi = int(np.argmax(it / np.maximum(cap, 1.0)))
    lo = 1 - hi
    val = r[:, hi] / max(cap[hi], 1.0) - r[:, lo] / max(cap[lo], 1.0)
    gate = 1.0 if it.max() >= 0.4 * cap.max() else 0.0
    return gate * val


# f0030 two_large_same_resource_fit (deep, 1 value): Active only when max(item/capacity) >= 0.4. r = bins - item (clip at 0). hi = argmax(item/capacity). Feature = min(r[hi]/capacity[hi], 1.0) 
def _f0030(item, bins, capacity):
    """Reward bins whose residual in the item's heavy resource can still fit another job as heavy as this one."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    frac = it / np.maximum(cap, 1.0)
    hi = int(np.argmax(frac))
    gate = 1.0 if frac[hi] >= 0.4 else 0.0
    r = np.clip(bins - it, 0.0, None)
    residual_frac = r[:, hi] / max(cap[hi], 1.0)
    return gate * np.minimum(residual_frac, 1.0) * frac[hi]


# f0071 avoid_stranding_medium_pair (deep, 1 value): Active only when 0.2 <= max(item/capacity) < 0.4. r = clip(bins - item, 0); a = r[:,0]/capacity[0], b = r[:,1]/capacity[1]. Feature = -( (a 
def _f0071(item, bins, capacity):
    """-1 for bins that placing a medium item would strand (one residual <5%, other >25%), else 0."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    active = (np.max(it / cap) >= 0.2) & (np.max(it / cap) < 0.4)
    r = np.clip(bins - it, 0.0, None)
    a = r[:, 0] / cap[0]
    b = r[:, 1] / cap[1]
    stranded = (a < 0.05) & (b > 0.25) | (b < 0.05) & (a > 0.25)
    return -stranded.astype(float) * active


# f0077 large_pair_same_axis_completion (deep, 1 value): Active only when max(item/capacity) >= 0.4. hi = argmax(item/capacity); lo = 1-hi. r = clip(bins - item, 0). Feature = min(r[:,hi]/(0.4*capa
def _f0077(item, bins, capacity):
    """For large items: room left on the item's heavy axis for a second large job, penalised by room on the light axis."""
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    frac = it / cap
    active = frac.max() >= 0.4
    hi = int(np.argmax(frac))
    lo = 1 - hi
    r = np.clip(bins - it, 0.0, None)
    heavy_room = np.minimum(r[:, hi] / (0.4 * cap[hi]), 1.0)
    light_room = np.minimum(r[:, lo] / (0.4 * cap[lo]), 1.0)
    val = heavy_room * (1.0 - light_room)
    return np.where(active, val, 0.0)


# f0074 tight_fit_small_jobs_tighter_side_gated (wide, 1 value): Tight fit of a small job, but only on the resource where the bin is nearly full: gate on the tighter residual side.
def _f0074(item, bins, capacity):
    """Tight fit of a small job, but only on the resource where the bin is nearly full: gate on the tighter residual side."""
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    small = it[0] < 0.2 * cap[0] and it[1] < 0.2 * cap[1]
    if not small:
        return np.zeros(bins.shape[0])
    rem = np.maximum(bins, 1.0)
    rem_frac = np.clip(bins / cap, 0.0, 1.0)
    item_frac = np.clip(it / cap, 0.0, 1.0)
    slack_after = rem_frac - item_frac[None, :]
    tight_side = np.argmin(slack_after, axis=1)
    rows = np.arange(bins.shape[0])
    tight_resid = slack_after[rows, tight_side]
    tight = item_frac[tight_side] / np.maximum(rem_frac[rows, tight_side], 1e-06)
    other_side = 1 - tight_side
    other_resid = slack_after[rows, other_side]
    gate = np.clip((0.5 - tight_resid) / 0.5, 0.0, 1.0)
    gate *= np.clip((other_resid - 0.05) / 0.45, 0.0, 1.0)
    return gate * tight

_TERMS = [(_f0008, np.array([0.04153939340274549])), (_f0010, np.array([-0.025090829967148162])), (_f0021, np.array([0.0748807826648194])), (_f0030, np.array([-0.020718103809020443])), (_f0071, np.array([0.13819509077574446])), (_f0077, np.array([-0.07595639012122751])), (_f0074, np.array([-0.009193990933211963]))]


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
