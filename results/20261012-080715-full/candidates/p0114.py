import numpy as np

def priority(item, bins, capacity):
    residual = bins - item                      # remaining after placing (>=0 for all candidates)
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    # base: blend of L-inf (best-fit on the tight resource) and L1 (area fit).
    # The L1 component mildly prefers bins that are also slim in the slack
    # resource, which helps when the two families disagree about the binding dim.
    big = np.maximum(n_c, n_m)
    small = np.minimum(n_c, n_m)
    base = -big - 0.15 * small

    # imbalance penalty: punish a leftover that is lopsided in one resource
    imb = -0.60 * (n_c - n_m) ** 2

    # shape penalty: punish a residual whose "free-space shape" drifts from the item's shape
    shape = -0.20 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: prefer bins whose residual points along the item's aspect ratio
    align = 0.32 * (n_c * f_c + n_m * f_m)

    # closing bonus: reward finishing off a bin whose tight leftover is tiny
    close = 0.33 * np.exp(-9.0 * big)

    # IMPORTANT: return one score per candidate bin -> shape (k,)
    return base + imb + shape + align + close
