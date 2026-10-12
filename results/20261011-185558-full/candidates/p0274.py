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

    # Normalised demand of the arriving item.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = min(max(0.5 * (d0 + d1), 0.0), 1.0)

    # 1) Binding-dimension tightness: prefer the bin the item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Concave pair score: geometric mean of the two leftovers.  This
    #    collapses to ~0 whenever EITHER resource is nearly exhausted, so it
    #    strongly discourages stranding one resource.
    pair = np.sqrt(Lc * Lm)

    # 3) Complementarity gate: bin can absorb the mirror-image job later.
    #    Mirror job needs (mem, cpu) = (d1, d0) in normalised units.
    mirror_ok = (Lc + 1e-12 >= d1) & (Lm + 1e-12 >= d0)
    comp = np.where(mirror_ok, 1.0, 0.0)

    # 4) Reserve smooth term: how closely the leftover matches that mirror.
    reserve = np.maximum(0.0, 1.0 - (np.abs(Lc - d1) + np.abs(Lm - d0)))

    # 5) Balance penalty only when severe (avoids double-counting with pair).
    bal = -np.abs(Lc - Lm)

    score = (1.30 * fit
             + 1.10 * pair
             + 0.55 * comp
             + 0.45 * reserve
             + 0.30 * bal)

    # Fresh-bin penalty: stronger when the item is small (wasting a big bin
    # on a tiny job), weaker when the item is large (a new bin is inevitable).
    score[-1] -= 0.22 - 0.16 * used

    return np.asarray(score, dtype=float).reshape(-1)
