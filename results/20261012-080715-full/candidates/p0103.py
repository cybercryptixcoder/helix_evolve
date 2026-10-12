import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    mx = np.maximum(n_c, n_m)
    mn = np.minimum(n_c, n_m)

    # BOLD CHANGE 1: base is a blend of L-infinity and L1 (sum) best-fit.
    # -max alone is pure best-fit in the binding resource; adding -w*min
    # also penalises leaving the *other* resource loose, which fights
    # fragmentation across the two dimensions.
    base = -mx - 0.15 * mn

    # imbalance penalty (kept)
    imb = -0.6302 * (n_c - n_m) ** 2

    # shape penalty (kept)
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward (kept)
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # BOLD CHANGE 2: a mild closing bonus that only kicks in for already
    # tight bins, to finish them off instead of scattering small residues.
    close = 0.30 * np.exp(-9.0 * mx)

    return base + imb + shape + align + close
