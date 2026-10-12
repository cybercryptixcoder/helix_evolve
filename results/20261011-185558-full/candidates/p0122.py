import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    it = item.astype(float)
    rem = bins.astype(float)

    after = rem - it  # >= 0 for all fitting bins
    ac = after[:, 0] / cap[0]
    am = after[:, 1] / cap[1]

    linf = np.maximum(ac, am)
    l1 = ac + am
    bal = np.abs(ac - am)

    # New bin is the last row (equal to capacity).
    is_new = np.zeros(rem.shape[0], dtype=bool)
    is_new[-1] = True

    score = -(1.0 * linf + 0.55 * l1 + 0.45 * bal)

    # Age: slight preference for older bins (earlier rows) to consolidate.
    k = rem.shape[0]
    if k > 1:
        age = (k - 1 - np.arange(k)) / (k - 1)  # 1 for oldest, 0 for newest
        score += 0.02 * age

    # New-bin penalty baseline (in addition to its computed fit).
    score[is_new] -= 0.05

    return score
