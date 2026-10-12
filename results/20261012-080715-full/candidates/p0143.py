import numpy as np

def priority(item, bins, capacity):
    residual = bins - item                      # remaining after placing (>=0 for all candidates)
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    # base: best-fit in the tighter resource (small binding residual is good)
    base = -np.maximum(n_c, n_m)

    # imbalance penalty: punish a leftover that is lopsided in one resource
    imb = -0.6302 * (n_c - n_m) ** 2

    # shape penalty: punish a residual whose free-space shape drifts from the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: prefer bins whose residual points along the item's aspect ratio
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # BOLD CHANGE 1: asymmetric binding penalty.
    # Classic -max is symmetric; but a residual that is tight in the *non-binding*
    # resource while loose in the other wastes usable space. Penalise the smaller
    # normalised residual too, so the score nudges toward residuals that are
    # simultaneously snug in both resources (a "square-ish" leftover).
    loose = -0.45 * np.minimum(n_c, n_m)

    # BOLD CHANGE 2: reset-aware closing term.
    # Only reward finishing a bin when the item is not oversized for the residual;
    # i.e. gate the closing bonus by how snug the *post-placement* bin is AND by
    # the item being small relative to capacity. This replaces the failed
    # symmetric close with a shape-aware one.
    snug = np.maximum(n_c, n_m)
    close = 0.34 * np.exp(-9.0 * snug) * (1.0 - np.maximum(f_c, f_m))

    return base + imb + shape + align + loose + close
