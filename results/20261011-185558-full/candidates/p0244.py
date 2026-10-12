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
    rem = np.maximum(bins - item, 0.0).astype(float)
    Lc = rem[:, 0]
    Lm = rem[:, 1]

    mx = np.maximum(Lc, Lm)
    mn = np.minimum(Lc, Lm)

    cap_sum = float(capacity[0]) + float(capacity[1])
    if cap_sum > 0.0:
        frac = (float(item[0]) + float(item[1])) / cap_sum
    else:
        frac = 0.0
    if frac < 0.0:
        frac = 0.0
    elif frac > 1.0:
        frac = 1.0

    # Large jobs: emphasize the bottleneck resource (min-max rule).
    # Small jobs: emphasize tight overall packing (best-fit / l1 rule).
    w_max = 0.5 + 0.4 * frac
    w_min = 1.0 - w_max

    score = -(w_max * mx + w_min * mn)
    # tiny tie-breaker: among equal shape blends prefer the tighter package
    score = score - 1e-3 * (Lc + Lm)
    return score
