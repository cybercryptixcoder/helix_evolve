import numpy as np
import math

def priority(item, bins, capacity):
    # remaining space after placing the item in each bin
    rem = bins - item  # shape (k, 2)

    # balance term: prefer bins whose post-placement leftover is balanced
    Lc = rem[:, 0]
    Lm = rem[:, 1]
    # a bin is "good" if its weaker leftover is large
    weak = np.minimum(Lc, Lm)

    # fill term: prefer packing into bins that are already more used (tighter fit)
    # usage fraction after placement
    used = (capacity[None, :] - rem) / np.maximum(capacity[None, :], 1.0)
    fill = used[:, 0] + used[:, 1]

    # matching term: how well leftover shape matches the item demand shape
    # avoid division by zero
    denom = np.maximum(rem[:, 0] + rem[:, 1], 1.0)
    match = (Lc + Lm) / denom  # = 1 always; placeholder removed below

    # core score: balance + slight fill preference
    score = weak.astype(float) + 0.25 * fill.astype(float)

    # New-bin penalty based on roominess of the best existing bin.
    if bins.shape[0] > 1:
        existing_weak = weak[:-1]
        best_g = float(np.max(existing_weak))
        # if an existing bin stays roomy after placement, penalize opening new
        # scale penalty by capacity to stay capacity-agnostic
        cap_min = float(np.min(capacity))
        penalty = best_g * 1.5 + 0.5 * cap_min
        score[-1] = score[-1] - penalty
    # else only one row (the empty bin): leave as is

    # ensure finite
    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
