import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Smallest "typical" demand in each resource: a leftover below this is dead space.
    # Use a modest fraction of capacity as the granularity threshold.
    tau = 0.08
    dead_c = np.maximum(tau - Lc, 0.0)
    dead_m = np.maximum(tau - Lm, 0.0)
    dead = -(dead_c + dead_m)

    # Shape: prefer a leftover rectangle that still has area but is not lopsided.
    # Reward having usable space in the *weak* dimension strongly.
    weak = np.minimum(Lc, Lm)
    strong = np.maximum(Lc, Lm)
    shape = weak * (1.0 - 0.5 * (strong - weak))

    # Compatibility: leftover should be anti-aligned with the item, so future
    # jobs of the opposite profile can still fit.  Item-heavy in cpu -> want mem leftover.
    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    comp = (im - ic) * (Lc - Lm)

    # Fit still matters mildly: don't waste a bin the item almost exactly fills.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    used = 0.5 * (ic + im)
    used = min(max(used, 0.0), 1.0)

    score = (0.55 * fit + 1.30 * shape + 1.10 * dead + 0.45 * comp)

    # Penalty for opening a new bin: strong for small items, mild for large ones.
    score[-1] -= 0.30 - 0.20 * used

    return score
