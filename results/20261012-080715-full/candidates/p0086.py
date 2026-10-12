import numpy as np


def priority(item, bins, capacity):
    """Variant of the best program: keep L-infinity best-fit core but
    make two bold changes.

    1) Replace the hard max with a smooth p-norm of the residual vector.
       The p-norm agrees with max on the *binding* resource, but it also
       penalises a large residual in the *non-binding* resource. That is
       exactly the 2D vector-packing lever: placing an item in a bin that
       leaves one whole dimension almost empty wastes that resource and
       creates a bin which only skewed future jobs can use. Grading
       "both dimensions tight" is strictly more informative than max, and
       collapses to max when the two residuals are equal.

    2) Scale the imbalance penalty by the item's hardness (its binding
       demand fraction), so demanding jobs - which decide the bin count -
       get strong pressure toward balanced leftovers, while tiny jobs are
       placed by pure best-fit. A mild density term rewards fuller bins.
    """
    residual = bins - item                    # >= 0 for every candidate
    n_c = residual[:, 0] / capacity[0]        # normalised residual CPU
    n_m = residual[:, 1] / capacity[1]        # normalised residual memory
    f_c = item[0] / capacity[0]               # normalised item demand
    f_m = item[1] / capacity[1]

    # (1) smooth max via p-norm, normalised so that a residual of (t, t)
    # still maps to t (keeps the scale comparable to plain max)
    p = 6.0
    base = -((n_c ** p + n_m ** p) / 2.0) ** (1.0 / p)

    hardness = np.maximum(f_c, f_m)

    # (2) imbalance penalty, stronger for demanding items
    imb = -(0.55 + 0.45 * hardness) * (n_c - n_m) ** 2

    # mild density bonus: prefer packing into already-full bins
    dens = -0.10 * (n_c + n_m)

    # shape penalty: residual "free-space shape" should match the item shape
    shape = -0.19 * ((n_c - f_c) - (n_m - f_m)) ** 2

    # alignment reward: residual pointing along the item's aspect ratio
    align = 0.30 * (n_c * f_c + n_m * f_m)

    return base + imb + dens + shape + align
