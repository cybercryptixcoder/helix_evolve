import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    # Post-placement residual, normalized.
    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # --- Idea: score how "self-similar" the residual is to the item shape.
    # A residual proportional to the item means the bin can keep absorbing
    # jobs of this same shape with no waste -> the bin is not getting lopsided.
    ic = it[0] / cap_safe[0]
    im = it[1] / cap_safe[1]
    # ratio of residual to item demand in each dimension (guarded)
    rc = lc / np.maximum(ic, 1e-6)
    rm = lm / np.maximum(im, 1e-6)
    # reward when the two ratios are equal (residual is a scaled item)
    shape = -np.abs(rc - rm)

    # --- Waste: prefer using up room, but weight by the *tighter* side so a
    # nearly-exhausted dimension is not over-rewarded.
    used = 1.0 - np.maximum(lc, lm)          # how full the tighter side is
    slack = np.minimum(lc, lm)               # the roomiest-side leftover

    # --- Bottleneck risk: a bin with one side near zero is a dead end for
    # mixed future traffic; penalize the smaller residual strongly.
    dead = 1.0 - np.minimum(np.minimum(lc, lm) * 4.0, 1.0)

    score = 1.30 * shape + 0.85 * used - 0.55 * slack - 0.90 * dead

    # New-bin handling: penalize the empty bin by how under-utilized the
    # arriving job would leave it (big jobs fill it -> cheap to open; small
    # jobs waste it -> expensive). Empty row is exactly `capacity`.
    empty = cap_safe
    waste = 1.0 - np.maximum(it[0] / empty[0], it[1] / empty[1])
    score[-1] -= 0.30 * waste + 0.02

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
