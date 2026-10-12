import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    rem = bins.astype(float) - item.astype(float)  # residual after placement, >= 0 for fitting bins
    np.clip(rem, 0.0, None, out=rem)
    a = rem[:, 0] / cap[0]
    b = rem[:, 1] / cap[1]
    total = a + b
    spread = np.abs(a - b)
    worst = np.maximum(a, b)
    score = -(0.6 * total + 0.4 * worst + 0.25 * spread)
    return score
