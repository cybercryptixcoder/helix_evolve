# Best Fit (L-infinity)
# The bin whose larger leftover (CPU or memory) after placing the job is smallest.
import numpy as np


def priority(item, bins, capacity):
    left = (bins - item) / capacity
    return -left.max(axis=1)
