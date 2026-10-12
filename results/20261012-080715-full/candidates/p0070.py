import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit + imbalance + shape terms, with one bold change:
    the imbalance/shape penalties are weighted by a measure of how
    "hard" the item is to place (its demand relative to capacity), and a
    dot-product alignment term rewards residuals that point along the
    item's aspect ratio (kept from a sibling program).

    Hard items (big in either dimension) get stronger imbalance pressure,
    because packing them well is what decides the bin count; tiny items
    are cheap to slot anywhere, so we mostly just do best-fit for them.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    # how demanding the item is: its binding dimension fraction
    hardness = np.maximum(f_c, f_m)

    # base: best-fit in the tighter resource
    base = -np.maximum(n_c, n_m)

    # imbalance penalty, scaled up for demanding items
    imb = -(0.5685 + 0.4 * hardness) * (n_c - n_m) ** 2

    # shape penalty: residual free-space shape should match item shape
    shape = -0.20 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: residual pointing along the item's aspect ratio
    align = 0.28 * (n_c * f_c + n_m * f_m)

    return base + imb + shape + align
