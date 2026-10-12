import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # normalized leftover after placement
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # how tightly the item fits (binding dimension)
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # concentration: a nearly-full resource is GOOD (leaves a big block)
    conc = np.maximum(Lc, Lm)

    # balance of remaining leftovers
    bal = -np.abs(Lc - Lm)

    # waste: geometric mean of leftovers (small = well used bin)
    geom = -np.sqrt(Lc * Lm)

    # size of the item relative to capacity
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(float(used), 0.0), 1.0)

    # fresh-bin penalty: big items justify a new bin, small ones don't
    fresh_pen = 0.20 - 0.14 * used

    score = (1.10 * fit
             + 0.70 * conc
             + 0.85 * bal
             + 0.55 * geom
             + 0.30 * np.minimum(2.0 * np.minimum(Lc, Lm), 1.0))

    score[-1] -= fresh_pen

    return score
