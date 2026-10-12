import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Demand fractions of the arriving job.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # Residual "hostability": can this leftover host a typical job?
    # Typical job ~ a quarter of capacity in each resource.
    typ = 0.25
    host = np.minimum(Lc / typ, 1.0) * np.minimum(Lm / typ, 1.0)

    # Tightness of the binding resource: reward nearly-filled bins.
    tight = np.minimum(np.minimum(d0 / np.maximum(Lc + d0, 1e-9),
                                   d1 / np.maximum(Lm + d1, 1e-9)), 1.0)

    # Balance of the leftover: even leftovers are more reusable.
    bal = 1.0 - np.abs(Lc - Lm)

    # Area term: prefer small leftover area (well packed).
    area = 1.0 - np.sqrt(Lc * Lm)

    # Complementarity: pair a skewed job with oppositely skewed leftover.
    skew = d0 - d1
    comp = 1.0 - np.abs(skew) * np.abs((Lm - Lc) - skew)

    # Combine multiplicatively so a bin must be good on several axes.
    score = (0.5 + 0.5 * tight) * (0.4 + 0.6 * host) * (0.5 + 0.5 * bal) \
            * (0.5 + 0.5 * area) * (0.7 + 0.3 * comp)

    # New-bin penalty: weaker for large jobs, stronger when item is small.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)
    score[-1] *= (0.80 + 0.20 * used)

    return score
