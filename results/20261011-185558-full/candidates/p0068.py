import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    # Leftover after placement, normalized to capacity.
    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # 1) Compactness via geometric mean of leftover: strongly penalizes any
    #    bin that keeps a large *residual block* in BOTH resources, while
    #    tolerating one oversized side (which is unavoidable sometimes).
    compact = -np.sqrt(lc * lm + 1e-12)

    # 2) Balance of the leftover shape.
    balance = -np.abs(lc - lm)

    # 3) Usability floor on the weaker side (keep bins alive for both types).
    weaker = np.minimum(lc, lm)
    usable = np.minimum(weaker * 2.5, 1.0)

    # 4) Fit quality: fraction of the bin's remaining the item consumes.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    score = 1.15 * fit + 0.95 * balance + 0.55 * compact + 0.30 * usable

    # Adaptive new-bin penalty ("regret"): only open a fresh bin when the
    # best existing option is genuinely bad. Compare the best non-new score
    # to the fresh bin's own score and penalize the fresh bin by the gap.
    if bins.shape[0] > 1:
        best_old = np.max(score[:-1])
        # fresh bin score before any penalty is roughly its own fit/balance
        score[-1] -= 0.10 + 0.35 * max(0.0, best_old - score[-1])
    else:
        score[-1] -= 0.10

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
