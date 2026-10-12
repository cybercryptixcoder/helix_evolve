import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    c0 = max(cap[0], 1e-9)
    c1 = max(cap[1], 1e-9)
    ic, im = it[0], it[1]

    rc = np.maximum(rem[:, 0], 0.0)
    rm = np.maximum(rem[:, 1], 0.0)

    # feasible = the item fits
    feas = (rc >= ic) & (rm >= im)

    # avoid division by zero
    rcs = np.maximum(rc, 1e-9)
    rms = np.maximum(rm, 1e-9)

    # relative leftover after placement
    kc = (rc - ic) / c0
    km = (rm - im) / c1

    # tightness: how full the binding dimension becomes (1 = perfectly tight)
    tight = np.minimum(ic / rcs, im / rms)

    # alignment between item skew and bin surplus skew
    si = ic / c0 - im / c1
    sr = rc / c0 - rm / c1
    comp = si * sr

    # residual imbalance of the leftover
    imb = np.abs(kc - km)

    # spare room (prefer larger remaining among equal tightness)
    spare = (rc / c0 + rm / c1) * 0.5

    score = (1.00 * tight
             + 0.20 * comp
             - 0.08 * imb
             + 0.02 * spare)

    # infeasible bins must never beat feasible ones
    score = np.where(feas, score, -1.0e9)

    return score
