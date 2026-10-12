import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the job.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tightness of the fit in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Residual alignment: leftover vector dotted with the "reusable" direction
    # (1,1). A bin whose leftovers are plentiful and balanced scores high.
    align = (Lc + Lm) * 0.5

    # Area well-filled: prefer small leftover product.
    geom = -np.sqrt(Lc * Lm)

    # Imbalance penalty.
    bal = -np.abs(Lc - Lm)

    # Weak-resource floor: keep the scarcer resource from being starved.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Job skew and complementarity bonus.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.abs(d0 - d1)
    comp = np.clip(d0 - d1, -1.0, 1.0) * (Lm - Lc)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.15 * fit
             + 0.55 * geom
             + 0.70 * bal
             + 0.30 * usable
             + 0.35 * align
             + 0.40 * skew * comp)

    # Fresh-bin gate: multiplicative, weak for large jobs (which need space),
    # strong for small jobs (which should tuck into existing bins).
    gate = 1.0 - (0.28 * (1.0 - used) ** 2)
    score = score * gate

    # Still nudge the fresh bin down a touch so it loses ties.
    score[-1] -= 0.02

    return score
