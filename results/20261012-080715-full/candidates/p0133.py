import numpy as np

def priority(item, bins, capacity):
    residual = bins - item                      # remaining after placing (>=0 for all candidates)
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    mx = np.maximum(n_c, n_m)                   # binding residual (the tighter resource)
    fmx = np.maximum(f_c, f_m)                  # item size in its binding resource

    # base: best-fit on the tighter resource, PLUS a light pull toward generally
    # fuller bins so that the non-binding resource is not left half-wasted.
    base = -mx - 0.12 * (n_c + n_m)

    # imbalance penalty: punish a leftover that is lopsided in one resource
    imb = -0.6302 * (n_c - n_m) ** 2

    # shape penalty: punish a residual whose free-space shape drifts from the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: keep usable room in the item's own direction
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # BOLD CHANGE: closing bonus is now a heavier-tailed rational fill reward
    # (instead of the gated exponential) so slightly-off bins still get finished,
    # combined with a narrow exact-fit spike that only fires on a near-perfect fit.
    close = 0.35 * (1.0 / (1.0 + 18.0 * mx)) * (1.4 - fmx) + 0.10 * np.exp(-40.0 * mx)

    return base + imb + shape + align + close
