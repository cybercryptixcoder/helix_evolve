import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit plus a tighter-resource-weighted imbalance penalty.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the extra term discourages lopsided
    leftovers, weighted by max(f_c, f_m) -- the arriving item's demand
    fraction in its dominant resource -- since a lopsided bin is most
    dangerous when the item leans hard on one resource.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f = item / capacity
    w = np.max(f)
    return -np.maximum(n_c, n_m) - 0.7526 * w * (n_c - n_m) ** 2
