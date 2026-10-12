import numpy as np


def priority(item, bins, capacity):
    """
    Score open bins for the arriving job.

    Idea (kept from the previous attempt):
      * compactness  : prefer bins that end up well filled in BOTH resources
                       (low normalised leftover after placement),
      * usable       : reward a healthy minimum leftover in both dims, but
                       saturate at half a bin so very empty bins get no edge,
      * balance      : penalise a lopsided leftover, since a skewed bin is a
                       dead end for the opposite kind of job.
    All three are computed in capacity-normalised units, so the rule works for
    any capacity vector, not just [100, 100].
    """
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Guard against a zero capacity component (division safety).
    cap_safe = np.where(cap > 0.0, cap, 1.0)

    # Leftover after hypothetically placing the job in each bin.
    after = np.maximum(rem - it, 0.0)
    fc = after[:, 0] / cap_safe[0]
    fm = after[:, 1] / cap_safe[1]

    # 1) Compactness: drive the total normalised leftover towards zero.
    compact = -(fc + fm)

    # 2) Usable: reward a minimum leftover in both dims, saturating at 0.5.
    usable = np.minimum(np.minimum(fc, fm) * 2.0, 1.0)

    # 3) Balance: punish an imbalanced leftover.
    balance = -np.abs(fc - fm)

    score = 1.0 * compact + 0.7 * usable + 0.5 * balance

    # Safety: replace any non-finite entry (should never happen) with -inf-free.
    score = np.nan_to_num(score, nan=-1e9, posinf=1e9, neginf=-1e9)
    return score
