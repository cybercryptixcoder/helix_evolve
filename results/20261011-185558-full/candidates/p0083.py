import numpy as np


def priority(item, bins, capacity):
    """
    Best-fit score.

    For each candidate bin we look at how large a fraction of each remaining
    resource the arriving job would eat, and take the *smaller* of the two
    fractions -- i.e. the tightest dimension.  A bin whose binding dimension is
    almost exactly consumed by the job scores near 1 and is the best fit; a
    nearly empty bin scores small.  The fresh (last) row additionally gets a
    small penalty so that an equally good old bin is preferred.
    """
    item = np.asarray(item, dtype=np.float64)
    bins = np.asarray(bins, dtype=np.float64)

    # guard against zero/negative left-overs (jobs are strictly positive)
    it = np.maximum(item, 1e-9)
    rem = np.maximum(bins, 1e-9)

    # fraction of each remaining resource that the job would consume: (k, 2)
    frac = it[None, :] / rem

    # binding dimension -> how "tight" a fit this bin gives
    score = np.min(frac, axis=1)

    # slight surcharge for opening a brand-new bin
    score[-1] -= 0.05

    return score
