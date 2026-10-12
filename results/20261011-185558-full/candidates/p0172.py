import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float).reshape(2), 1.0)
    it = np.asarray(item, dtype=float).reshape(2)
    rem = np.asarray(bins, dtype=float)
    if rem.ndim == 1:
        rem = rem.reshape(1, -1)
    rem = rem.reshape(-1, 2)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # remaining fractions after placement
    Lc = np.maximum(rem[:, 0] - it[0], 0.0) / cap[0]
    Lm = np.maximum(rem[:, 1] - it[1], 0.0) / cap[1]

    # 1) binding tightness: item nearly fills the scarcer leftover dimension
    fc = it[0] / rc
    fm = it[1] / rm
    fit = np.minimum(np.minimum(fc, fm), 1.0)

    # 2) post-placement utilization and balance
    u_small = 1.0 - np.maximum(Lc, Lm)
    balance = 1.0 - np.abs(Lc - Lm)

    # 3) squareness of leftover area
    area = 1.0 - Lc * Lm

    # 4) slack in the weaker dimension
    slack = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    score = 1.0 * fit + 0.7 * u_small + 0.7 * balance + 0.5 * area + 0.25 * slack
    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return np.asarray(score, dtype=float).reshape(-1)
