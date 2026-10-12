import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:,0]/capacity[0]
    n_m = residual[:,1]/capacity[1]
    f_c = item[0]/capacity[0]
    f_m = item[1]/capacity[1]
    align = 0.3228*(n_c*f_c + n_m*f_m)
    return -np.maximum(n_c,n_m) - 0.5558*(n_c-n_m)**2 - 0.2135*((n_c-f_c)-(n_m-f_m))**2 + align
