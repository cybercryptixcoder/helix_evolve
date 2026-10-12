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

    # Fit: tightness in the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Harmonic mean of leftovers: collapses toward 0 if EITHER resource
    # is nearly exhausted, so sliver-leftover bins are strongly punished.
    hmean = 2.0 * Lc * Lm / np.maximum(Lc + Lm, 1e-9)
    geom = np.sqrt(Lc * Lm)

    # Sliver penalty: how unbalanced the leftover is (0 = even, 1 = sliver).
    sliver = np.abs(Lc - Lm) / np.maximum(Lc + Lm, 1e-9)

    # Alignment: for skewed jobs, prefer bins whose leftover matches the
    # job's heavy resource (leftover large where the job was small).
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.abs(d0 - d1)
    align = np.clip(d0 - d1, -1.0, 1.0) * (Lm - Lc)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.85 * hmean
             + 0.35 * geom
             - 0.55 * sliver * (1.0 - 0.5 * used)
             + 0.30 * align * skew)

    # Fresh-bin penalty: weaker for big jobs (opening is right for them).
    score[-1] -= 0.18 - 0.14 * used

    return score
