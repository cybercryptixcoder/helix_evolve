import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Post-placement normalised leftover per resource.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    waste = np.maximum(Lc, Lm)      # leftover in the dimension that binds
    spread = np.minimum(Lc, Lm)     # leftover slack in the other dimension

    # Tightness of the fit (how nearly the item fills the tighter resource).
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Lower waste is better; penalise leftover in both dimensions, but the
    # binding one more, and reward a snug fit.
    score = -(waste + 0.6 * spread) + 0.25 * fit

    # New-bin penalty: discourage opening a bin only when the job is small
    # enough that existing slack should absorb it.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.22 * (1.0 - used) ** 2

    return score
