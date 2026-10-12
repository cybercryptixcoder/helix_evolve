# Helix feature policy | trial of f0012 residual_axis_imbalance
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

_TERMS = [(_f0008, np.array([0.04153939340274549]))]


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
