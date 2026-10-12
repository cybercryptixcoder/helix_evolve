import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    qc = it[0] / cap[0]
    qm = it[1] / cap[1]

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # tight fit in binding dimension
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    bal = -np.abs(Lc - Lm)
    geom = -np.sqrt(Lc * Lm)
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # complementarity: item skew vs bin residual skew (relative, bounded)
    sq = np.clip(qc - qm, -1.0, 1.0)
    rc_n = rem[:, 0] / cap[0]
    rm_n = rem[:, 1] / cap[1]
    br = (rm_n - rc_n) / (rm_n + rc_n + 1e-9)
    comp = sq * br

    used = 0.5 * (qc + qm)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.55 * comp
             + 0.30 * np.abs(sq) * comp)  # stronger for skewed items

    score[-1] -= 0.16 - 0.12 * used
    return score
