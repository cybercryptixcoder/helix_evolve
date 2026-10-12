import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # --- Core: shape alignment (cosine between item demand and bin leftover).
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    dnorm = np.sqrt(d0 * d0 + d1 * d1) + 1e-9
    rnorm = np.sqrt(rem[:, 0] * rem[:, 0] + rem[:, 1] * rem[:, 1]) / cap[0] + 1e-9
    align = (d0 * rem[:, 0] / cap[0] + d1 * rem[:, 1] / cap[1]) / (dnorm * rnorm)

    # Binding-resource tightness: how close to full the harder dimension gets.
    fill = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Leftover evenness (a bin left lopsided is harder to reuse).
    bal = -np.abs(Lc - Lm)

    # Weak-side preservation, but softened so it doesn't dominate.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(1.5 * weak, 1.0)

    # Age preference: earlier bins slightly favoured to fill before opening.
    k = rem.shape[0]
    age = -np.arange(k, dtype=float) / max(k, 1)

    # Size-scaled fresh-bin penalty: big jobs shouldn't be scared off new bins.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.30 * fill
             + 0.80 * align
             + 0.70 * bal
             + 0.40 * usable
             + 0.05 * age)

    score[-1] -= 0.14 - 0.11 * used

    return score
