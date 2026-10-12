import numpy as np


def priority(item, bins, capacity):
    rem = np.asarray(bins, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)

    ic = it[0]
    im = it[1]
    rc = np.maximum(rem[:, 0], 0.0)
    rm = np.maximum(rem[:, 1], 0.0)

    # Fraction of each remaining resource the job consumes.
    # A dimension that is already exhausted contributes a full ratio.
    fc = np.where(rc > 0.0, ic / np.maximum(rc, 1.0), 1.0)
    fm = np.where(rm > 0.0, im / np.maximum(rm, 1.0), 1.0)
    fit = np.minimum(fc, fm)                       # tight fit in the binding dim

    tight = (ic + im) / np.maximum(rc + rm, 1.0)   # overall 1D-style tightness

    lc = np.maximum(rc - ic, 0.0)
    lm = np.maximum(rm - im, 0.0)
    tot = lc + lm
    bal = 1.0 - np.abs(lc - lm) / np.maximum(tot, 1.0)   # leftover stays balanced

    capsum = cap[0] + cap[1]
    compact = 1.0 - tot / np.maximum(capsum, 1.0)        # little residual overall

    norm_r = np.sqrt(rc * rc + rm * rm)
    norm_i = np.sqrt(ic * ic + im * im)
    align = (rc * ic + rm * im) / np.maximum(norm_r * norm_i, 1e-9)  # shape match

    return 2.0 * fit + 0.8 * tight + 0.6 * bal + 0.6 * compact + 0.5 * align
