# Helix feature policy | trial of f0073 bimodal_large_pair_residual
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


# f0005 balanced_fill_ratio (wide, 1 value): Fraction of each bin's free CPU/mem that this job would consume, penalised by the imbalance between the two.
def _f0005(item, bins, capacity):
    """Fraction of each bin's free CPU/mem that this job would consume, penalised by the imbalance between the two."""
    cap = capacity.astype(float)
    d = item / cap
    r = np.maximum(bins / cap, 1e-09)
    u = np.minimum(d / r, 1.0)
    uc, um = (u[:, 0], u[:, 1])
    spread = np.abs(uc - um)
    return (np.minimum(uc, um) - spread) * 0.5 + 0.5 * np.minimum(uc, um)


# f0058 age_discounted_tight_fill (wide, 1 value): Age-aware best-fit: how full the bin becomes, weighted down for older (earlier) bins, so a good fit in a young bin beats an equal fit in an 
def _f0058(item, bins, capacity):
    """Age-aware best-fit: how full the bin becomes, weighted down for older (earlier) bins, so a good fit in a young bin beats an equal fit in an old one."""
    cap = capacity.astype(float)
    d = item / cap
    L = (bins - item) / cap
    Lc, Lm = (L[:, 0], L[:, 1])
    mn = np.minimum(Lc, Lm)
    k = len(bins)
    age = np.arange(k, dtype=float) / max(k - 1, 1)
    fill = 1.0 - np.clip(mn, 0.0, 1.0)
    return fill * (0.25 + 0.75 * age)


# f0073 bimodal_large_pair_residual (deep, 1 value): Conditional on item being large (item[0]>=0.4*cap[0] or item[1]>=0.4*cap[1]). Let r = bins - item, s = 0.15*capacity. Return per bin: indica
def _f0073(item, bins, capacity):
    """For large items: 1 if the residual after placing still fits a typical small job, scaled by remaining room."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    r = bins - it
    s = 0.15 * cap
    large = it[0] >= 0.4 * cap[0] or it[1] >= 0.4 * cap[1]
    if not large:
        return np.zeros(bins.shape[0])
    fits = (r[:, 0] >= s[0]) & (r[:, 1] >= s[1])
    room = np.minimum(r[:, 0] / cap[0], r[:, 1] / cap[1])
    room = np.clip(room, 0.0, 1.0)
    return fits.astype(float) * (1.0 - room)

_TERMS = [(_f0001, np.array([-3.420533090900932, 6.107922014990574, 7.841740313317702, -17.97951060547126, -58.476587047169325, -2.8353542213654124, -16.05830578300361, -6.159280926175289, -4.646013585004563, 34.302415332514556, -8.22766489348096, 16.049215548246146, 0.8219013889464095, -0.9805045734225906, 78.02009752570294, 12.07118283622632, 1.0843656980899972, 6.365063820712797])), (_f0005, np.array([1.5414495098742318])), (_f0058, np.array([1.6946272437869343])), (_f0073, np.array([-0.03348113221026776]))]


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
