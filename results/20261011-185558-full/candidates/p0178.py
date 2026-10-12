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

    # Tightness of the fit in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Bottleneck waste: the worst leftover resource dominates usefulness.
    # Small max leftover => the bin can't serve many future jobs.
    waste = -np.maximum(Lc, Lm)

    # Balance: even leftovers are more reusable.
    bal = -np.abs(Lc - Lm)

    # Area term, softened: rewards compact packing without over-tightening.
    geom = -np.sqrt(Lc * Lm)

    # Reusability: both resources at least a third of a bin.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(3.0 * weak, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    umax = min(max(it[0] / cap[0], it[1] / cap[1]), 1.0)

    score = ((1.00 + 0.30 * used) * fit
             + 0.85 * bal
             + 0.55 * geom
             + 0.60 * waste
             + 0.35 * usable)

    # New-bin penalty: only meaningful if some old bin accepts the item well.
    # best_fit measures how snugly the item lands in the best existing bin.
    if score.shape[0] > 1:
        best_fit = float(np.max(fit[:-1]))
    else:
        best_fit = 0.0

    # Base reluctance to open a new bin, eased for big or lopsided jobs
    # and eased when no existing bin takes the item snugly.
    penalty = (0.20 - 0.10 * umax) * (0.5 + 0.5 * best_fit)
    score[-1] -= penalty

    return score
