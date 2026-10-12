import numpy as np

def priority(item, bins, capacity):
    it = item.astype(float)
    cap = capacity.astype(float)
    rem = bins.astype(float) - it                       # leftover after placing
    rem = np.maximum(rem, 0.0)

    # normalized leftover and demand
    L = rem / cap
    d = it / cap
    Lc, Lm = L[:, 0], L[:, 1]
    dc, dm = d[0], d[1]

    # fit: prefer bins the item packs tightly into (fills the scarcer dimension)
    used = it / np.maximum(bins.astype(float), 1.0)     # fraction of this bin consumed
    fit = np.max(used, axis=1)

    # balance of resulting leftover
    bal = -np.abs(Lc - Lm)

    # complementarity: reward leftover skew opposite to the item's skew,
    # so CPU-heavy jobs leave memory-rich holes for memory-heavy jobs (and vice versa)
    sk_item = dc - dm
    sk_left = Lc - Lm
    comp = -sk_item * sk_left

    # usable: leftover shouldn't be usable only via one resource / nearly empty
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    score = 1.15 * fit + 0.90 * bal + 0.45 * comp + 0.50 * usable

    # discourage opening a brand-new bin unless it really scores better
    is_new = np.zeros(bins.shape[0])
    is_new[-1] = 1.0
    score = score - 0.30 * is_new

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
