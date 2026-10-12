import numpy as np
import math


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)

    rem = bins.astype(float)
    Lc = rem[:, 0] - it[0]
    Lm = rem[:, 1] - it[1]
    Lc = np.clip(Lc, 0.0, None)
    Lm = np.clip(Lm, 0.0, None)

    # normalise residuals by capacity
    rc = Lc / cap[0]
    rm = Lm / cap[1]

    # tightness of the resulting fit (how full the bin becomes on the tight side)
    fc = np.clip(1.0 - rc, 0.0, 1.0)
    fm = np.clip(1.0 - rm, 0.0, 1.0)
    used = np.maximum(fc, fm)
    bal = 1.0 - np.abs(rc - rm)
    geom = np.sqrt(np.clip(rc, 1e-12, None) * np.clip(rm, 1e-12, None))
    usable = fc * fm
    accept = 1.0 - np.minimum(rc, rm)

    score = ((1.05 + 0.25 * used) * used
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept)

    # novelty penalty on the fresh empty bin; lopsided jobs get more freedom
    umax = min(max(it[0] / cap[0], it[1] / cap[1]), 1.0)
    score = np.asarray(score, dtype=float)
    score[-1] -= 0.16 - 0.12 * umax

    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
