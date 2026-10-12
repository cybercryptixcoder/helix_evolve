import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap <= 0.0, 1.0, cap)
    it = np.asarray(item, dtype=float)
    itn = it / cap

    # Residual capacity of each bin after hypothetically placing the item.
    r = np.maximum(np.asarray(bins, dtype=float) - it, 0.0)
    a = r[:, 0] / cap[0]
    b = r[:, 1] / cap[1]

    M = np.maximum(a, b)   # binding residual (worst-fit dimension left over)
    m = np.minimum(a, b)   # slack dimension

    # Alignment of the remaining (pre-placement) capacity with the item's shape.
    u = np.asarray(bins, dtype=float) / cap
    nu = np.sqrt(u[:, 0] * u[:, 0] + u[:, 1] * u[:, 1])
    ni = np.sqrt(itn[0] * itn[0] + itn[1] * itn[1])
    denom = nu * ni
    safe = denom > 0.0
    cos = np.where(
        safe,
        (u[:, 0] * itn[0] + u[:, 1] * itn[1]) / np.where(safe, denom, 1.0),
        0.0,
    )

    score = (
        -1.00 * M                 # primary: tightest fit on the binding resource
        - 0.35 * (a + b)          # compactness: fill volume
        - 0.50 * (M - m)          # balance penalty: avoid lopsided leftovers
        + 0.25 * np.minimum(2.0 * m, 1.0)  # keep some usability in both dims
        + 0.15 * cos              # prefer bins shaped like the arriving job
    )

    # Mild penalty for opening a brand-new bin (last row) when a fit exists.
    score = score.copy()
    score[-1] -= 0.05

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
