import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised demand of the arriving job.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    dnorm = np.sqrt(d0 * d0 + d1 * d1) + 1e-12

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # 1) Tightness: prefer the bin the item nearly fills (binding resource).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Small leftover area (well-filled bin) -- strong best-fit pressure.
    area = Lc + Lm

    # 3) Shape matching: align the residual leftover direction with the
    #    *transpose* of the item direction, so a CPU-heavy job leaves a
    #    memory-heavy bin (and vice versa). This is what stops resources
    #    from being stranded on anticorr / bimodal families.
    Lnorm = np.sqrt(Lc * Lc + Lm * Lm) + 1e-12
    # transposed item direction
    tc = d1 / dnorm
    tm = d0 / dnorm
    shape = (Lc * tc + Lm * tm) / Lnorm   # in [-1, 1]
    shape = shape * np.minimum(Lnorm * 2.0, 1.0)  # fade when leftover tiny

    # 4) Balance of leftover (prefer even, so neither resource dies).
    bal = -np.abs(Lc - Lm)

    # 5) Usable weaker resource: keep a floor of slack for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Scale of the job: big jobs should be less afraid of a fresh bin.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.30 * fit
             - 0.90 * area
             + 0.70 * shape
             + 0.90 * bal
             + 0.35 * usable)

    # Fresh-bin handicap: modest, and fades for larger jobs.
    score[-1] -= 0.22 - 0.18 * used

    return np.asarray(score, dtype=float).reshape(-1)
