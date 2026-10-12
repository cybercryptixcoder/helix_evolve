import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    # soft-max base: smoothly interpolate between L1 and L-inf best-fit
    t = 8.0
    base = -np.logaddexp(t * n_c, t * n_m) / t

    imb = -0.6302 * (n_c - n_m) ** 2
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    return base + imb + shape + align
