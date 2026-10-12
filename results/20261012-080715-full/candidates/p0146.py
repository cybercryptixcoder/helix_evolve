import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    n_c = residual[:,0]/capacity[0]
    n_m = residual[:,1]/capacity[1]
    f_c = item[0]/capacity[0]
    f_m = item[1]/capacity[1]

    # soft-max (log-sum-exp) approximates the binding residual, smooth version of
    # max(n_c,n_m) -> keeps best-fit character but differentiable/well-behaved
    a = 14.0
    sm = np.logaddexp(a*n_c, a*n_m)/a   # ~ max(n_c,n_m)
    # soft-min ~ min(n_c,n_m)
    smin = -np.logaddexp(-a*n_c, -a*n_m)/a

    base = -sm
    # waste penalty: also care about the loose direction being left large
    waste = -0.42*smin
    # balance
    imb = -0.55*(n_c-n_m)**2
    # shape match residual vs item
    shape = -0.20*((n_c-f_c)-(n_m-f_m))**2
    # alignment
    align = 0.30*(n_c*f_c + n_m*f_m)
    # exact-fill bonus, scaled by item size
    close = 0.33*np.exp(-9.0*sm)*(1.4-(f_c+f_m))
    return base+waste+imb+shape+align+close
