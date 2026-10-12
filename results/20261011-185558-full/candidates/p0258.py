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

    # Demand fractions.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # Complementarity: leftover in the resource the job stresses less.
    # A CPU-heavy job (d0 > d1) should value memory leftover, and vice versa.
    comp = np.where(d0 >= d1, Lm, Lc)

    # Worst-case slack: the smaller of the two post-placement leftovers,
    # but only counted once it exceeds a "useful" threshold, so we don't
    # reward bins with a sliver in one dimension.
    weak = np.minimum(Lc, Lm)
    floor = np.clip(weak / 0.25, 0.0, 1.0)

    # Balance: even leftovers are more versatile.
    bal = -np.abs(Lc - Lm)

    # Fit: prefer bins the item nearly fills (bounded by 1).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Waste penalty: large total leftover area is bad.
    waste = np.sqrt(Lc * Lm)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    # Complementary resource weight grows with how skewed the job is.
    skew = np.abs(d0 - d1)

    score = (0.55 * fit
             + 0.70 * bal
             + (0.30 + 0.55 * skew) * comp
             + 0.60 * floor
             - 0.45 * waste)

    # Fresh-bin penalty: weaker for large jobs (they need their own bin anyway).
    score[-1] -= 0.14 - 0.11 * used

    return score
