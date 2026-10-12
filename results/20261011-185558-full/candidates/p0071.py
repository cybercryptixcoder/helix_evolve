import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    cap_c = max(cap[0], 1.0); cap_m = max(cap[1], 1.0)
    c = float(item[0]); m = float(item[1])
    rc = np.maximum(bins[:,0].astype(np.float64), 0.0)
    rm = np.maximum(bins[:,1].astype(np.float64), 0.0)

    # post-placement normalized leftover
    Lc = np.clip(rc - c, 0.0, None) / cap_c
    Lm = np.clip(rm - m, 0.0, None) / cap_m

    # 1) bottleneck fill: item occupies a large share of the scarcer dim
    fc = np.minimum(c / np.maximum(rc, 1.0), 1.0)
    fm = np.minimum(m / np.maximum(rm, 1.0), 1.0)
    bott = np.sqrt(fc * fm)        # geometric: both dims must be consumed

    # 2) balance of post-placement leftover
    bal = -np.abs(Lc - Lm)

    # 3) generic-job acceptance (prob a random U(0,cap/2) job fits)
    accept = np.minimum(2.0*Lc, 1.0) * np.minimum(2.0*Lm, 1.0)

    # 4) tightness on the worst leftover
    tight = -np.maximum(Lc, Lm)

    score = 1.1*bott + 0.9*bal + 0.35*accept + 0.3*tight

    # adaptive new-bin penalty: opening a fresh bin is wasteful mainly for small jobs
    used = (c/cap_c + m/cap_m) * 0.5   # in [0,1]
    score[-1] -= 0.12 * (1.0 - used)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
