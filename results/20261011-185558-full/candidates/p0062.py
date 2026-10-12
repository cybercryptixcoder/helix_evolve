import numpy as np


def priority(item, bins, capacity):
    """
    Greedy "compact & balanced" leftover score.

    For a candidate bin, let lc, lm be the remaining CPU / memory after the
    arriving job is placed.  We use the coupling quantity

        f = (lc^2 + lm^2) / (lc + lm)
          = s/2 + d^2/(2s),   s = lc + lm,  d = lc - lm

    which is small exactly when the leftover is *tight* (small total s) and
    *square* (small imbalance d) -- i.e. it simultaneously consolidates load
    and keeps the residual bin usable for future jobs.  We return -f so the
    highest score corresponds to the smallest f.

    When lc = lm = 0 (perfect exact fit) the expression is 0/0; we set f = 0
    there (the safest possible guard, and the best possible score).
    """
    rem = np.asarray(bins, dtype=np.float64) - np.asarray(item, dtype=np.float64)

    lc = rem[:, 0]
    lm = rem[:, 1]

    s = lc + lm
    # Where s == 0 we must have lc == lm == 0, so the numerator is also 0;
    # substituting 1.0 keeps the division well defined and gives f = 0.
    denom = np.where(s > 0.0, s, 1.0)

    f = (lc * lc + lm * lm) / denom
    return -f
