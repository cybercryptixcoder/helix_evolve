import numpy as np

def priority(item, bins, capacity):
    # ---- normalised leftover after placing this job (>=0 for every candidate) ----
    residual = bins - item
    nc = residual[:, 0] / capacity[0]      # remaining CPU fraction
    nm = residual[:, 1] / capacity[1]      # remaining MEM fraction
    fc = item[0] / capacity[0]             # item CPU fraction
    fm = item[1] / capacity[1]             # item MEM fraction

    # (1) TIGHTNESS: instead of a hard max (pure best-fit), use a p-norm
    #     "soft max" of the two leftovers. p between 1 (sum) and inf (max)
    #     lets the two resources share the decision when they are close,
    #     which avoids over-committing to one dimension.
    p = 4.0
    tight = -(nc ** p + nm ** p) ** (1.0 / p)

    # (2) BALANCE: squared aspect drift of the leftover -> prefer squarish bins
    bal = -0.60 * (nc - nm) ** 2

    # (3) SHAPE DRIFT: leftover shape should echo the job's shape
    shape = -0.20 * ((nc - fc) - (nm - fm)) ** 2

    # (4) COMPLEMENTARITY: residual pointing along the job's aspect ratio
    comp = 0.30 * (nc * fc + nm * fm)

    # (5) CLOSING: reward finishing a bin (near-zero binding leftover),
    #     gated so that big jobs are not dumped into already-tight slivers
    close = 0.33 * np.exp(-8.0 * np.maximum(nc, nm)) * (1.40 - np.maximum(fc, fm))

    return tight + bal + shape + comp + close
