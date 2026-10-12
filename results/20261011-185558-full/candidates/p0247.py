import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    mc = np.maximum(rem[:, 0], 1e-9) / cap[0]
    mm = np.maximum(rem[:, 1], 1e-9) / cap[1]

    # Residual fractions after placement (>= 0).
    Lc = np.clip(mc - ic, 0.0, None)
    Lm = np.clip(mm - im, 0.0, None)

    # 1) Perfect-fit emphasis: reward exactly emptying the binding dimension.
    #    Binding dim = the one the item consumes a larger fraction of.
    if ic >= im:
        empty = np.exp(-25.0 * Lc)
    else:
        empty = np.exp(-25.0 * Lm)

    # 2) Residual alignment: the leftover should mirror the item's skew so the
    #    bin's remaining shape still matches the traffic that filled it.
    skew_item = ic - im
    skew_left = Lc - Lm
    align = -np.abs(skew_left - skew_item)

    # 3) Area and balance of the leftover (well-filled, square bin).
    area = -(Lc * Lm)
    bal = -np.abs(Lc - Lm)

    # 4) Weak-dimension survival: keep at least a small usable chunk.
    weak = np.minimum(np.minimum(Lc, Lm) * 2.0, 1.0)

    # 5) Tight fit in the binding dimension.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    score = (1.30 * empty
             + 0.90 * fit
             + 0.70 * align
             + 0.55 * area
             + 0.40 * bal
             + 0.30 * weak)

    # New-bin gate keyed on the item's *binding* dimension: big or skewed jobs
    # may legitimately need a fresh bin; small jobs should nearly always reuse.
    binding = max(ic, im)
    binding = min(max(binding, 0.0), 1.0)
    score[-1] -= 0.22 * (1.0 - binding) ** 2

    # Mild oldest-bin bias for consolidation.
    k = rem.shape[0]
    if k > 1:
        idx = np.arange(k, dtype=float)
        score = score - 1e-6 * idx

    return np.nan_to_num(score, nan=0.0, posinf=1e12, neginf=-1e12).reshape(-1)
