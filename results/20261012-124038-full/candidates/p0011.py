# Helix feature policy | trial of f0003 wide_f0003
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math



# f0001 textbook (seed, 18 values): the usual measurements of a candidate bin: leftover_sum: total room left after placing the job (CPU + memory, as fractions); leftover_max: t
def _f0001(item, bins, capacity):
    """The textbook measurements of each candidate bin (18 values per bin, in TEXTBOOK_COLUMNS order)."""
    cap = capacity.astype(float)
    d = item / cap
    r = bins / cap
    L = (bins - item) / cap
    Lc, Lm = (L[:, 0], L[:, 1])
    mx, mn = (np.maximum(Lc, Lm), np.minimum(Lc, Lm))
    skew = d[0] - d[1]
    k = len(bins)
    new = np.zeros(k)
    new[-1] = 1.0
    rn = np.sqrt((r * r).sum(axis=1)) + 1e-09
    dn = math.sqrt(float(d[0] * d[0] + d[1] * d[1])) + 1e-09
    return np.stack([Lc + Lm, mx, mn, np.abs(Lc - Lm), (Lm - Lc) * skew, Lc * Lm, r @ d / (rn * dn), 2.0 - r.sum(axis=1), np.exp(-np.maximum(mn, 0.0) / 0.05), np.exp(-np.maximum(mx, 0.0) / 0.1), new, new * (d[0] + d[1]), new * abs(skew), Lc * Lc + Lm * Lm, abs(skew) * np.abs(Lc - Lm), -np.arange(k) / max(k, 1), np.sqrt(np.maximum(Lc * Lm, 0.0)), np.minimum(d[0] / np.maximum(r[:, 0], 1e-09), d[1] / np.maximum(r[:, 1], 1e-09))], axis=1)


# f0003 wide_f0003 (wide, 1 value): Complementary leftover geometry: the small-resource leftover after the job, and how much of the bin's total *original* room the job consumes
def _f0003(item, bins, capacity):
    """Complementary leftover geometry: the small-resource leftover after the job, and how much of the bin's total *original* room the job consumes, only when the job is lopsided (skewed), else 0."""
    cap = capacity.astype(float)
    d = item / cap
    r = bins / cap
    L = (bins - item) / cap
    Lc, Lm = (L[:, 0], L[:, 1])
    mn = np.minimum(Lc, Lm)
    mx = np.maximum(Lc, Lm)
    skew = d[0] - d[1]
    lop = np.abs(skew)
    heavy_c = skew > 0
    scarce_left = np.where(heavy_c, Lc, Lm)
    scarce_before = np.where(heavy_c, r[:, 0], r[:, 1])
    frac_eaten = d[np.where(heavy_c, 0, 1)] / np.maximum(scarce_before, 1e-09)
    sliver = np.exp(-np.maximum(scarce_left, 0.0) / 0.08)
    other_left = np.where(heavy_c, Lm, Lc)
    room_other = np.minimum(other_left, 1.0)
    return lop * (sliver - room_other) + (1.0 - lop) * (mn - mx) * 0.0
_f0003_name: complement_scarce_sliver_lopsided

_TERMS = [(_f0001, np.array([-4.016611610157923, 7.344125726840032, 6.65385294186683, -17.66868162207442, -64.46162820662535, -2.0443914280021844, -12.928643255802404, -5.841153377501184, -4.979548917113483, 32.477724353734025, -8.16545051701019, 13.503094153334372, 0.9942153356936928, -0.3323880440831117, 79.51567339902533, 12.074753385727597, 0.48933493206430984, 5.291838378678596])), (_f0003, np.array([0.19088091698353973]))]


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
