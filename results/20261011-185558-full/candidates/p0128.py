import numpy as np

def priority(item, bins, capacity):
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)
    cap = np.asarray(capacity, dtype=float)
    
    ic, im = it[0], it[1]
    Cc, Cm = cap[0], cap[1]
    rc = rem[:, 0]
    rm = rem[:, 1]
    
    # residuals after placement (>= 0 because item fits)
    ac = np.maximum(rc - ic, 0.0) / Cc
    am = np.maximum(rm - im, 0.0) / Cm
    
    # dot-product heuristic term, normalized
    denom = ic * Cc + im * Cm
    if denom <= 0:
        denom = 1.0
    d = (ic * rc + im * rm) / denom
    
    score = -1.0 * d - 0.5 * np.abs(ac - am) - 0.25 * (ac + am)
    return score
