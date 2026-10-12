import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tight fit in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Closeness of the residual vector to zero: prefers bins that end up
    # snug and balanced in BOTH resources (compact 2D best-fit).
    dist = -np.sqrt(Lc * Lc + Lm * Lm)

    # Ensure enough room in the weaker resource for the future.
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    # Reward both residuals being >= half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.00 + 0.35 * used) * fit
             + 0.95 * dist
             + 0.40 * usable
             + 0.15 * accept)

    # Penalise opening a fresh bin, less so for big jobs.
    score = score - (0.17 - 0.13 * used) * (np.arange(rem.shape[0]) == rem.shape[0] - 1)

    return score
