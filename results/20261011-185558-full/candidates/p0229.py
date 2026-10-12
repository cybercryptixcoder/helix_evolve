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

    # Normalised demands.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]

    # Tightness in the max-norm: how close the item comes to filling the
    # binding resource, but measured jointly so both matter.
    tight = np.maximum(it[0] / rc, it[1] / rm)
    tight = np.minimum(tight, 1.0)

    # Wasted area of the resulting leftover rectangle (smaller is better).
    # Use sqrt so large leftovers are penalised more gently.
    waste = np.sqrt(Lc * Lm)

    # Usability: a bin is only useful if the leftover can host *some* future
    # job.  Reward the minimum leftover, but only up to the size of a typical
    # job so we don't over-reward huge empty bins.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(weak / 0.25, 1.0)

    # Complementarity: a skewed job should go where leftover is skewed the
    # opposite way, so the two fill each other's weak spot.
    comp = (dc - dm) * (Lm - Lc)

    # Penalty for opening a new bin: strong for small jobs, weak for big.
    used = 0.5 * (dc + dm)
    used = min(max(used, 0.0), 1.0)

    # Anti-domination: if the leftover rectangle is smaller than the item in
    # both resources, the bin is nearly useless for anything but tiny jobs.
    dominated = (Lc < dc) & (Lm < dm)

    score = (1.10 * tight
             - 0.75 * waste
             + 0.45 * usable
             + 0.30 * comp
             - 0.35 * dominated.astype(float))

    score[-1] -= 0.14 - 0.10 * used

    return score
