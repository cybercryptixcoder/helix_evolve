import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    hi = np.maximum(n_c, n_m)
    lo = np.minimum(n_c, n_m)

    # base: best-fit in the binding resource, plus a soft penalty on the
    # other (non-binding) leftover so we also fill the slack dimension
    base = -hi - 0.16 * lo

    # imbalance penalty
    imb = -0.63 * (n_c - n_m) ** 2

    # shape penalty
    shape = -0.21 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward
    align = 0.31 * (n_c * f_c + n_m * f_m)

    # closing bonus, gated by item size (small items finish bins off)
    close = 0.33 * np.exp(-8.86 * hi) * (1.38 - np.maximum(f_c, f_m))

    return base + imb + shape + align + close
