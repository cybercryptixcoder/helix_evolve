import numpy as np

def priority(item, bins, capacity):
    # residual space left in each candidate bin after placing the job
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]        # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]        # normalised residual memory
    f_c = item[0] / capacity[0]               # normalised item demand
    f_m = item[1] / capacity[1]

    # BOLD CHANGE 1: base is no longer pure best-fit on the binding resource.
    # We still prefer a small *binding* residual (max term), but now also penalise
    # waste in the slack resource (min term). This steers jobs into bins whose
    # non-critical dimension is not left half-empty, which matters because the
    # next job may bind on the other resource.
    base = -np.maximum(n_c, n_m) - 0.25 * np.minimum(n_c, n_m)

    # keep the proven core corrections
    imb = -0.6302 * (n_c - n_m) ** 2
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # closing bonus: finish off bins whose binding residual is nearly exhausted
    close = 0.3301 * np.exp(-8.86 * np.maximum(n_c, n_m)) * (1.38 - np.maximum(f_c, f_m))

    # BOLD CHANGE 2: explicitly reward residuals that could still hold a *twin*
    # of the arriving job in both resources. This promotes leaving "reusable"
    # corners instead of slivers, so runs of similar jobs pack two-at-a-time.
    twin = 0.15 * ((residual[:, 0] >= item[0]) & (residual[:, 1] >= item[1]))

    return base + imb + shape + align + close + twin
