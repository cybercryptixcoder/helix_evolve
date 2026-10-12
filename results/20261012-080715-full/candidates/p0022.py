import numpy as np


def priority(item, bins, capacity):
    """Fresh idea: "seal-and-abandon" scoring via a sum-of-squares of the
    *fractional fill* in the tighter dimension, plus an explicit reward for
    fully using a bin in one resource.

    Instead of measuring how much room is LEFT (all the shown programs do that),
    measure how CLOSE the bin is to being sealed in its tightest resource.
    A bin whose tighter resource is nearly exhausted is a "finished" bin and
    should be preferred, because it will soon leave the pool; a bin that is
    still half-empty in its tighter resource is a waste of a whole machine.

    For each candidate bin after placement:
        f_c = (cap_c - res_c) / cap_c   in [0,1]  fractional fill, cpu
        f_m = (cap_m - res_m) / cap_m   in [0,1]  fractional fill, mem
        t   = max(f_c, f_m)             the tighter resource's fill
    Score = t  -  small * (1 - min(f_c,f_m)) * slack_penalty

    The dominant term t rewards sealing. The correction discourages leaving
    the *other* resource nearly untouched when the tight one is full, which
    would strand capacity for jobs that need that other resource.

    The fresh empty bin has t = max(item/cap) which is small for small jobs,
    so it is only chosen when no open bin is close to sealed -- a genuinely
    different decision rule from Best-Fit / norm-based greedy.
    """
    res = bins - item                          # >= 0 for every candidate row
    cap = capacity.astype(float)

    # fractional FILL (not leftover) in each resource, clipped for safety
    fc = 1.0 - res[:, 0] / cap[0]
    fm = 1.0 - res[:, 1] / cap[1]
    np.clip(fc, 0.0, 1.0, out=fc)
    np.clip(fm, 0.0, 1.0, out=fm)

    tight = np.maximum(fc, fm)                 # the fuller (tighter) resource
    loose = np.minimum(fc, fm)                 # the emptier resource

    # reward sealing the tight resource; mildly penalise a very empty other side
    score = tight - 0.25 * (1.0 - loose) * tight
    return score
