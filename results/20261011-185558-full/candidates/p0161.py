import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    cap = np.maximum(cap, 1.0)
    it = np.asarray(item, dtype=float)

    rem = np.asarray(bins, dtype=float)
    # after placement residual (should be >= 0 for feasible bins)
    resid = np.maximum(rem - it[None, :], 0.0)
    L = resid / cap[None, :]   # normalized leftover in [0,1]

    Lc = L[:, 0]
    Lm = L[:, 1]

    # fit quality: prefer small leftover in the tight dimension and small total
    mx = np.maximum(Lc, Lm)
    sm = Lc + Lm
    mn = np.minimum(Lc, Lm)

    score = -(0.6 * mx + 0.4 * sm) + 0.15 * mn
    ...
