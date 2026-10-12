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

    # Best-fit: how completely the item fills its binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Complementarity: a cpu-heavy job prefers a memory-rich bin and vice versa.
    d = it[0] / cap[0] - it[1] / cap[1]
    comp = np.clip(d, -1.0, 1.0) * (Lm - Lc)

    # Balance of residual: even leftovers are easier to reuse.
    bal = -np.abs(Lc - Lm)

    # Fragmentation: penalise a bin that ends up with a tiny sliver in either
    # resource (hard to ever fill) more than one with a moderate leftover.
    sliver = -np.exp(-6.0 * np.minimum(Lc, Lm))

    # Room: reward residuals that are still at least a moderate fraction of a
    # bin in both resources, so they can host a future job.
    room = np.minimum(Lc, Lm)

    # Waste: total slack created by this placement, in the tighter resource.
    waste = -(Lc + Lm - 2.0 * np.minimum(Lc, Lm))

    score = (1.10 * fit
             + 0.45 * comp
             + 0.55 * bal
             + 0.40 * sliver
             + 0.45 * room
             + 0.25 * waste)

    # New-bin penalty: strong for small/medium jobs, near zero for big ones.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.20 - 0.16 * used

    return np.asarray(score, dtype=float)
