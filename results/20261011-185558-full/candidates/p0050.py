import numpy as np

def priority(item, bins, capacity):
    """
    Score open bins for an arriving 2D job.
    Balances three concerns:
      * L-infinity best fit: minimise the worst leftover dimension
        (keeps bins from becoming unusable while still filling them),
      * L1 compactness: minimise total leftover (fewer, fuller bins),
      * leftover balance: keep the two remaining resources similar
        (less fragmentation, fewer dead dimensions later).
    A brand-new bin is extra-penalised, more so for small items.
    """
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # post-placement leftover fractions (>=0 for every row that fits)
    lc = np.maximum(rem[:, 0] - it[0], 0.0) / cap[0]
    lm = np.maximum(rem[:, 1] - it[1], 0.0) / cap[1]

    worst = np.maximum(lc, lm)          # L-infinity leftover
    total = lc + lm                     # L1 leftover
    imbalance = np.abs(lc - lm)         # shape skew

    score = -0.50 * worst - 0.30 * total - 0.20 * imbalance

    # adaptive penalty for opening the (always last) fresh bin
    need_c = it[0] / cap[0]
    need_m = it[1] / cap[1]
    new_pen = 0.05 * (1.0 - 0.5 * (need_c + need_m))   # bigger for small jobs

    is_new = np.zeros(rem.shape[0], dtype=float)
    is_new[-1] = 1.0
    score = score - is_new * new_pen

    return score
