import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Leftover after placing the item, normalised by capacity.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Harmonic mean of leftovers: blows up (toward 0) if either resource is
    # nearly exhausted, so a bin that becomes unusable is heavily penalised.
    eps = 1e-6
    harm = (2.0 * Lc * Lm) / (Lc + Lm + eps)

    # Max leftover: how much "room to manoeuvre" remains in the looser dim.
    mx = np.maximum(Lc, Lm)

    # Fit: how tightly the item fills its binding dimension (well-filled bin).
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Prefer small harmonic leftover (tight, still-usable bin) and small max
    # leftover (don't leave a huge empty gap), plus tight fit.
    score = -(2.0 * harm + 0.6 * mx) + 0.9 * fit

    # Fresh-bin surcharge: discourage opening a new bin, but only mildly for
    # large jobs where no old bin would be a good fit anyway.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.18 - 0.14 * used

    return score
