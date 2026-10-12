import numpy as np


def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Item fractions of capacity.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]

    # Normalised leftover after placing the item.
    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # 1) Tight fit in the binding dimension: prefer a bin the item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Balance: leftover even across the two resources stays reusable.
    bal = -np.abs(Lc - Lm)

    # 3) Geometric fill: small leftover *area* means a well-filled bin.
    geom = -np.sqrt(Lc * Lm)

    # 4) Usable: keep the weaker resource from being starved.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # 5) Accept: reward both leftovers being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # 6) Complementarity: a skewed item should land in a bin whose leftover is
    #    skewed the *other* way, so the pair packs tightly (helps anticorr).
    comp = -(dc - dm) * (Lc - Lm)

    used = 0.5 * (dc + dm)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.30 * used) * fit
             + 0.90 * bal
             + 0.45 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.35 * comp)

    # Mild oldest-first tie-break for consolidation.
    idx = np.arange(score.shape[0], dtype=float)
    score = score - 1e-6 * idx

    # Gate opening a fresh bin, weaker for larger jobs.
    score[-1] -= 0.16 - 0.12 * used

    return np.nan_to_num(score, nan=-1e6, posinf=1e6, neginf=-1e6)
