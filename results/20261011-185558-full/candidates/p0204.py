import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover in each resource after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fit: binding-dimension tightness (prefer the bin the item nearly fills).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance: prefer leftover that is even across the two resources.
    bal = -np.abs(Lc - Lm)

    # Geom: prefer the small leftover *area* (well-filled bin).
    geom = -np.sqrt(Lc * Lm)

    # Usable: keep the weaker resource reasonably large for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Accept: reward both leftovers being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # Size-scaled complementarity: match a CPU-heavy job to a memory-rich bin
    # (and vice versa), scaled by how skewed the arriving job is.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    comp = np.clip(d0 - d1, -1.0, 1.0) * (Lm - Lc)

    # Adaptive penalty discouraging a fresh bin, weaker for big jobs.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit + 0.90 * bal + 0.50 * geom
             + 0.35 * usable + 0.15 * accept
             + (0.30 * np.abs(d0 - d1)) * comp)

    score[-1] -= 0.16 - 0.12 * used

    return score
