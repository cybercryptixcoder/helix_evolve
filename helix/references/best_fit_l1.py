# Best Fit (L1)
# The job goes into the bin it leaves with the least total room (normalised CPU + memory left).
# The standard online baseline for vector bin packing.
import numpy as np


def priority(item, bins, capacity):
    left = (bins - item) / capacity
    return -left.sum(axis=1)
