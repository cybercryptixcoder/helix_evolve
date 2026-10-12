import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised residual after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Best-fit: how fully the item fills its binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Waste: the residual is only useful up to its weaker dimension.
    # Reward residual that is *deep* in both resources (usable) and penalise
    # residuals whose weaker dimension is a sliver (dead space).
    weak = np.minimum(Lc, Lm)
    strong = np.maximum(Lc, Lm)
    usable = np.minimum(3.0 * weak, 1.0)
    sliver = np.clip(1.0 - 6.0 * weak, 0.0, 1.0) * strong   # dead-ish residual

    # Complementarity: a cpu-heavy item wants a bin rich in memory and vice
    # versa, so the residual opposes the item's dominant resource.
    d = it[0] / cap[0] - it[1] / cap[1]
    comp = np.clip(d, -1.0, 1.0) * (Lm - Lc)

    # Evenness of the residual (mild preference, not dominant).
    bal = -np.abs(Lc - Lm)

    score = (1.15 * fit
             + 0.50 * usable
             + 0.40 * comp
             + 0.20 * bal
             - 0.55 * sliver)

    # Penalty for opening a new bin: strong when the item fits comfortably
    # somewhere, weak (or even reversed) for big items that need a fresh bin.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.20 - 0.16 * used

    return np.asarray(score, dtype=float)
