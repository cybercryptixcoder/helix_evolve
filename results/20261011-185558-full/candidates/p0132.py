import numpy as np

def priority(item, bins, capacity):
    it = np.asarray(item, dtype=np.float64)
    b = np.asarray(bins, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)
    eps = 1e-9

    rem = np.maximum(b - it, 0.0)          # residual after placement
    rn = rem / cap                          # normalized residual

    # 1) tightness: prefer bins the item fits into snugly (best fit)
    fit = np.min(it / np.maximum(b, eps), axis=?)
