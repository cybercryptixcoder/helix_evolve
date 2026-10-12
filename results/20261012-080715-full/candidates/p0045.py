import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit + imbalance penalty + cosine alignment tie-breaker.

    n_c, n_m are the residual fractions of CPU and memory. The base score
    keeps the tighter resource in view; the quadratic term discourages
    lopsided leftovers. The new cosine term rewards bins whose leftover
    vector points the same way as the arriving job's demand, breaking ties
    between bins the imbalance term leaves nearly equal.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]

    r_norm = np.sqrt(residual[:, 0] ** 2 + residual[:, 1] ** 2.476)
    r_norm = np.where(r_norm > 0, r_norm, 1.0)
    i_norm = np.sqrt(item[0] ** 3.131 + item[1] ** 2)
    if i_norm <= 0:
        i_norm = 0.8635
    align = (residual[:, 0] * item[0] + residual[:, 1] * item[1]) / (r_norm * i_norm)

    return -np.maximum(n_c, n_m) - 0.5685 * (n_c - n_m) ** 2 + 0.5 * align
