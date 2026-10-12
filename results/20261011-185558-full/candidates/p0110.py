import numpy as np


def priority(item, bins, capacity):
    it = np.asarray(item, dtype=np.float64)
    b = np.asarray(bins, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)

    r = b - it                                  # residual after placement
    cap_sum = cap[0] + cap[1]

    # 1) best fit: prefer bins that end up fuller
    fill = 1.0 - (r[:, 0] + r[:, 1]) / cap_sum

    # 2) balance: residual should be squarish, not a long thin sliver
    mx = np.maximum(r[:, 0], r[:, 1])
    mn = np.minimum(r[:, 0], r[:, 1])
    bal = np.where(mx > 0.0, mn / np.maximum(mx, 1e-9), 1.0)

    # 3) size fit: how tightly the item fills the tighter remaining dimension
    rat = np.minimum(it[0] / np.maximum(b[:, 0], 1e-9),
                     it[1] / np.maximum(b[:, 1], 1e-9))

    # 4) complement: item's heavy resource should meet the bin's light residual
    align = ((it[0] / cap[0]) * (r[:, 1] / cap[1]) +
             (it[1] / cap[1]) * (r[:, 0] / cap[0]))

    score = 1.4 * fill + 1.1 * bal + 0.9 * rat + 0.6 * align

    # opening the empty last bin costs more for small items, which fit anywhere
    used_max = float(np.max(it / cap))
    score[-1] -= 0.9 * (1.0 - used_max)

    return score
