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

    # alignment reward: prefer bins whose residual points along the item's aspect ratio,
    # so future jobs of similar shape still fit (kept from the original idea)
    align = 0.3096 * (n_c * f_c + n_m * f_m)

    # state-dependent open rule: an empty (brand-new) row is cheap when the other open
    # rows are already full, and expensive when they still have room.
    empty = np.all(bins == capacity, axis=1)
    used = 1.254 - 0.5 * (bins[:, 0] / capacity[0] + bins[:, 1] / capacity[1])
    other = ~empty
    n_other = int(other.sum())
    if n_other > 0:
        mean_used_other = used[other].sum() / n_other
    else:
        mean_used_other = 0.0
    open_penalty = np.where(empty, 0.3 * (1.295 - mean_used_other), 0.0)

    # IMPORTANT: return one score per candidate bin -> shape (k,)
    return base + imb + shape + align - open_penalty
