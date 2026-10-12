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

    # Demand skew: +1 CPU-heavy, -1 memory-heavy.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.clip(d0 - d1, -1.0, 1.0)

    # Per-resource "goodness": slack is useful only if it survives future
    # items; scale it so that >= half a bin is fully good.
    gc = np.minimum(2.0 * Lc, 1.0)
    gm = np.minimum(2.0 * Lm, 1.0)

    # Multiplicative core: a bin is only as good as its weaker resource.
    core = np.sqrt(gc * gm)

    # Complementarity: prefer leftover concentrated in the resource the
    # job does NOT stress, so skew-heavy jobs land in opposite-skew bins.
    comp = gc * (0.5 - 0.5 * skew) + gm * (0.5 + 0.5 * skew)

    # Tightness: how completely the item fills the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance of leftover (geometric mean already handles this, but add a
    # gentle nudge against extremely lopsided bins).
    bal = 1.0 - np.abs(Lc - Lm)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.10 + 0.30 * used) * fit
             + 0.85 * core
             + 0.45 * comp
             + 0.25 * bal)

    # Fresh-bin penalty, softer for large jobs (which rarely fit well anyway).
    score[-1] -= 0.18 - 0.14 * used

    return score
