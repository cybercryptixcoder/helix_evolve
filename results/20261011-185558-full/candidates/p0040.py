import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, float), 1.0)
    it = np.asarray(item, float)
    rem = np.asarray(bins, float)

    left = np.clip(rem - it, 0.0, None) / cap
    lc = left[:, 0]
    lm = left[:, 1]
    mx = np.maximum(lc, lm)
    mn = np.minimum(lc, lm)

    # base: best-fit in the binding (largest residual) dimension
    score = -1.6 * mx
    # reward keeping both dimensions available, saturating
    score += 0.5 * np.minimum(mn / 0.5, 1.0)
    # penalize imbalance, weighted by how loose the bin is
    score -= 0.6 * (mx - mn) * (1.0 - mx)

    return np.asarray(score, dtype=float)
