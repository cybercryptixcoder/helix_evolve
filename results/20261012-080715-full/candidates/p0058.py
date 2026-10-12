import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus one-sided imbalance and shape-matching penalties.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view. The imbalance term is now one-sided:
    it only penalises lopsided leftovers that exceed the arriving item's own
    resource split, so a lopsided item may legitimately leave a matching
    lopsided residual. The final term rewards the residual change being close
    to the item's own resource split in the binding dimension.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]
    return (
        -np.maximum(n_c, n_m)
        - 0.7393 * np.maximum(0.0, np.abs(n_c - n_m) - np.abs(f_c - f_m)) ** 2
        - 0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2
    )
