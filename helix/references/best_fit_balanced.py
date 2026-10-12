# Best Fit with balance
# Tight fit plus even leftovers, so the bin stays useful for jobs of either shape (a common refinement
# in VM-placement work).
import numpy as np


def priority(item, bins, capacity):
    left = (bins - item) / capacity
    return -left.sum(axis=1) - np.abs(left[:, 0] - left[:, 1])
