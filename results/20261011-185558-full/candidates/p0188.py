import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Which resource is binding for this item in this bin?
    fc = it[0] / rc
    fm = it[1] / rm
    fit = np.minimum(np.minimum(fc, fm), 1.0)

    # Stranded slack: leftover on the non-binding side (pure waste).
    stranded = np.abs(Lc - Lm)

    # Prefer the leftover on the binding side to be small, and on the
    # non-binding side to be either large (reusable) or ~0.
    weak = np.minimum(Lc, Lm)
    strong = np.maximum(Lc, Lm)
    reuse = np.minimum(2.0 * weak, 1.0) * np.minimum(2.0 * strong, 1.0)

    # Balance term: reward near-equal leftover, mild.
    bal = -stranded

    # Geom: small leftover area.
    geom = -np.sqrt(Lc * Lm)

    # Compatibility: CPU-heavy item into memory-rich bin and vice versa.
    comp = np.clip(it[0] / cap[0] - it[1] / cap[1], -1.0, 1.0) * (Lm - Lc)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.10 + 0.30 * used) * fit
             + 0.70 * bal
             + 0.55 * geom
             + 0.40 * reuse
             + 0.12 * comp
             - 0.25 * stranded * (1.0 - fit))

    score[-1] -= 0.18 - 0.14 * used

    return score
