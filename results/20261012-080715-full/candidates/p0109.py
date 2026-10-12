import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    base = -np.maximum(n_c, n_m)
    imb = -0.6302 * (n_c - n_m) ** 2
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # NEW: L1 fill term -- prefer bins that end up fuller in total (concentrate)
    fill = -0.35 * (n_c + n_m)

    # NEW: complementarity -- reward residual opposing the item's aspect
    comp = -0.25 * (n_c - n_m) * (f_c - f_m)

    return base + imb + shape + align + fill + comp
