import numpy as np

def priority(item, bins, capacity):
    lc = bins[:, 0] - item[0]
    lm = bins[:, 1] - item[1]
    lc = np.maximum(lc, 0)
    lm = np.maximum(lm, 0)
    sq = lc * lc + lm * lm
    compact = lc + lm
    balance = np.abs(lc - lm)
    return -(sq + compact + balance)
