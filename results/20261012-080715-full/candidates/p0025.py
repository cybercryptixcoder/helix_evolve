import numpy as np


def priority(item, bins, capacity):
    """Code Zero + new-bin penalty: score = -max(n_c, n_m), with a constant
    penalty of 0.05 subtracted from the last row (the empty new bin) so it only
    wins when no fitting open bin is at least as good."""
    residual = bins - item
    score = -np.maximum(residual[:, 0] / capacity[0], residual[:, 1] / capacity[1])
    score[-1] -= 0.05
    return score
