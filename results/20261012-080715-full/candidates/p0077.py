import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:,0]/capacity[0]
    n_m = residual[:,1]/capacity[1]
    f_c = item[0]/capacity[0]
    f_m = item[1]/capacity[1]
    hard = np.maximum(f_c,f_m)
    base = -np.maximum(n_c,n_m) - 0.35*np.minimum(n_c,n_m)   # volume-aware best fit
    imb = -(0.5685 + 0.3*hard)*(n_c-n_m)**2
    shape = -0.19*((n_c-f_c)-(n_m-f_m))**2
    align = 0.30*(n_c*f_c + n_m*f_m)
    return base+imb+shape+align
