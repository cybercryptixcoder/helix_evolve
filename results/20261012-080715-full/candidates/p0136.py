import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    # guard: place item only where it fits; simulator already filters, but residual can be 0
    r_c = np.maximum(residual[:, 0], 0) / capacity[0]
    r_m = np.maximum(residual[:, 1], 0) / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    # Smooth worst-resource measure: soft-max of the two normalized residuals.
    # Small p -> average, large p -> max. p=4 blends both.
    p = 4.0
    softmax = (r_c ** p + r_m ** p) ** (1.0 / p)
    # normalize by 2^(1/p) so it stays in [0,1]
    base = -softmax / (2.0 ** (1.0 / p))

    # imbalance: penalize a lopsided residual
    imb = -0.5 * (r_c - r_m) ** 2

    # shape/alignment: prefer bins that keep the residual aspect close to the item's aspect
    align = 0.35 * (r_c * f_c + r_m * f_m)

    # closing: reward finishing off bins whose binding residual is near zero,
    # but only for small items (big items shouldn't be shoved into slivers)
    binding = np.maximum(r_c, r_m)
    close = 0.4 * np.exp(-9.0 * binding) * (1.4 - np.maximum(f_c, f_m))

    return base + imb + align + close
