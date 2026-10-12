import numpy as np


def priority(item, bins, capacity):
    """
    Score each candidate bin by how well the arriving job fills it.

    item:     np.ndarray, shape (2,), int    [cpu, mem] demand
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem]; last row is empty bin
    capacity: np.ndarray, shape (2,), int    full capacity
    """
    cap = capacity.astype(float)[None, :]          # (1, 2)
    rem = bins.astype(float) - item.astype(float)  # (k, 2), >= 0 for fitting bins

    # Normalised leftover in each resource (0 .. 1)
    Lc = rem[:, 0] / cap[0, 0]
    Lm = rem[:, 1] / cap[0, 1]

    # How exhausted the tighter (binding) resource is after placement.
    fill_bind = 1.0 - np.maximum(Lc, Lm)

    # Area-based fill of the bin.
    fill_area = 1.0 - Lc * Lm

    # Balance: the leftover should be similar in both resources so the bin
    # can keep accepting jobs without wasting one resource.
    balance = 1.0 - np.abs(Lc - Lm)

    # Small residual norm => fuller bin (gentle tie-break).
    resid = np.sqrt(Lc * Lc + Lm * Lm)

    score = 0.6 * fill_bind + 0.4 * fill_area + 0.2 * balance - 0.1 * resid

    # Guarantee finiteness (should already hold, since capacities are positive).
    score = np.nan_to_num(score, nan=-1e9, posinf=1e9, neginf=-1e9)
    return score
