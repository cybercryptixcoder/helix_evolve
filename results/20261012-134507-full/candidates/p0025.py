# Helix feature policy | trial of f0018 tight_fit_small_jobs_bottleneck
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


# f0018 tight_fit_small_jobs_bottleneck (wide, 1 value): Tightness of fit for small jobs: min-slack (bottleneck) measure, not summed ratios.
def _f0018(item, bins, capacity):
    """Tightness of fit for small jobs: min-slack (bottleneck) measure, not summed ratios."""
    small = item[0] < 0.2 * capacity[0] and item[1] < 0.2 * capacity[1]
    if not small:
        return np.zeros(bins.shape[0])
    cap = np.maximum(capacity, 1).astype(float)
    rem = np.maximum(bins, 1).astype(float)
    rem_frac = np.clip(rem / cap, 0.0, 1.0)
    item_frac = np.clip(item / cap, 0.0, 1.0)
    slack = rem_frac - item_frac[None, :]
    bottleneck = np.min(slack, axis=1)
    tight = 1.0 / (1.0 + 20.0 * np.maximum(bottleneck, 0.0))
    return tight

_TERMS = [(_f0008, np.array([0.5789159193244431])), (_f0010, np.array([-0.4889895504906889])), (_f0018, np.array([0.14499265858824517]))]


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
