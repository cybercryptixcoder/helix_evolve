import numpy as np

def priority(item, bins, capacity):
    # --- same core as the program to improve -------------------------------
    residual = bins - item                      # remaining after placing the job
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    # best-fit in the tighter resource (small remaining is good)
    base = -np.maximum(n_c, n_m)

    # lopsided-leftover penalty
    imb = -0.6302 * (n_c - n_m) ** 2

    # free-space "shape" drift from the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment of residual aspect with the item's aspect
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # --- bold change 1: twin-fit reward ------------------------------------
    # Reward a leftover whose size matches ONE more item in BOTH resources
    # (|n - f| small), i.e. leave exactly room for a future twin job instead
    # of a lopsided hole. Different functional form from `shape` (sum of
    # squared *absolute* residual-vs-item gaps rather than their difference).
    double = -0.20 * ((n_c - f_c) ** 2 + (n_m - f_m) ** 2)

    # --- bold change 2: item-adaptive closing bonus ------------------------
    # Strongly reward driving the binding residual to zero so bins get
    # finished off, and scale the strength with the arriving item's size:
    # big jobs are the ones worth "closing" a bin with.
    strength = 0.25 + 0.35 * np.maximum(f_c, f_m)
    close = strength * np.exp(-8.86 * np.maximum(n_c, n_m))

    return base + imb + shape + align + double + close
