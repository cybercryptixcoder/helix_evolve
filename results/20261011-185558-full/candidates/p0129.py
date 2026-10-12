import numpy as np


def priority(item, bins, capacity):
    ic = float(item[0])
    im = float(item[1])

    rem = np.asarray(bins, dtype=float)
    rc = rem[:, 0]
    rm = rem[:, 1]

    eps = 1e-9
    scale = float(capacity[0] + capacity[1]) + eps

    # "Area best fit": both ratios near 1 => residual area close to item area.
    fit_c = ic / np.maximum(rc, eps)
    fit_m = im / np.maximum(rm, eps)
    score = fit_c * fit_m

    # Weak tie-break: prefer residual whose leftovers are balanced in the two dims.
    left_c = rc - ic
    left_m = rm - im
    score = score - 1e-6 * np.abs(left_c - left_m) / scale

    # Any row that does not actually fit is pushed far below every valid score.
    legal = (rc >= ic - eps) & (rm >= im - eps)
    score = np.where(legal, score, -1e6)

    return np.clip(score, -1e17, 1e17)
