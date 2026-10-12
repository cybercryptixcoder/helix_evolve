# Helix feature policy | trial of f0039 bimodal_same_axis_large_pairing
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

_TERMS = [(_f0008, np.array([0.04153939340274549])), (_f0010, np.array([-0.025090829967148162])), (_f0021, np.array([0.0748807826648194])), (_f0030, np.array([-0.020718103809020443]))]


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
