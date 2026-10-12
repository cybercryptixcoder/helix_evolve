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

    # Per-resource demand fraction of the arriving job.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # Tightness of the fit in the binding dimension (prefer near-full bins).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Residual usefulness: a leftover only counts if it can host another
    # job roughly the size of the current one. Geometric-style discounting
    # in each dimension, then combined multiplicatively so an empty
    # dimension kills the value.
    u = (Lc / (Lc + d0 + 1e-9)) * (Lm / (Lm + d1 + 1e-9))

    # Complementarity: leftover shape should mirror item skew, so a
    # CPU-heavy job prefers a bin left with lots of memory and vice versa.
    skew = d0 - d1
    comp = skew * (Lm - Lc)

    # Reward keeping both leftovers reasonably balanced (avoid a bin that
    # is rich in one resource and starved in the other).
    bal = -np.abs(Lc - Lm)

    # Fresh-bin discouragement, weaker for large jobs (which rarely fit).
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.30 * fit
             + 1.10 * u
             + 0.55 * comp
             + 0.30 * bal)

    score[-1] -= 0.20 - 0.14 * used

    return score
