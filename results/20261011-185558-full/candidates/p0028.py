import numpy as np

def priority(item, bins, capacity):
    # Remaining capacity after placing the job, normalised to [0, 1] per resource.
    cap = np.asarray(capacity, dtype=float)
    rem = (bins - item).astype(float) / cap
    np.clip(rem, 0.0, 1.0, out=rem)

    # The binding resource (max remaining) and the scarcer resource (min remaining).
    maxr = rem.max(axis=1)
    minr = rem.min(axis=1)

    # Base: prefer the fullest bin that still fits (smallest max remaining).
    # Concave bonus on the scarcer resource: steep marginal value while it is
    # small (<= 0.5), flat afterwards, so bins that are lopsided are punished.
    score = -maxr + 0.45 * minr + 0.7 * np.minimum(minr, 0.5)

    return score
