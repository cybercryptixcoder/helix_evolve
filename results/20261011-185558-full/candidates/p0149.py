import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Residual after placing the item, normalised.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tight fit in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Compactness: prefer residual close to zero (snug 2D best-fit).
    dist = -np.sqrt(Lc * Lc + Lm * Lm)

    # Balance of residual across resources.
    bal = -np.abs(Lc - Lm)

    # "Productive" residual: both dimensions big enough to host a typical job.
    weak = np.minimum(Lc, Lm)
    strong = np.maximum(Lc, Lm)
    # A residual is productive if weak >= ~0.3 cap AND strong >= ~0.3 cap.
    productive = np.minimum(weak / 0.30, 1.0) * np.minimum(strong / 0.30, 1.0)

    # Sliver penalty: if one dim is tiny, the bin is nearly useless for the future.
    sliver = np.minimum(weak / 0.10, 1.0)

    # Skew complementarity: CPU-heavy jobs like memory-rich bins and vice versa.
    skew = np.clip(it[0] / cap[0] - it[1] / cap[1], -1.0, 1.0)
    comp = skew * (Lm - Lc)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.10 + 0.30 * used) * fit
             + 0.85 * dist
             + 0.75 * bal
             + 0.45 * productive
             + 0.30 * sliver
             + 0.18 * comp)

    # Penalise opening a fresh bin; weaker penalty for big jobs.
    score[-1] -= 0.18 - 0.14 * used

    return score
