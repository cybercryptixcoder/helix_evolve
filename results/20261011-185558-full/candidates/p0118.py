import numpy as np

def priority(item, bins, capacity):
    c = np.maximum(capacity.astype(np.float64), 1.0)
    b = bins.astype(np.float64)
    it = item.astype(np.float64)

    # leftover capacity in each resource after placing the job
    dc = b[:, 0] - it[0]
    dm = b[:, 1] - it[1]
    rc = np.clip(dc / c[0], 0.0, 1.0)
    rm = np.clip(dm / c[1], 0.0, 1.0)

    rmin = np.minimum(rc, rm)
    rmax = np.maximum(rc, rm)

    # best fit: bin ends up as full as possible
    fill = 1.0 - 0.5 * (rc + rm)
    # balance: square residuals stay usable for both job types
    bal = 1.0 - (rmax - rmin)
    # sliver killer: eat that thin strip so it is not stranded
    sliver = 1.0 - rmin
    # usable room left in the fatter dimension
    room = 1.0 - rmax

    # how big is the arriving job, normalized to capacity
    size = 0.5 * (it[0] / c[0] + it[1] / c[1])
    size = min(max(size, 0.0), 1.0)

    score = ((0.90 + 0.50 * size) * fill
             + 0.70 * bal
             + (0.50 - 0.25 * size) * sliver
             + 0.15 * room)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
