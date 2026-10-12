import numpy as np


def priority(item, bins, capacity):
    """Smooth p-norm: score = -((n_c**p + n_m**p)**(1/p)), n = (bins - item) / capacity."""
    p = 4
    residual = bins - item
    n = residual / capacity
    return -((n[:, 0] ** p + n[:, 1] ** p) ** (1.0 / p))
