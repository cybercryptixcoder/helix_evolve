import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # tightness in binding dimension
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # balance of leftover
    bal = -np.abs(Lc - Lm)

    # small total leftover (best fit)
    tot = -(Lc + Lm)

    # geometric
    geom = -np.sqrt(Lc * Lm)

    # usable weak resource
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # accept
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    score = 1.0 * fit + 0.9 * bal + 0.5 * geom + 0.35 * usable + 0.15 * accept + 0.1 * tot

    score = np.asarray(score, dtype=float)
    score = np.nan_to_num(score, nan=0.0, posinf=1e9, neginf=-1e9)
    return np.atleast_1d(score)
