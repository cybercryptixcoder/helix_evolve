import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Item "shape": share of demand in each resource.
    tot = max(it[0] + it[1], 1e-9)
    ic, im = it[0] / tot, it[1] / tot

    # Bin leftover direction, guarded.
    lt = np.maximum(Lc + Lm, 1e-9)
    bc, bm = Lc / lt, Lm / lt

    # Alignment: does the bin's remaining shape match the item's demand shape?
    align = ic * bc + im * bm          # in [0,1]

    # Waste: the largest leftover resource is what future jobs must fit.
    waste = np.maximum(Lc, Lm)

    # Tight fit: reward bins the item nearly fills (binding dimension).
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # New-bin penalty, weaker for large jobs.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = 1.10 * align + 0.90 * fit - 0.55 * waste
    score[-1] -= 0.20 - 0.16 * used

    return score
