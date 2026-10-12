import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placement.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fit: tightness in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance and geometric tightness.
    bal = -np.abs(Lc - Lm)
    geom = -np.sqrt(Lc * Lm)

    # Usable / accept: keep both leftovers healthy.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # Alignment: dot product of item demand direction and leftover direction.
    # Big when the item is heavy in the axis where the bin is rich -> good match.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]
    align = (dc - dm) * (Lm - Lc)

    # Residual: penalise a bin that still has a large max leftover (loose bin).
    resid = -np.maximum(Lc, Lm)

    # Tightness of the *smaller* leftover scaled by how full the bin was pre-item.
    pre_c = np.clip(rem[:, 0] / cap[0], 0.0, 1.0)
    pre_m = np.clip(rem[:, 1] / cap[1], 0.0, 1.0)
    tight = -np.sqrt((1.0 - pre_c) * (1.0 - pre_m))

    # Adaptive new-bin penalty, milder for large jobs.
    used = 0.5 * (dc + dm)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.85 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.18 * align
             + 0.25 * resid
             + 0.20 * tight)

    score[-1] -= 0.16 - 0.12 * used

    return score
