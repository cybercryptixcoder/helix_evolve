import numpy as np

def priority(item, bins, capacity):
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    cap = np.asarray(capacity, dtype=float)
    rem = np.maximum(b - it, 0.0)
    a = rem[:, 0] / cap[0]
    bb = rem[:, 1] / cap[1]
    lo = np.minimum(a, bb)
    hi = np.maximum(a, bb)
    # tightest bin: minimize hi; balance: prefer larger lo
    score = -hi + 0.6 * lo
    return score
