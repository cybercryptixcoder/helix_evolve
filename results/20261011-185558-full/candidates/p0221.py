import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placement.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Direction alignment: leftover vector vs capacity direction.
    # Rewards bins whose remaining shape matches the bin's overall shape,
    # i.e. leftover is proportional to capacity (a "clean" residual bin).
    Ln = np.sqrt(Lc * Lc + Lm * Lm) + 1e-9
    align = (Lc + Lm) / (np.sqrt(2.0) * Ln)

    # Fill: prefer the item to fill the bin's binding resource (tight fit),
    # but measured against the leftover *shape*, not raw ratios.
    bind = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance: even leftover across resources.
    bal = -np.abs(Lc - Lm)

    # Geom: small leftover area (well packed).
    geom = -np.sqrt(Lc * Lm)

    # Usable: keep the weaker resource reasonably large.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Accept: reward both leftovers at least half a bin (room for more).
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # Adaptive new-bin penalty, weaker for big jobs.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    # Skew: how directional the job is.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.abs(d0 - d1)

    # Complementarity: for skewed jobs prefer leftover big in the heavy resource.
    comp = skew * (Lm - Lc) * np.sign(d0 - d1)

    score = ((1.00 + 0.30 * used) * bind
             + 0.55 * bal
             + 0.45 * geom
             + 0.35 * usable
             + 0.15 * accept
             + (0.35 + 0.35 * skew) * align
             + 0.45 * comp)

    score[-1] -= 0.15 - 0.11 * used

    return score
