import numpy as np
import math

def priority(item, bins, capacity):
    item = np.asarray(item, dtype=float)
    bins = np.asarray(bins, dtype=float)
    cap  = np.asarray(capacity, dtype=float)

    # leftover room in each resource after placing the arriving job
    lc = np.maximum(bins[:, 0] - item[0], 0.0)
    lm = np.maximum(bins[:, 1] - item[1], 0.0)

    bottleneck = np.maximum(lc, lm)   # L-infinity leftover  -> tight-fit pressure
    spread     = np.abs(lc - lm)      # leftover imbalance   -> keep bins square
    scale      = cap[0] + cap[1] + 1e-9

    # complementarity: alignment of the job with the bin's remaining room
    ni  = math.hypot(item[0], item[1]) + 1e-9
    nr  = np.hypot(bins[:, 0], bins[:, 1]) + 1e-9
    dot = bins[:, 0] * item[0] + bins[:, 1] * item[1]
    align = dot / (ni * nr)           # in [0, 1] for non-negative inputs

    score = (-0.55 * (bottleneck / scale)
             - 0.20 * (spread / scale)
             + 0.25 * align)

    # discourage opening a brand-new bin unless it is clearly the best option
    new_bin = (bins[:, 0] >= cap[0] - 1e-9) & (bins[:, 1] >= cap[1] - 1e-9)
    score = score - 0.10 * new_bin

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
