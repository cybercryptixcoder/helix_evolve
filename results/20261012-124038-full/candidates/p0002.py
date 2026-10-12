# Helix feature policy | p0002, generation 0, 1 features
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

_TERMS = [(_f0001, np.array([-3.496526212068671, 7.383490918906549, 6.236016567602183, -19.00531147243995, -66.79931450930081, -2.0871128893187616, -13.050128995989745, -5.76083035666383, -4.0451690925289325, 31.79573632122272, -7.796644561888203, 12.212558406014553, 2.357153875057604, -0.15599551160941474, 72.94557994597729, 12.291648603996832, -0.04133102036316559, 6.107846126450929]))]


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
