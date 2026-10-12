import numpy as np


def priority(item, bins, capacity):
    """Code Zero: every score is equal, so the oldest bin that fits wins = First Fit."""
    residual = bins - item
    return -np.maximum(residual[:, 0] / capacity[0], residual[:, 1] / capacity[1])
