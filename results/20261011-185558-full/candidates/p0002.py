import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # leftover after placing the item (bins shown already fit, so >= 0)
    left = rem - it

    # Guard denominators
    cap_safe = np.maximum(cap, 1.0)
    left_safe = np.maximum(left, 1e-9)

    # fraction of each resource still free after placement
    frac = left_safe / cap_safe

    # Bottleneck fit: the smaller free fraction dominates how "full" the bin is.
    # Tighter fit (small bottleneck fraction) is preferred -> we negate.
    bottleneck = np.min(frac, axis=1)

    # Imbalance penalty: leftover room that is lopsided wastes future flexibility.
    imbalance = np.abs(frac[:, 0] - frac[:, 1])

    # Prefer bins that end up tight overall but balanced; big penalty for
    # leaving a lot of free room (wasted capacity).
    score = -bottleneck - 0.5 * imbalance

    # Mildly discourage opening a brand-new bin unless it's clearly best:
    # an empty bin leaves frac ~ 1, so it naturally scores low, which is fine.
    return score
