import numpy as np


def priority(item, bins, capacity):
    # Residual free space after hypothetically placing the item (>= 0 for candidates).
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    # how demanding the item is (binding dimension fraction)
    hardness = np.maximum(f_c, f_m)

    # base: best-fit in the tighter (binding) resource
    base = -np.maximum(n_c, n_m)

    # imbalance penalty, strengthened for hard items (they decide bin count)
    imb = -(0.63 + 0.45 * hardness) * (n_c - n_m) ** 2

    # shape penalty: residual free-space shape should match the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: residual pointing along the item's aspect ratio
    align = 0.31 * (n_c * f_c + n_m * f_m)

    # BOLD CHANGE 1: tie-break toward fuller bins via total free space,
    # so that among equal max-residual bins we consume more of the leftover.
    fill = -0.09 * (n_c + n_m)

    # BOLD CHANGE 2: soft-max pickup. A differentiable nudge that also rewards
    # keeping the *secondary* resource tight, not just the binding one.
    softmax_pick = -0.12 * (n_c * n_m)

    return base + imb + shape + align + fill + softmax_pick
