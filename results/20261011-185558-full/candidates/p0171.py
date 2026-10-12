import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised residual after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Item direction in normalised space.
    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    inorm = np.sqrt(ic * ic + im * im) + 1e-9
    uc = ic / inorm
    um = im / inorm

    # Residual direction; alignment with item direction means future similar
    # jobs can stack here (good for correlated / bimodal families).
    lnorm = np.sqrt(Lc * Lc + Lm * Lm) + 1e-9
    align = (Lc * uc + Lm * um) / lnorm  # in [-1, 1]

    # Tightness of the binding resource: how close the item gets to filling it.
    tight = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Residual magnitude: prefer small residual (well filled) but not zero.
    mag = -lnorm

    # Reusability: residual close to a whole item's worth, in either resource.
    reuse = -np.minimum(np.abs(Lc - ic), 1.0) - np.minimum(np.abs(Lm - im), 1.0)

    # Balance of residual shape.
    bal = -np.abs(Lc - Lm)

    used = min(max(0.5 * (ic + im), 0.0), 1.0)

    score = (1.10 * tight
             + 0.55 * align
             + 0.60 * mag
             + 0.30 * reuse
             + 0.35 * bal)

    # Penalise opening a new bin, but less so for large items.
    score[-1] -= 0.18 - 0.14 * used

    return score
