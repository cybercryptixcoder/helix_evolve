import numpy as np


def priority(item, bins, capacity):
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)

    after = np.maximum(rem - it, 0.0)
    a = after[:, 0] / cap[0]          # leftover cpu fraction
    b = after[:, 1] / cap[1]          # leftover mem fraction

    # Direction of the arriving job in normalized space.
    d = it / cap
    dn = np.sqrt(d[0] * d[0] + d[1] * d[1]) + 1e-12
    ux, uy = d[0] / dn, d[1] / dn

    # Projection of leftover onto the item direction: how much of the
    # leftover lies "ahead" of the job (bad) vs perpendicular (good).
    proj = a * ux + b * uy
    perp = np.abs(a * uy - b * ux)

    # Total leftover magnitude.
    mag = np.sqrt(a * a + b * b) + 1e-12

    # Reward perpendicular residual strips, penalize residual piled along
    # the job's own direction, and discourage overall waste.
    align = proj / mag                    # 0 = perfect strip, 1 = aligned
    score = -(0.6 * align + 0.9 * mag + 0.25 * (a + b))

    # Bonus: leftover is essentially zero in one axis -> clean corner.
    clean = np.minimum(a, b)
    score += 0.15 * np.exp(-8.0 * clean)

    # Slight preference to keep the brand-new bin as a last resort.
    score[-1] -= 0.04

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
