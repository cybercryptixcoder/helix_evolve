import numpy as np


def priority(item, bins, capacity):
    """Norm-based greedy (normalised).

    Score each candidate bin by how balanced its *remaining* capacity is after
    the item is placed: keep the squared Euclidean norm of the residual small.
    Working in capacity-normalised units makes the two resources comparable and
    keeps the rule valid for any capacity, never hard-coding 100.

    residual = bins - item  (>= 0 by construction, so no division/NaN risk)
    score    = -( (res_cpu/cap_cpu)^2 + (res_mem/cap_mem)^2 )

    Best (highest) score -> the fitting bin whose two residuals are jointly
    smallest, which avoids stranding a bin with one resource fully exhausted.
    The fresh empty bin (last row) has the largest residual, so it is only
    chosen when no existing bin offers a tighter, better-balanced fit.
    """
    res = bins - item
    res = res / capacity            # normalise each resource by its capacity
    return -np.einsum('ij,ij->i', res, res)
