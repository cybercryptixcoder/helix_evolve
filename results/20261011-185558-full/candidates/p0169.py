import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Leftover after placing the item, normalised.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # How tightly the item binds each resource of this bin.
    tight_c = np.minimum(it[0] / rc, 1.0)
    tight_m = np.minimum(it[1] / rm, 1.0)
    # Binding dimension: the one the item stresses most.
    fit = np.maximum(tight_c, tight_m)

    # Residual shape: leftover should be balanced AND both parts usable.
    weak = np.minimum(Lc, Lm)
    strong = np.maximum(Lc, Lm)
    bal = -np.abs(Lc - Lm)
    # Reusable: a bin is worth keeping only if its weaker side stays healthy.
    reusable = np.minimum(2.0 * weak, 1.0) * (1.0 - 0.5 * np.sqrt(Lc * Lm))
    # Symmetry bonus: near-square leftover is easy to fill later.
    sym = 1.0 - np.abs(Lc - Lm) / np.maximum(Lc + Lm, 1e-9)

    # Job size in units of a bin (0..1).
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = float(min(max(used, 0.0), 1.0))

    score = ((0.95 + 0.30 * used) * fit
             + 0.55 * bal
             + 0.70 * reusable
             + 0.25 * sym)

    # Fresh-bin penalty: base cost, softened for big jobs, and additionally
    # forgiven when the best open bin has a poor weak-side leftover.
    best_weak = np.min(Lc[:-1]) if Lc.shape[0] > 1 else 0.0
    forgive = float(min(max(best_weak / 0.25, 0.0), 1.0))
    penalty = (0.18 - 0.14 * used) * (1.0 - 0.5 * forgive)
    score[-1] -= penalty

    return score
