import numpy as np


def priority(item, bins, capacity):
    c = float(item[0])
    m = float(item[1])
    C = float(capacity[0])
    M = float(capacity[1])

    rc = bins[:, 0].astype(float)
    rm = bins[:, 1].astype(float)

    # Normalised post-placement residuals (fits guaranteed, so >= 0).
    pc = (rc - c) / C
    pm = (rm - m) / M

    # Weight residuals by the arriving job's own resource mix.
    s = c + m
    if s <= 0.0:
        wc = 0.5
        wm = 0.5
    else:
        wc = c / s
        wm = m / s

    # Residual along the job's demand direction: small = tight, on-axis fit.
    wr = wc * pc + wm * pm
    # Overall leftover capacity: small = the bin ends up well filled.
    tr = pc + pm
    # Skew of the leftover: a lopsided bin is a good future host for the
    # lopsided jobs that dominate anticorr / bimodal traffic.
    skew = np.abs(pc - pm)
    # How loaded the bin already is (0 = empty, 2 = full): reuse beats opening.
    used = (1.0 - rc / C) + (1.0 - rm / M)

    score = -(1.0 * wr + 0.40 * tr) - 0.10 * skew + 0.02 * used
    return score
