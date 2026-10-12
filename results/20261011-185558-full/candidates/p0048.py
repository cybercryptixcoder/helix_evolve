import numpy as np

def priority(item, bins, capacity):
    # Normalize everything by capacity so the rule is scale-free.
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    a = it[0] / cap[0]
    b = it[1] / cap[1]

    # Remaining fraction in each resource for every candidate bin.
    rc = rem[:, 0] / cap[0]
    rm = rem[:, 1] / cap[1]

    # Residual after placement (fractions). Guard against negatives from float noise.
    lc = np.clip(rc - a, 0.0, None)
    lm = np.clip(rm - b, 0.0, None)

    # The "useful" side of the residual is the smaller one: that resource can
    # still be filled by future items. The larger residual is largely dead if
    # the other side is already tight.
    mn = np.minimum(lc, lm)
    mx = np.maximum(lc, lm)

    # Reward tight fits (small min) and penalize lopsided dead space (large max,
    # especially when the min side is already small).
    score = -mn - 0.6 * mx * (1.0 - mn)

    # Bonus for placements that leave a bin nearly perfectly balanced empty,
    # which tends to pair well with complementary future items.
    balance = 1.0 - np.abs(lc - lm)
    score = score - 0.15 * (1.0 - balance)

    # The last row is a fresh bin: nudge it slightly so a genuinely good fit in
    # an existing bin still wins, but a near-empty existing bin does not beat
    # opening fresh.
    score[-1] = score[-1] + 0.02

    return score
