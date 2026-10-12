import numpy as np

def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int    demand of the arriving job, [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of every open bin
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    returns:  np.ndarray, shape (k,), float

    Idea: score each candidate by the *shape* of what would be left after placing
    the job.  A leftover that is balanced (same fraction of cpu and memory free)
    can absorb either kind of future job, which is what keeps anticorrelated
    streams packable.  A mild best-fit term breaks ties toward the fullest bin
    and keeps brand-new bins (always the last row, largest leftover) from being
    opened while a decent old bin exists.
    """
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)

    # leftover after hypothetically placing the job in each open bin
    left = bins.astype(float) - item.astype(float)
    a = left[:, 0] / cap[0]
    b = left[:, 1] / cap[1]

    # balance: penalise inequality between the two free fractions
    balance = -np.abs(a - b)

    # best fit: prefer bins that end up fuller (less total free fraction)
    tight = -(a + b)

    # small preference for bins where the incoming item's skew matches the
    # bin's remaining skew cheaply -- keeps cpu-heavy jobs in cpu-rich bins
    # without ever forcing an obviously bad placement
    score = balance + 0.5 * tight

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=-1e12)
