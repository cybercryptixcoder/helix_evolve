import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = 0.5 * (d0 + d1)
    skew = np.abs(d0 - d1)

    # tight fit on the binding dimension
    fit = np.minimum(np.minimum(it[0]/rc, it[1]/rm), 1.0)

    # after-placement squareness, amplified for skewed items
    sq = -np.abs(Lc - Lm) * (0.6 + 1.4 * skew)

    # area / fragmentation
    geom = -np.sqrt(Lc*Lm)

    # weak-resource room
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0*weak, 1.0)

    # both-resources room
    accept = np.minimum(2.0*Lc,1.0)*np.minimum(2.0*Lm,1.0)

    score = (1.15 + 0.20*used)*fit + 0.75*sq + 0.45*geom + 0.35*usable + 0.10*accept
    score[-1] -= 0.15 - 0.10*used
    return score
