import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus a small L1 penalty: prefers bins that are tight in the
    binding dimension and not wasteful in the other, breaking the ties that pure
    max-fit leaves behind."""
    n = (bins - item) / capacity
    n_c = n[:, 0]
    n_m = n[:, 1]
    return -(np.maximum(n_c, n_m) + 0.25 * (n_c + n_m))
