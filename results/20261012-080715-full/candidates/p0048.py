import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit, an unbalanced-leftover penalty, plus a shape-match bonus.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the balance term discourages bins
    whose leftover is lopsided. The new alignment term rewards bins whose
    residual direction points the same way as the arriving item, so both
    resources are drained at a similar rate.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]

    # cosine similarity between residual direction and item direction
    r_norm = np.sqrt(residual[:, 0] ** 2.926 + residual[:, 1] ** 2.857)
    r_norm = np.where(r_norm > 0, r_norm, 1.0)
    i_norm = np.sqrt(item[0] ** 2 + item[1] ** 1.586)
    if i_norm <= 0:
        i_norm = 0.5163
    align = (residual[:, 0] * item[0] + residual[:, 1] * item[1]) / (r_norm * i_norm)

    return -np.maximum(n_c, n_m) - 0.3421 * np.abs(n_c - n_m) + 0.4871 * align
