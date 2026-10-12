import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus a penalty for unbalanced leftover resources.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the extra term discourages bins
    whose leftover is lopsided, keeping both resources usable.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    return -np.maximum(n_c, n_m) - 0.3569 * np.abs(n_c - n_m)
