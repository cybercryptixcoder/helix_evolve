import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the job.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tightness: how much of the binding resource the job consumes.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Joint viability: a bin is only useful if BOTH leftovers stay usable.
    # Use a soft-min (geometric mean) so a zero in either resource kills it.
    weak = np.sqrt(np.maximum(Lc, 0.0) * np.maximum(Lm, 0.0))

    # Balance: reward even leftover profiles (less fragmentation).
    bal = -np.abs(Lc - Lm)

    # Complementarity: if the job is CPU-heavy, prefer bins with spare memory.
    d0, d1 = it[0] / cap[0], it[1] / cap[1]
    comp = (d0 - d1) * (Lm - Lc)

    # Combined score: tightness dominates, viability + balance shape the rest.
    score = 1.20 * fit + 0.95 * weak + 0.55 * bal + 0.45 * comp

    # Adaptive new-bin gate: penalise opening fresh bins when existing bins
    # are still roomy, but relax it for large jobs that need space.
    used = min(max(0.5 * (d0 + d1), 0.0), 1.0)
    if len(bins) > 1:
        fill_existing = float(np.median(1.0 - np.minimum(Lc[:-1], Lm[:-1])))
    else:
        fill_existing = 0.0
    newpen = (0.22 - 0.16 * used) * (1.0 - fill_existing)
    score[-1] -= max(newpen, 0.0)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
