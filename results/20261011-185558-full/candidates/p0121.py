import numpy as np

def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int    demand of the arriving job, [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of every open bin the job fits in,
                                             oldest bin first. The LAST row is always a brand-new
                                             empty bin (equal to capacity).
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    returns:  np.ndarray, shape (k,), float  one finite score per row of bins.
    """
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover in each resource *after* placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fit: how completely the item fills the dimension it stresses most.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance: prefer leftover that is even across the two resources.
    bal = -np.abs(Lc - Lm)

    # Residual area: prefer a well-filled bin (small leftover product).
    geom = -np.sqrt(Lc * Lm)

    # Total residual: best-fit on aggregate leftover room.  This is the new
    # force -- it stops small jobs leaking into loosely-filled bins.
    total = Lc + Lm

    # Usable: keep the scarcer resource from being wiped out.
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    # Accept: reward a bin that still has half capacity in both resources.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    score = (1.05 * fit
             + 0.85 * bal
             + 0.30 * geom
             - 0.20 * total
             + 0.35 * usable
             + 0.15 * accept)

    # Penalty discouraging a fresh bin, weaker for big jobs.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.16 - 0.12 * used

    return score
