import numpy as np

def priority(item, bins, capacity):
    """
    Combined score: snugness of the fit, balance of the leftovers,
    geometric mean of the leftovers, usable slack, and a mild
    reward for leaving room; the brand-new bin gets a penalty that
    shrinks as the open bins fill up.
    """
    it = np.asarray(item, dtype=float)
    B = np.asarray(bins, dtype=float)
    cap = np.asarray(capacity, dtype=float)
    eps = 1e-9

    itc, itm = it[0], it[1]
    capc, capm = cap[0], cap[1]

    rc = B[:, 0]
    rm = B[:, 1]

    # leftover after placement, scaled by capacity so the terms are comparable
    Lc = np.maximum(rc - itc, 0.0) / capc
    Lm = np.maximum(rm - itm, 0.0) / capm

    # how much of the bin's remaining space the item consumes (want high)
    fit = np.minimum(np.minimum(itc / (rc + eps), itm / (rm + eps)), 1.0)

    # prefer balanced leftovers (small |Lc - Lm|)
    bal = -np.abs(Lc - Lm)

    # prefer small leftover area
    geom = -np.sqrt(Lc * Lm + eps)

    # prefer leaving little slack in the tighter dimension
    usable = -np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    # mild preference for leaving room in both dimensions
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    score = (1.15 * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept)

    # penalty on the new (last) bin, relaxed when the open bins are already full
    if B.shape[0] > 1:
        used = 1.0 - 0.5 * float(
            np.mean(B[:-1, 0] / capc + B[:-1, 1] / capm)
        )
    else:
        used = 0.0
    score[-1] += -(0.16 - 0.12 * used)

    return score
