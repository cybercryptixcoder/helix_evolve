import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    it = item.astype(float)
    rem = bins.astype(float)

    after = rem - it
    after = np.maximum(after, 0.0)

    # worst-case leftover fraction: how much of the tighter resource remains
    W = 1.0 - np.minimum(after[:, 0] / cap[0], after[:, 1] / cap[1])

    # balance of the remaining bin
    bal = np.abs(after[:, 0] - after[:, 1]) / np.maximum(cap[0], cap[1])

    # volume term (geometric mean of leftover fractions)
    vol = -np.sqrt((after[:, 0] / cap[0]) * (after[:, 1] / cap[1]))

    score = -(1.0 * W) - 0.5 * bal + 0.3 * vol
    score = score + 0.02 * (1.0 - np.minimum(rem[:, 0] / cap[0], rem[:, 1] / cap[1]))

    return score.astype(float)
