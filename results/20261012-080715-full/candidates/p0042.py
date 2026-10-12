import numpy as np

def priority(item, bins, capacity):
    residual = np.maximum(bins - item, 0.0)  # feasible so >=0, but guard
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    
    # soft L_inf via power mean with p=4
    p = 4.0
    soft_max = (0.5*(n_c**p + n_m**p))**(1.0/p)
    # imbalance using geometric-ish: penalize product being small relative to square
    imb = np.abs(n_c - n_m)
    
    return -soft_max - 0.45*imb
