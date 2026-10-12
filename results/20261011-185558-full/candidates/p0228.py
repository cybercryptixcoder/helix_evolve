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

    # Fill: how tightly the item packs against the binding resource.
    fill = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Waste: total normalised leftover area (smaller is better -> negate).
    waste = -(Lc + Lm)

    # Evenness: penalise lopsided leftovers.
    even = -np.abs(Lc - Lm)

    # Stranded complement: reward when the larger leftover is small relative
    # to the smaller one (both resources nearly used up together).
    big = np.maximum(Lc, Lm)
    small = np.minimum(Lc, Lm)
    strand = -(big - small) * (1.0 - small)

    # Room to grow: keep a modest minimum in the weaker resource.
    room = np.minimum(2.0 * small, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.15 * fill + 0.65 * waste + 0.85 * even
             + 0.45 * strand + 0.30 * room)

    # New-bin penalty, weaker for large jobs.
    score[-1] -= 0.18 - 0.14 * used

    return score
