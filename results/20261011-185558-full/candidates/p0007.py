import numpy as np


def priority(item, bins, capacity):
    cap = capacity.astype(float)
    b = bins.astype(float)
    it = item.astype(float)

    rem = b - it  # leftover after placing item; some entries may be negative (they don't fit)

    # Normalised leftover in each resource, clipped at 0.
    r0 = np.clip(rem[:, 0], 0.0, None) / cap[0]
    r1 = np.clip(rem[:, 1], 0.0, None) / cap[1]

    # Shape balance: 1 when both leftovers are equal, ->0 when one is empty.
    lo = np.minimum(r0, r1)
    hi = np.maximum(r0, r1)
    balance = lo / (hi + 1e-9)

    # Prefer bins where the smaller leftover resource is still reasonably large,
    # so we don't strand a bin that can only accept tiny jobs.
    min_left = np.minimum(r0, r1)

    # Penalise using up most of a resource the item is heavy in.
    item_frac = it / cap
    heavy = np.maximum(item_frac[0], item_frac[1])
    tight_pen = heavy * (1.0 - min_left)

    score = 0.6 * balance + 0.4 * min_left - 0.5 * tight_pen

    # The last row is the new bin; give it a modest baseline so it wins only
    # when every open bin is a bad shape fit.
    score[-1] = 0.30

    return score
