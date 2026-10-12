import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    t = np.maximum(n_c, n_m)          # binding residual
    u = np.minimum(n_c, n_m)          # slack residual
    s = n_c + n_m
    d = n_c - n_m
    area = n_c * n_m

    # 1) best-fit: small binding residual is good
    base = -t
    # 2) L1 balance: square-ish leftover keeps both dims usable
    balance = -0.35 * np.abs(d)
    # 3) squared distance to a "target residual" that is either near-zero
    #    (close the bin) or roughly the item's own size (room for a twin job)
    target_c = 0.5 * f_c
    target_m = 0.5 * f_m
    shape = -0.20 * ((n_c - target_c) ** 2 + (n_m - target_m) ** 2)
    # 4) area reward scaled by balance: only reward leftover we can actually use
    usable = 0.9 * area / (1.0 + 6.0 * np.abs(d))   # penalize lopsided area
    return base + balance + shape + usable
