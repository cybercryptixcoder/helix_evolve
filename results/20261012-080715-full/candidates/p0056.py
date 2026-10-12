import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus quadratic imbalance and shape-matching penalties,
    with an extra item-scaled cost on the new-bin row so large jobs do not
    open a fresh bin too cheaply.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]
    score = (
        -np.maximum(n_c, n_m)
        - 0.5685 * (n_c - n_m) ** 2
        - 0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2
    )
    w = 0.2355
    f = item / capacity
    score[-1] -= w * np.max(f)
    return score
