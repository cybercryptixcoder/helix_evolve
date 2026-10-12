import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tightness in each resource: how much of the remaining resource the
    # item consumes. Prefer bins where the item is a snug fit.
    tc = np.minimum(it[0] / rc, 1.0)
    tm = np.minimum(it[1] / rm, 1.0)

    # Multiplicative core: a bin must be decent in BOTH resources.
    # Small leftover in either resource is punished.
    core = np.sqrt(tc * tm)

    # Leftover shape: reward leftover that is usable in the weaker resource,
    # and reward evenness so neither resource is stranded.
    weak = np.minimum(Lc, Lm)
    even = 1.0 - np.abs(Lc - Lm)

    # Future utility: geometric mean of leftovers (penalises stranded bins).
    util = np.sqrt((Lc + 1e-6) * (Lm + 1e-6))

    # Skew awareness: job heavier in one resource should land in a bin whose
    # leftover in that heavy resource is comparatively large.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.clip(d0 - d1, -1.0, 1.0)
    match = skew * (Lm - Lc)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.30 * core
             + 0.55 * weak
             + 0.35 * even
             + 0.45 * util
             + 0.35 * abs(skew) * match)

    # Opening a new bin: only attractive when the item is large.
    score[-1] -= 0.20 - 0.15 * used

    return score
