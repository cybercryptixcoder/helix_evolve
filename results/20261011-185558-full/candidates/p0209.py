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

    # Fit: binding-dimension tightness.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance across resources.
    bal = -np.abs(Lc - Lm)

    # Geom: small leftover area is good.
    geom = -np.sqrt(Lc * Lm)

    # Usable: keep the weaker resource reasonably large.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Accept: reward both leftovers being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # Residual compatibility: a leftover is "productive" if it is a decent
    # fraction of a bin in BOTH resources -- such bins still take typical jobs.
    # Use a soft, saturating measure that peaks around half a bin.
    prod = (np.minimum(Lc / 0.5, 1.0) * np.minimum(Lm / 0.5, 1.0))

    # Wasted-space penalty: if the item leaves a big chunk in one resource
    # while nearly exhausting the other, the bin is effectively dead.
    waste = np.maximum(Lc, Lm) - np.minimum(Lc, Lm)
    dead = np.clip(waste - 0.5, 0.0, None)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit + 0.90 * bal + 0.50 * geom
             + 0.35 * usable + 0.15 * accept
             + 0.30 * prod - 0.55 * dead)

    # Fresh-bin penalty: stronger when the item is small (we should reuse),
    # weaker when the item is large (a new bin is often right).
    score[-1] -= 0.22 - 0.20 * used

    return score
