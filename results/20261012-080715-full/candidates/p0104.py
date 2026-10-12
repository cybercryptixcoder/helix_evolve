import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:,0]/capacity[0]
    n_m = residual[:,1]/capacity[1]
    f_c = item[0]/capacity[0]
    f_m = item[1]/capacity[1]

    # base: power-mean fit (p=4) -> smoother than hard max, still close to L-inf
    p = 4.0
    base = -(n_c**p + n_m**p)**(1.0/p)

    imb = -0.5685*(n_c - n_m)**2
    shape = -0.179*((n_c - f_c) - (n_m - f_m))**2
    align = 0.3748*(n_c*f_c + n_m*f_m)
    # closing bonus (borrowed): reward bins that end nearly full
    close = 0.33*np.exp(-8.86*np.maximum(n_c, n_m))

    return base + imb + shape + align + close
