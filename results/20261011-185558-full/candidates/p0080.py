import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, float), 1.0)
    it = np.asarray(item, float)
    rem = np.asarray(bins, float)          # k x 2, oldest first, last row = empty bin
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # post-placement leftover, normalized by capacity
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # bottleneck fill: how much of the tighter resource does the item consume
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # balance of the leftover and geometric compactness
    bal = -np.abs(Lc - Lm)
    geom = -np.sqrt(Lc * Lm + 1e-12)

    # room left in the weaker dimension, capped
    weaker = np.minimum(Lc, Lm)
    usable = np.minimum(2.5 * weaker, 1.0)

    # rough chance a generic uniform job still fits afterwards
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    score = 1.15 * fit + 0.9 * bal + 0.5 * geom + 0.35 * usable + 0.15 * accept

    # adaptive new-bin penalty: bigger jobs get a smaller penalty (opening a fresh
    # bin for a big job is cheap), tiny jobs get a larger one so they squeeze in.
    used_frac = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    pen = 0.16 - 0.12 * used_frac

    n = score.shape[0]
    is_new = np.zeros(n, dtype=bool)
    if n > 0:
        is_new[-1] = True
    score = score - pen * is_new

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
