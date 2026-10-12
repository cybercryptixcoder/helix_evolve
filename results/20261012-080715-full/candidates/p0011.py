import numpy as np

def priority(item, bins, capacity):
    # Best-Fit variant: prefer the bin that, after placing the job, leaves the
    # least normalized free space, with a mild preference for square (balanced)
    # leftovers so future jobs of either shape still fit.
    left = bins - item                      # remaining after placement (>=0)
    cap = capacity.astype(float)
    n_c = left[:, 0] / cap[0]
    n_m = left[:, 1] / cap[1]
    # L1 best fit + balance term
    score = -(n_c + n_m) - 0.3 * np.abs(n_c - n_m)
    return score
