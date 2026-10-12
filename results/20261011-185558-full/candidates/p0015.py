import numpy as np


def priority(item, bins, capacity):
    # remaining after placing the item in each bin
    rem = bins - item  # shape (k, 2)

    # how tightly the item fills each bin (fraction consumed of each resource)
    used_frac = item / capacity  # constant across bins, but keep for weighting

    # scarcity of each resource in each bin: smaller remaining => scarcer
    # score high when the bin's remaining room in a resource is small but >= 0
    eps = 1e-9
    rem_cpu = np.maximum(rem[:, 0], 0.0)
    rem_mem = np.maximum(rem[:, 1], 0.0)

    # normalized leftover after placement
    left_cpu = rem_cpu / capacity[0]
    left_mem = rem_mem / capacity[1]

    # A bin is "good" if it is left tight (small leftover) in both resources.
    # Use the max leftover as the dominant waste term, plus a small sum term
    # to break ties toward balanced leftovers.
    waste = np.maximum(left_cpu, left_mem) + 0.3 * (left_cpu + left_mem)

    # Prefer bins where the scarcer resource (in this bin) is the one the item
    # stresses most: weight leftover by how much of the item it takes.
    weight = np.array([used_frac[0], used_frac[1]])
    weight = weight / (weight.sum() + eps)
    weighted_left = left_cpu * weight[0] + left_mem * weight[1]

    score = -(waste + 0.5 * weighted_left)

    return score
