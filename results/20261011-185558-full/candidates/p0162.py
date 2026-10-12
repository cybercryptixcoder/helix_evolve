import numpy as np

def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int    demand of the arriving job, [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of every open bin the job fits in
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    """
    rem = np.asarray(bins, dtype=float)
    it = np.asarray(item, dtype=float)
    cap = np.asarray(capacity, dtype=float)

    # Guard against zero/negative residuals: never divide by 0.
    rem_safe = np.maximum(rem, 1.0)

    # Tightest-dimension fit: how much of the scarcer remaining dimension the
    # job consumes. Large only when the bin is snug along its tightest axis.
    fit = np.minimum(it[0] / rem_safe[:, 0], it[1] / rem_safe[:, 1])

    # Tiny tie-break: among equal fits prefer the tighter (less remaining) bin,
    # so roomy bins stay available for future jobs.
    tie = -rem_safe[:, 0] - rem_safe[:, 1]

    score = fit * 1e6 + tie * 1e-6

    # Safety: guarantee finite output.
    score = np.nan_to_num(score, nan=-1e18, posinf=1e18, neginf=-1e18)
    return score
