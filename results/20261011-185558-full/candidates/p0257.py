import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Core: minimise the worst leftover resource (best-fit in the tight dim).
    worst = np.maximum(Lc, Lm)

    # Small area tiebreak: prefer the less-empty bin overall.
    area = np.sqrt(Lc * Lm)

    # Tightness of the binding resource: how close the item comes to filling it.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Complementarity: match a skewed job to a bin skewed the other way.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    comp = np.clip(d0 - d1, -1.0, 1.0) * (Lm - Lc)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (-1.30 * worst
             - 0.35 * area
             + 0.45 * fit
             + 0.30 * comp)

    # New-bin penalty, weaker for large jobs (they rarely fit well anywhere).
    score[-1] -= 0.20 - 0.15 * used

    return score
