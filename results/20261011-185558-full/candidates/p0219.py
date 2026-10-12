import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Binding-resource tightness: how fully the item plugs the tighter side.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Convex residual-area penalty: strongly prefers bins that end up full.
    area = Lc * Lm
    geom = -(Lc + Lm) - 2.0 * np.sqrt(np.maximum(area, 0.0))

    # Imbalance penalty.
    bal = -np.abs(Lc - Lm)

    # Weak-resource preservation (avoid stranding a tiny sliver).
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Item skew in [0,1]: how lopsided the job is between resources.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.abs(d0 - d1)

    # For skewed jobs, reward leftover that mirrors the job's heavy side.
    comp = skew * (d0 - d1) * (Lm - Lc)

    # New-bin penalty scales with how much residual the best open bin keeps.
    best_open = np.max(np.minimum(Lc, Lm)[:-1]) if bins.shape[0] > 1 else 0.0
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.10 + 0.30 * used) * fit
             + 0.55 * geom
             + 0.85 * bal
             + 0.30 * usable
             + 0.35 * comp)

    # Fresh-bin discount: small when an open bin already retains good room.
    score[-1] -= (0.20 - 0.14 * used) * (1.0 - 0.6 * best_open)

    return score
