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

    # Normalised item demand.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    # --- Fit: binding-dimension tightness (near-fill preferred). ---
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # --- Residual shape matching: log-ratio of leftover vs item shape.
    # If the bin's leftover has the same aspect as the item, the item
    # "fits the hole" and future packing is cleaner.
    eps = 1e-6
    item_ratio = (d0 + eps) / (d1 + eps)
    left_ratio = (Lc + eps) / (Lm + eps)
    shape = -np.abs(np.log(left_ratio / item_ratio))

    # --- Balance: prefer even leftovers. ---
    bal = -np.abs(Lc - Lm)

    # --- Geom: prefer small leftover area (well-filled). ---
    geom = -np.sqrt(Lc * Lm)

    # --- Usable: keep the weaker resource alive. ---
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # --- Complementarity: lopsided item wants oppositely lopsided bin. ---
    comp = np.clip(d0 - d1, -1.0, 1.0) * (Lm - Lc)

    # --- Smooth, capacity-aware new-bin penalty: discourage opening a
    # fresh bin more when the item is small relative to capacity. ---
    small = 1.0 - used
    new_pen = 0.18 * small + 0.06

    score = ((1.00 + 0.30 * used) * fit
             + 0.55 * shape
             + 0.85 * bal
             + 0.45 * geom
             + 0.30 * usable
             + 0.30 * comp)

    score[-1] -= new_pen

    return score
