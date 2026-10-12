import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    it = item.astype(float)
    rem = bins.astype(float) - it  # leftover after placing, shape (k, 2)

    # Estimate which resource is currently scarcer using the already-open bins.
    if bins.shape[0] > 1:
        open_bins = bins[:-1].astype(float)
    else:
        open_bins = bins.astype(float)

    mean_open = open_bins.mean(axis=0)
    a = mean_open[0] / cap[0] + 1e-9  # normalised avg remaining cpu
    b = mean_open[1] / cap[1] + 1e-9  # normalised avg remaining mem

    # Less remaining -> scarcer -> bigger weight on that resource's leftover.
    w_cpu = 1.0 / a
    w_mem = 1.0 / b
    tot = w_cpu + w_mem
    w_cpu /= tot
    w_mem /= tot

    u = rem[:, 0] / cap[0]
    v = rem[:, 1] / cap[1]

    # Minimise weighted leftover in the scarce resource -> tightly packed scarce resource.
    score = -(w_cpu * u + w_mem * v)
    return score
