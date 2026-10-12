import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    cap = np.maximum(cap, 1.0)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    n = rem.shape[0]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # post-placement residual, normalized
    Lc = np.maximum(rem[:, 0] - it[0], 0.0) / cap[0]
    Lm = np.maximum(rem[:, 1] - it[1], 0.0) / cap[1]

    # best fit: how full the bin becomes in its tighter dimension
    fill = 1.0 - np.maximum(Lc, Lm)

    # balance of residual
    hi = np.maximum(Lc, Lm)
    lo = np.minimum(Lc, Lm)
    bal = 1.0 - (hi - lo)   # = 1 - |Lc-Lm|

    # normalize residual shape: reward near-square leftover
    # usable residual beyond the average job size
    avgc = 0.28
    avgm = 0.28
    fut = np.minimum(np.minimum(Lc / avgc, Lm / avgm), 1.0)

    # how much of each resource the item consumes relative to what's there
    fc = np.minimum(it[0] / rc, 1.0)
    fm = np.minimum(it[1] / rm, 1.0)
    tight = np.minimum(fc, fm)

    score = 1.1 * fill + 0.7 * bal + 0.5 * fut + 0.4 * tight

    # new-bin penalty adapts: large items cheaper to open
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    pen = 0.14 - 0.10 * used
    score[-1] -= pen

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
