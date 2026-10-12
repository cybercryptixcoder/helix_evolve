import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    # soft-max base: p-norm blends tightest-resource fit with total leftover
    p = 4.0
    base = -(n_c ** p + n_m ** p) ** (1.0 / p)

    hardness = np.maximum(f_c, f_m)
    imb = -(0.5685 + 0.4 * hardness) * (n_c - n_m) ** 2
    shape = -0.20 * ((n_c - f_c) - (n_m - f_m)) ** 2
    align = 0.28 * (n_c * f_c + n_m * f_m)

    return base + imb + shape + align
