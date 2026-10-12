import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    post = np.maximum(b - it, 0.0)
    f = post / cap
    q = it / cap
    total = q[0] + q[1]
    w = q / total  # direction weights
    
    # term 1: overall fullness (fill fullest bin first)
    t1 = f[0] + f[1]
    # term 2: fill the dimension the item is heavy in
    t2 = w[0]*f[0] + w[1]*f[1]
    # term 3: complementarity — residual skewed toward the light dimension
    # (equivalently anti-alignment) — captured by t2 already? 
    score = -(0.4*t1 + 1.2*t2)
    return score
