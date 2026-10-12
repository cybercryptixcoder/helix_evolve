import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item (both >= 0 since bin fits).
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tightness: how much of the bin the item actually consumes in the
    # binding dimension.  Prefer bins the job nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance of the residual: an even leftover is more reusable.
    bal = -np.abs(Lc - Lm)

    # Residual-match: a leftover that itself looks like a plausible job
    # (roughly equal, not too lopsided) is worth keeping intact.  Score
    # the leftover by its harmonic-style "usable square" — maximised when
    # both residual fractions are moderate and equal.
    resid = (2.0 * Lc * Lm) / np.maximum(Lc + Lm, 1e-9)   # harmonic mean
    # Also reward residuals big enough to hold a smallish job of each kind.
    roomy = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    # Adaptive fresh-bin penalty: big jobs deserve a new bin more readily.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.15 * fit + 0.55 * bal + 0.90 * resid + 0.40 * roomy)

    score[-1] -= 0.20 - 0.16 * used

    return score
