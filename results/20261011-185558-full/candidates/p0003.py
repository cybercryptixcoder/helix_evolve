import numpy as np


def priority(item, bins, capacity):
    rem = bins.astype(np.float64)
    it = item.astype(np.float64)
    cap = capacity.astype(np.float64)

    # Residual space after placing the item (guard against zero)
    r0 = rem[:, 0] - it[0]
    r1 = rem[:, 1] - it[1]

    # Best-fit: prefer small residual (tight packing in both dims).
    # Normalise by capacity so the two resources are comparable.
    fit = (r0 / cap[0]) + (r1 / cap[1])

    # Balance: reward bins whose remaining shape matches the item's shape.
    # A bin that is lopsided in the same direction the item is lopsided
    # is a poor host; a bin that complements the item is a good host.
    item_ratio = it[0] / (it[0] + it[1] + 1e-9)
    bin_ratio = rem[:, 0] / (rem[:, 0] + rem[:, 1] + 1e-9)
    balance = -np.abs(item_ratio - bin_ratio)

    # Fullness: how much of the bin the item consumes, gently favouring
    # bins that are already more loaded (leave empty bins for later).
    used = (it[0] + it[1]) / (rem[:, 0] + rem[:, 1] + 1e-9)

    # New bin penalty: the last row is the fresh bin. Subtracting a term
    # proportional to its emptiness discourages opening unless needed.
    score = -fit + 0.6 * balance + 0.5 * used
    return score
