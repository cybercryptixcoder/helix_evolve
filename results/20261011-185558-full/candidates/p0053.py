import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=np.float64), 1.0)
    it = np.asarray(item, dtype=np.float64).reshape(2)
    rem = np.asarray(bins, dtype=np.float64)
    if rem.ndim == 1:
        rem = rem.reshape(1, 2)
    k = rem.shape[0]

    # fraction of each resource left in every bin after placing the job
    left = np.clip((rem - it) / cap, 0.0, None)
    lc = left[:, 0]
    lm = left[:, 1]

    # --- scarcity weights from the current open bins (exclude fresh bin) ---
    if k > 1:
        avg = np.clip(rem[:-1], 0.0, None).mean(axis=0) / cap
    else:
        avg = np.array([0.5, 0.5])

    # a resource that is on average scarcer among open bins gets more weight
    w = np.clip(1.0 - avg, 1e-3, None)
    w = w / w.sum()

    # tightest fit in the scarce direction (fresh bin never wins on this term)
    tight = -(w[0] * lc + w[1] * lm)

    # mild nudge towards leftovers that are balanced in both resources
    bal = -0.25 * np.maximum(lc, lm)

    score = tight + bal
    return np.where(np.isfinite(score), score, -1e18)
