import numpy as np


def priority(item, bins, capacity):
    rem = bins.astype(float)
    cap = capacity.astype(float)
    item = item.astype(float)

    after = rem - item
    # Slack after placing: how much of each resource would remain.
    slack = np.clip(after, 0.0, None)

    # Scarcity weight: resources that are scarce overall in open bins matter more.
    # Fraction of total open capacity still free in each dimension.
    total = rem.sum(axis=0) + 1e-9
    free_frac = total / (cap * max(len(bins), 1))
    # Weight is larger for the tighter (less free) resource.
    w = 1.0 / (free_frac + 0.05)

    # Best-fit: small leftover is good. Use normalized leftover per dimension.
    tight = (slack / (cap + 1e-9)) * w
    score = -(tight[:, 0] + tight[:, 1])

    # Strongly prefer filling near-perfectly in either dimension.
    fill = np.clip(after / (cap + 1e-9), 0.0, None)
    score -= 0.5 * np.min(fill, axis=1)

    # Penalise opening a fresh bin (last row) slightly unless nothing fits well.
    score[-1] -= 0.15

    return score
