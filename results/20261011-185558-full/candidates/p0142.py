import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap < 1e-9, 1.0, cap)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # residual left in each candidate bin after placing the item
    post = rem - it
    post = np.maximum(post, 0.0)
    r = post / cap  # normalized post-placement residual, shape (k, 2)

    # 1) tightness: bins that end up with little residual overall
    tight = -(r[:, 0] + r[:, 1])

    # 2) worst-dimension residual: keep the largest leftover small
    worst = -np.maximum(r[:, 0], r[:, 1])

    # 3) alignment: weight residual by the resource the item stresses more
    total = it[0] + it[1]
    if total > 1e-9:
        w = it / total
    else:
        w = np.array([0.5, 0.5])
    align = -(w[0] * r[:, 0] + w[1] * r[:, 1])

    # 4) balance: mildly punish very lopsided leftovers, easier to reuse later
    bal = -np.abs(r[:, 0] - r[:, 1])

    score = 3.0 * tight + 1.5 * worst + 1.0 * align + 0.4 * bal
    score = np.nan_to_num(score, nan=-1e18, posinf=1e18, neginf=-1e18)
    return score
