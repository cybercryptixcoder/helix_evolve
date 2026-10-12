import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    k = b.shape[0]

    need = it / cap
    rem = b / cap
    after = rem - need

    score = -(after[:, 0] + after[:, 1])
    comp = (need[0] - need[1]) * (rem[:, 0] - rem[:, 1])
    score = score + 0.2 * comp

    if k > 1:
        used = 1.0 - 0.5 * (rem[:-1, 0] + rem[:-1, 1])
        roomy = max(0.0, 1.0 - float(np.mean(used)))
        margin = 0.05 + 0.30 * roomy
        score[-1] = score[-1] - margin

    return score.astype(float)
