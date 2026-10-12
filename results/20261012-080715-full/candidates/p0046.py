import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus a quadratic penalty for unbalanced leftover resources,
    with a small constant penalty on opening a new bin.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the extra term strongly discourages
    bins whose leftover is lopsided, keeping both resources usable. The last
    row (a brand-new empty bin) gets a small constant penalty so a new bin
    must beat the best old bin by that margin to be opened.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    score = -np.maximum(n_c, n_m) - 0.5685 * (n_c - n_m) ** 2
    score[-1] -= 0.05
    return score
