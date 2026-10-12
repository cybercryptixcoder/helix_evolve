import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus a relative penalty for unbalanced leftover resources.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the extra term discourages bins
    whose leftover is lopsided, scaled by how full the bin is so that the
    penalty bites hardest on near-full bins that block future placements.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    eps = 1.45e-06
    return -np.maximum(n_c, n_m) - 0.2844 * np.abs(n_c - n_m) / (n_c + n_m + eps)
