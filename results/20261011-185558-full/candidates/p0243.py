import numpy as np
import math


def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Fractions of capacity
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    mc = np.maximum(rem[:, 0], 1e-9) / cap[0]
    mm = np.maximum(rem[:, 1], 1e-9) / cap[1]

    # Leftover after placing the item (fractions), clipped to >= 0
    Lc = np.clip(mc - d0, 0.0, None)
    Lm = np.clip(mm - d1, 0.0, None)

    # Tightness: how well the item fills the binding residual dimension
    fit = np.minimum(
        np.minimum(d0 / np.maximum(mc, 1e-9), d1 / np.maximum(mm, 1e-9)), 1.0
    )

    # Balance of the leftover between the two resources
    bal = -np.abs(Lc - Lm)
    # Geometric fill reward
    geom = -np.sqrt(np.maximum(Lc * Lm, 0.0))
    # Keep both resources alive so the bin stays usable
    weak = np.minimum(Lc, Lm)
    alive = np.minimum(2.0 * weak, 1.0)
    # Euclidean magnitude of the leftover (penalise large remainders)
    mag = -np.sqrt(np.maximum(Lc * Lc + Lm * Lm, 0.0))

    used = 0.5 * (d0 + d1)
    w_fit = 1.05 + 0.30 * used

    score = (
        w_fit * fit
        + 0.90 * bal
        + 0.50 * geom
        + 0.30 * alive
        + 0.20 * mag
    )

    # Tiny tie-break favouring older (earlier) bins for consolidation
    idx = np.arange(len(score), dtype=float)
    score = score - 1e-6 * idx

    # Small adaptive penalty for opening a brand-new bin
    score[-1] -= 0.16 - 0.12 * used

    return np.nan_to_num(score, nan=-1e6, posinf=1e6, neginf=-1e6)
