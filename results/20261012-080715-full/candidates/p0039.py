import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit + imbalance penalty, but scored on the *absolute*
    leftover instead of the residual-after-placement.

    The core keeps the tighter resource small (L-infinity). The bold change:
    instead of penalizing the leftover after the job is hypothetical placed
    (bins - item), we look at the bin's current free space relative to the
    item and reward bins that the item *almost* fills in the tight resource
    (good fit) while explicitly rewarding a strong directional match to the
    item so both resources drain together. A mild pull toward fuller bins
    (small total leftover) breaks ties toward compactness.
    """
    residual = bins - item
    # clamp tiny negatives (job guaranteed to fit, but stay safe)
    residual = np.maximum(residual, 0.0)

    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]

    tight = np.maximum(n_c, n_m)          # leftover of the binding resource
    imbalance = np.abs(n_c - n_m)         # lopsided leftover penalty

    # directional match: residual direction should oppose item direction,
    # i.e. a bin whose free space "faces" the arriving job drains evenly.
    r_norm = np.sqrt(residual[:, 0] ** 2 + residual[:, 1] ** 2)
    r_norm = np.where(r_norm > 0, r_norm, 1.0)
    i_norm = np.sqrt(item[0] ** 2 + item[1] ** 2)
    i_norm = i_norm if i_norm > 0 else 1.0
    align = (residual[:, 0] * item[0] + residual[:, 1] * item[1]) / (r_norm * i_norm)

    return -tight - 0.3569 * imbalance - 0.1453 * (n_c + n_m) - 0.30 * align
