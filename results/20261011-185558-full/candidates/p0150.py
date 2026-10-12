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

    # Snugness: how tightly the item fills the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Soft distance-to-corner: penalise residual size but reward a
    # *balanced* residual (both dims small together), not just one.
    r2 = Lc * Lc + Lm * Lm
    snug = 1.0 / (1.0 + 3.0 * r2)

    # Directional match: item's skew should line up with leftover skew.
    iskew = it[0] / cap[0] - it[1] / cap[1]
    lskew = Lc - Lm
    align = -np.abs(iskew + lskew)

    # Keep the weaker resource from drying up completely.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.15 + 0.30 * used) * fit + 1.10 * snug + 0.55 * align + 0.30 * usable

    # Fresh-bin penalty: only significant when a snug fit already exists.
    best_fit = float(np.max(fit[:-1])) if rem.shape[0] > 1 else 0.0
    fresh = 0.20 - 0.14 * used - 0.10 * best_fit
    score[-1] -= max(fresh, 0.0)

    return score
