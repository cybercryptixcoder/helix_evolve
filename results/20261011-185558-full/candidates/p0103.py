import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # post-placement residual fractions
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # tightness in the binding dimension (best-fit flavour)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # balance / complementarity of the leftover
    bal = 1.0 - np.abs(Lc - Lm)

    # compactness: prefer small leftover area
    geom = 1.0 - np.sqrt(np.minimum(Lc, 1.0) * np.minimum(Lm, 1.0))

    # keep a usable slack in the weaker dimension
    weaker = np.minimum(Lc, Lm)
    usable = np.minimum(2.5 * weaker, 1.0)

    # both dimensions roomy enough for a mid-size job
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    score = (1.05 * fit
             + 0.95 * bal
             + 0.55 * (2.0 * geom - 1.0)
             + 0.35 * usable
             + 0.25 * accept)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
