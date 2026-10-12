import numpy as np


def priority(item, bins, capacity):
    """L-infinity fit + imbalance penalty, but with a soft "best-fit" bonus
    that depends on how tightly the item's shape matches the bin's leftover.

    Core idea kept: -max(n_c, n_m) keeps the tighter resource in view and the
    quadratic imbalance term discourages lopsided leftovers. Bold change:
    instead of a fixed penalty, the imbalance cost is scaled by how lopsided
    the *item* is, and we add a concave (sqrt) reward for filling the tighter
    resource more completely. This makes the rule adaptive: for balanced jobs
    we care mostly about the max-residual fit, while for skewed jobs we let
    the naturally skewed bins win without over-penalizing them.
    """
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]

    # how lopsided is the arriving item (0 = balanced, 1 = fully skewed)
    ic = item[0] / capacity[0]
    im = item[1] / capacity[1]
    skew = np.abs(ic - im) / (ic + im + 1e-12)

    # concave reward for draining the tighter resource (rewards tight fits
    # without the linear term's over-aggression on the looser resource)
    tight = np.maximum(n_c, n_m)
    fit_bonus = np.sqrt(np.clip(1.0 - tight, 0.0, 1.0))

    # adaptive imbalance penalty: strong for balanced items, weak for skewed
    imbalance = np.abs(n_c - n_m)
    penalty = (0.45 * (1.0 - skew) + 0.10 * skew) * imbalance

    return -tight - penalty + 0.30 * fit_bonus - 0.05 * (n_c + n_m)
