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

    # Normalised item demand direction.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]

    # Tightness in the binding resource: prefer a bin the item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Geometric fill (small leftover area is good).
    geom = -np.sqrt(Lc * Lm)

    # Balance of the leftover.
    bal = -np.abs(Lc - Lm)

    # NEW: waste penalty. If the item is skewed, putting it in a bin whose
    # rich resource is the opposite axis wastes the rich resource. Penalise
    # leftover that is large on the axis the item barely uses.
    waste = -(np.maximum(dc - dm, 0.0) * Lc + np.maximum(dm - dc, 0.0) * Lm)

    # NEW: complementarity -- reward matching a skewed item to a bin leftover
    # skewed the opposite way (helps anticorr families).
    comp = (dc - dm) * (Lm - Lc)

    # NEW: the minimum leftover across axes, softly capped. This is the
    # "future-proofing" term: a bin with a healthy weak axis can still take
    # more jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Accept: reward both leftovers being reasonably large.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    used = 0.5 * (dc + dm)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.30 * waste
             + 0.25 * comp)

    # Softer, smoother new-bin gate: only mildly discourage the fresh bin,
    # and less so for large jobs (which can rarely fit anyway).
    score[-1] -= 0.17 - 0.13 * used

    return score
