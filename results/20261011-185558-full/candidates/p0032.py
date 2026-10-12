import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    rem = bins.astype(float)
    # residual fractions of each resource, per open bin
    frac = rem / cap                      # shape (k, 2)
    a = frac[:, 0]
    b = frac[:, 1]

    s = a + b                             # overall slack
    d = np.abs(a - b)                     # imbalance of the leftover

    # bonus that rewards bins whose tighter resource is still usable
    mn = np.minimum(a, b)
    theta = 0.5
    usable = np.minimum(mn / theta, 1.0)

    # balance dominates, compactness is a light tie-breaker, usable adds a bonus
    score = -0.9 * d - 0.1 * s + usable

    # safety: no NaN / inf can appear, but clamp anyway
    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
