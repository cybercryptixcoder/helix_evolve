import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    it = item.astype(float)
    rem = bins.astype(float)

    after = rem - it  # >= 0 in both coords for rows passed in

    # fit: how snugly the item uses the tighter remaining dimension
    denom = np.maximum(rem, 1.0)
    fit = np.minimum(it[0] / denom[:, 0], it[1] / denom[:, 1])

    # balance of leftover: prefer residuals whose two dims are close
    af = after / np.maximum(cap, 1.0)
    balance = -np.abs(af[:, 0] - af[:, 1])

    # usable: reward bins that stay generally useful (both dims left)
    usable = np.minimum(2.0 * af[:, 0], 1.0) * np.minimum(2.0 * af[:, 1], 1.0)

    # compact: penalize large total leftover (prefer filling bins)
    compact = -(af[:, 0] + af[:, 1])

    # fill2: reward completely emptying the tighter dimension
    fill2 = np.minimum(after[:, 0] / np.maximum(it[0], 1.0),
                       after[:, 1] / np.maximum(it[1], 1.0))

    score = (1.1 * fit
             + 0.9 * balance
             + 0.35 * usable
             + 0.30 * compact
             + 0.25 * fill2)

    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
