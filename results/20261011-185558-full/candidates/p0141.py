import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # pre-placement availability
    Bc = rem[:,0]/cap[0]
    Bm = rem[:,1]/cap[1]

    rc = np.maximum(rem[:,0], 1e-9)
    rm = np.maximum(rem[:,1], 1e-9)

    # post-placement normalised residuals
    Lc = np.clip(rem[:,0]-it[0], 0.0, None)/cap[0]
    Lm = np.clip(rem[:,1]-it[1], 0.0, None)/cap[1]

    x = it[0]/cap[0]
    y = it[1]/cap[1]

    fit = np.minimum(np.minimum(it[0]/rc, it[1]/rm), 1.0)

    tot = Lc + Lm + 1e-9
    relbal = 1.0 - np.abs(Lc-Lm)/tot   # in [0,1]

    geom = -np.sqrt(Lc*Lm)
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0*weak, 1.0)

    # pairing: item's dominant resource should match bin's abundant resource
    d = x - y
    b = Bc - Bm
    pair = np.clip(d*b, -1.0, 1.0)

    used = np.clip(0.5*(x+y), 0.0, 1.0)

    score = (1.1*fit + 0.6*relbal + 0.5*geom + 0.55*usable
             + 0.35*pair + (0.15+0.1*used)*np.minimum(2*Lc,1)*np.minimum(2*Lm,1))
    score[-1] -= 0.16 - 0.12*used
    return score
