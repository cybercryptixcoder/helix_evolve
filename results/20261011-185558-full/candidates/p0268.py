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
    L = np.stack([Lc, Lm], axis=1)

    # Normalised item demand vector.
    d = np.array([it[0] / cap[0], it[1] / cap[1]])
    dn = np.sqrt(d[0] ** 2 + d[1] ** 2) + 1e-9
    du = d / dn

    # Alignment: cosine between item direction and leftover direction.
    # A CPU-heavy item wants a memory-heavy leftover, and vice versa,
    # so the bin whose leftover points "away" from the item is preferred.
    Ln = np.sqrt(L[:, 0] ** 2 + L[:, 1] ** 2) + 1e-9
    cos = (L[:, 0] * du[0] + L[:, 1] * du[1]) / Ln
    align = -cos * (dn / np.sqrt(2.0))  # scale by item imbalance

    # Fit: binding-dimension tightness.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance and geometric leftovers.
    bal = -np.abs(Lc - Lm)
    geom = -np.sqrt(Lc * Lm)

    # Usable: keep the weaker resource alive for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Accept: reward both leftovers being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit + 0.85 * bal + 0.45 * geom
             + 0.35 * usable + 0.15 * accept + 0.55 * align)

    score[-1] -= 0.16 - 0.12 * used

    return score
