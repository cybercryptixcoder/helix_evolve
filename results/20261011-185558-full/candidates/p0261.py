import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # residuals after hypothetically placing the item
    Lc = rem[:, 0] - it[0]
    Lm = rem[:, 1] - it[1]

    # normalised residuals (1 = empty, 0 = exactly full)
    nc = Lc / cap[0]
    nm = Lm / cap[1]

    # fit: reward filling the bin tightly (small residual); guard against negatives
    fit = 1.0 - (nc + nm) * 0.5
    fit = np.clip(fit, -1.0, 1.0)

    # balance: penalise lopsided residuals (absolute difference)
    bal = -np.abs(nc - nm)

    # geometric mean: strongly prefer bins that keep both resources usable
    geom = -np.sqrt(np.clip(nc, 0.0, None) * np.clip(nm, 0.0, None))

    # usable: reward leaving a healthy amount of both resources free
    usable = np.minimum(np.clip(nc, 0.0, 1.0), np.clip(nm, 0.0, 1.0))

    # accept: bonus when both residuals stay above a small threshold
    accept = np.minimum(np.clip((nc - 0.10) / 0.30, 0.0, 1.0),
                        np.clip((nm - 0.10) / 0.30, 0.0, 1.0))

    # item shape: balanced items care more about balance, lopsided items about fit
    diff = abs(it[0] / cap[0] - it[1] / cap[1])
    comp = 0.42 * diff

    score = (1.05 * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + comp * bal)

    # never allow a non-fitting bin (shouldn't happen, but be safe)
    valid = (Lc >= 0.0) & (Lm >= 0.0)
    score = np.where(valid, score, -1e9)

    return score
