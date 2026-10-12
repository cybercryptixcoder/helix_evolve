import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Post-placement slack, normalised.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Binding-dimension best fit: how tightly the item fills its tighter side.
    fill = np.minimum(it[0] / rc, it[1] / rm)
    fit = np.minimum(fill, 1.0)

    # Residual shape: a bin is useless if one slack is tiny and the other large;
    # punish the imbalance in absolute terms (this is the "wasted bin" signal).
    imbalance = np.abs(Lc - Lm)

    # Complementarity: an item heavy in cpu should leave memory slack free,
    # and vice versa -- so residual should oppose the item's own skew.
    d = it[0] / cap[0] - it[1] / cap[1]
    comp = np.clip(d, -1.0, 1.0) * (Lm - Lc)

    # Keep some usable room in the weaker resource for future arrivals.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    score = (1.15 * fit
             - 0.85 * imbalance
             + 0.55 * comp
             + 0.30 * usable)

    # Fresh-bin penalty, relaxed for large items (they rarely fit elsewhere).
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.18 - 0.13 * used

    return np.asarray(score, dtype=float)
