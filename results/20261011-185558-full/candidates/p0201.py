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

    # Occupancy of the bin BEFORE the item (how full it already was).
    pre_c = np.clip(rem[:, 0] / cap[0], 0.0, 1.0)
    pre_m = np.clip(rem[:, 1] / cap[1], 0.0, 1.0)

    # Fit: prefer the bin the item nearly fills in its binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Geom: small leftover area after placement (well-filled bin).
    geom = -np.sqrt(Lc * Lm)

    # Balance: leftover even across resources.
    bal = -np.abs(Lc - Lm)

    # Complementarity for skewed (anticorr/bimodal) items.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = d0 - d1
    comp = skew * (Lm - Lc)

    # Tightness: how full the bin becomes (both resources).
    tight = np.minimum(pre_c + d0, 1.0) * np.minimum(pre_m + d1, 1.0)

    # Fresh-bin penalty: strong default, relaxed for large items.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.6 * fit
             + 0.9 * geom
             + 0.5 * bal
             + 0.6 * comp
             + 0.4 * tight)

    score[-1] -= 0.30 - 0.22 * used

    return score
