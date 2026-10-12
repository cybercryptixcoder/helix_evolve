import numpy as np

def priority(item, bins, capacity):
    residual = bins - item                      # remaining after placing (>=0 for all candidates)
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    tight = np.maximum(n_c, n_m)                # the binding residual (L-infinity fit)

    # base: best-fit in the tighter resource
    base = -tight

    # imbalance penalty: punish a leftover that is lopsided in one resource
    imb = -0.6302 * (n_c - n_m) ** 2

    # shape penalty: residual "free-space shape" should match the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: residual points along the item's aspect ratio
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # closing bonus: reward a near-zero binding residual so bins get finished off
    close = 0.3301 * np.exp(-8.86 * tight)

    # L1 squeeze: among bins with the same binding residual, prefer the one that
    # also drains the non-binding resource -> fewer half-empty bins overall
    l1 = -0.12 * (n_c + n_m)

    return base + imb + shape + align + close + l1
