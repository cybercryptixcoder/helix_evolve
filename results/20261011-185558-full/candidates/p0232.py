import numpy as np

def priority(item, bins, capacity):
    rc = bins[:, 0].astype(np.float64)
    rm = bins[:, 1].astype(np.float64)
    it0 = float(item[0])
    it1 = float(item[1])
    Cc = max(float(capacity[0]), 1.0)
    Cm = max(float(capacity[1]), 1.0)

    Lc = rc - it0          # >= 0 because the item fits
    Lm = rm - it1
    lc = Lc / Cc           # normalised leftover in [0, 1]
    lm = Lm / Cm

    # 1. tightness: how much of the binding remaining resource this job consumes
    r0 = it0 / np.maximum(rc, 1.0)
    r1 = it1 / np.maximum(rm, 1.0)
    fit = np.minimum(r0, r1)

    # 2. balance of the leftover
    bal = -np.abs(lc - lm)

    # 3. small leftover-product = well packed
    geom = -np.sqrt(np.maximum(lc, 0.0) * np.maximum(lm, 0.0))

    # 4. usable square of free space (room for a future job)
    usable = np.minimum(lc, lm)

    # 5. can a typical future job still fit?
    accept = ((lc >= 0.2) & (lm >= 0.2)).astype(np.float64)

    # 6. complementary skew: leave the *other* resource free
    s0 = it0 + it1
    skew = (it0 - it1) / s0 if s0 > 0 else 0.0
    comp = skew * (Lm - Lc) / (Cc + Cm)

    used = 1.0 - np.minimum(lc, lm)
    fit_w = 1.05 + 0.25 * used

    score = (fit_w * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.35 * comp
             - 0.20 * (lc + lm))

    # discourage opening the brand-new bin; less so when the open bins are already full
    if len(bins) > 1:
        mean_used = float(np.mean(used[:-1]))
    else:
        mean_used = 0.0
    newpen = 0.16 - 0.12 * mean_used + 0.06 * skew
    score[-1] -= newpen

    # safety: finite values only
    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
