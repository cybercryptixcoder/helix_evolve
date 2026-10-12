import numpy as np

def priority(item, bins, capacity):
    residual = bins - item                      # remaining after placing (>=0 for all candidates)
    n_c = residual[:, 0] / capacity[0]          # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]          # normalised residual memory
    f_c = item[0] / capacity[0]                 # normalised item demand
    f_m = item[1] / capacity[1]

    # base: best-fit in the tighter resource (small remaining is good)
    base = -np.maximum(n_c, n_m)

    # imbalance penalty: punish a leftover that is lopsided in one resource
    imb = -0.6302 * (n_c - n_m) ** 2

    # shape penalty: punish a residual whose "free-space shape" drifts from the item's shape
    shape = -0.211 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: prefer bins whose residual points along the item's aspect ratio
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # closing bonus: reward a near-zero binding residual so bins get finished off
    close = 0.3301 * np.exp(-8.86 * np.maximum(n_c, n_m))

    # NEW: guard against stranding a resource.  When the leftover in the *other*
    # resource is large but the binding one is tiny, the bin is a sliver that only
    # small jobs can use.  Penalise the free volume that is unusable by a job of
    # the item's own shape, i.e. residual shortfall along the item's aspect.
    strand = -0.25 * np.minimum(n_c, n_m) * (1.0 - np.maximum(f_c, f_m))

    # NEW: mild preference for older bins (earlier rows) so bins get closed out
    # rather than spread thin; decay with row index, vectorised.
    k = bins.shape[0]
    age = -0.015 * (np.arange(k) / max(k - 1, 1))

    return base + imb + shape + align + close + strand + age
