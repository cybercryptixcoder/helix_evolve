# Dot product (Tetris-style alignment)
# Panigrahy et al. 2011; Grandl et al., "Multi-resource packing for cluster schedulers" (SIGCOMM 2014):
# prefer the open bin whose remaining room points the same way as the job, most strongly for the fullest bins.
import numpy as np


def priority(item, bins, capacity):
    d = item / capacity
    r = bins / capacity
    align = (r @ d) / (np.linalg.norm(r, axis=1) * np.linalg.norm(d) + 1e-12)
    fullness = 1.0 - r.sum(axis=1) / 2.0
    score = align + fullness
    score[-1] = -1.0          # a new bin only when no open bin fits
    return score
