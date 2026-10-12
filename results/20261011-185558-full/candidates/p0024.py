import numpy as np


def priority(item, bins, capacity):
    item = np.asarray(item, dtype=float)
    bins = np.asarray(bins, dtype=float)
    cap = np.asarray(capacity, dtype=float)

    rem = bins - item
    rem = np.maximum(rem, 0.0)          # clamp, job fits so already >= 0

    mx = rem.max(axis=1)                # tightest slack in either resource
    mn = rem.min(axis=1)                # slack in the other resource

    gamma = 0.0
    score = -mx + gamma * mn            # small & balanced leftover wins

    # Reserve: mildly discourage opening the brand-new (last) bin.
    new_bin_penalty = 0.05 * (cap[0] + cap[1])
    score = score - new_bin_penalty * (np.arange(bins.shape[0]) == bins.shape[0] - 1)

    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
