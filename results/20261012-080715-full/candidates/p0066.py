import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus quadratic imbalance and shape-matching penalties.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the quadratic term discourages
    lopsided leftovers. The new term rewards the residual being close to the
    item's own resource split in the binding dimension.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]
    return (
        -np.maximum(n_c, n_m)
        - 0.5685 * (n_c - n_m) ** 2
        - 0.179 * ((n_c - f_c) - (n_m - f_m)) ** 2
    )
