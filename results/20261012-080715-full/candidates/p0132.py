import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    nc = residual[:,0] / capacity[0]
    nm = residual[:,1] / capacity[1]
    fc = item[0] / capacity[0]
    fm = item[1] / capacity[1]

    # soft-max base (smooth best-fit): log-sum-exp of the leftover fractions
    # approximates -max(nc, nm), so the tightest-fitting bin scores highest.
    beta = 8.0
    a = beta * nc
    b = beta * nm
    m = np.maximum(a, b)
    sm = -(m + np.log(np.exp(a - m) + np.exp(b - m))) / beta
    return sm
