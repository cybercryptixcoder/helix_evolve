import numpy as np

def priority(item, bins, capacity):
    # Remaining capacity after hypothetically placing the item in each bin.
    rem = bins - item  # shape (k, 2)

    cap = capacity.astype(float)
    cap_safe = np.where(cap <= 0, 1.0, cap)

    # Normalize the item demand by capacity.
    di = item.astype(float) / cap_safe

    # Normalized leftover after placement (clipped at 0).
    nc = np.clip(rem[:, 0], 0.0, None) / cap_safe[0]
    nm = np.clip(rem[:, 1], 0.0, None) / cap_safe[1]

    # Dot product: rewards leaving capacity in the dimension the item did NOT use,
    # which pairs well with future complementary jobs (good for anticorr).
    dot = di[0] * nc + di[1] * nm

    # Small term that prefers balanced leftovers, to avoid creating dead corners.
    balance = -np.abs(nc - nm)

    # Prefer tighter fits slightly (smaller leftover after placement) among ties,
    # scaled small so it does not dominate the dot product.
    leftover = nc + nm

    score = dot + 0.05 * balance - 0.01 * leftover

    # The last row is a fresh empty bin; give it a mild bonus so that when
    # everything else is nearly full we don't jam items into dead bins.
    score = score.copy()
    score[-1] += 0.02

    return score
