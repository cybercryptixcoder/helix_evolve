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

    # 1. How much of the binding resource this job consumes (tight fit).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2. Residual magnitude: prefer small total leftover (well-packed bin).
    mag = -np.sqrt(Lc * Lc + Lm * Lm)

    # 3. Residual aspect balance: leftover should be square-ish, not a sliver.
    s = Lc + Lm
    aspect = 1.0 - np.abs(Lc - Lm) / np.maximum(s, 1e-9)

    # 4. Both-resources-alive floor (room for a typical future job).
    weak = np.minimum(Lc, Lm)
    alive = np.minimum(2.0 * weak, 1.0)

    # Job size (normalised) drives the new-bin gate.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = 0.5 * (d0 + d1)

    score = 1.10 * fit + 0.60 * mag + 0.55 * aspect + 0.30 * alive

    # Multiplicative gate: existing bins are damped only mildly; the fresh
    # bin is suppressed strongly for small jobs and only lightly for big ones.
    gate = 1.0 - 0.30 * (1.0 - used) ** 2
    score = score * gate

    # Fresh-bin extra suppression: near-total for small jobs, vanishing for
    # jobs that are a large fraction of a bin.
    score[-1] -= 0.22 * (1.0 - used) ** 2

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
