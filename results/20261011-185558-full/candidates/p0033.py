import numpy as np

def priority(item, bins, capacity):
    """
    Composite residual score:
      t = max normalised post-placement residual  -> penalise (best-fit on tight dim)
      u = min normalised post-placement residual  -> reward  (prefer balanced, roomy-other-dim fits)
    score = -alpha * t + beta * u
    """
    cap = np.asarray(capacity, dtype=float)
    x = np.asarray(item, dtype=float)

    # bins all fit the item, so this is >= 0 elementwise; capacity is > 0
    rem = (np.asarray(bins, dtype=float) - x) / cap

    a = rem[:, 0]
    b = rem[:, 1]
    t = np.maximum(a, b)
    u = np.minimum(a, b)

    score = -1.55 * t + 0.45 * u
    return score
