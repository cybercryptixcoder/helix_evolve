# Helix v3 policy: scheduling, gap 7.017%, progress 99.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 relative_job_size_below_mean_slack (wide): Gap between the least-loaded machine and the mean load, scaled by the arriving job's relative size.
def _f003(job, loads, past_jobs, jobs_left):
    """Gap between the least-loaded machine and the mean load, scaled by the arriving job's relative size."""
    m = len(loads)
    mean_load = np.mean(loads)
    # relative size of the arriving job compared to typical work still to come
    if jobs_left > 0:
        horizon = mean_load / (m * jobs_left + 1.0)  # rough per-job-per-machine scale
    else:
        horizon = mean_load / m if mean_load > 0 else 1.0
    rel = job / (horizon + 1e-9)
    rel = rel / (1.0 + rel)  # squash to (0,1)
    slack = (mean_load - loads) / (mean_load + 1e-9)  # positive for below-average machines
    return rel * slack

# f045 tiny_fraction_gate_fill_to_current_max (deep): Gated tiny-job packing: tiny-dominated history scores machines whose post-load stays under the current max loa
def _f045(job, loads, past_jobs, jobs_left):
    """Gated tiny-job packing: tiny-dominated history scores machines whose post-load stays under the current max load, higher for fuller machines."""
    if past_jobs.size < 5:
        return np.zeros(loads.shape[0])
    Q = np.quantile(past_jobs, 0.9)
    if Q <= 0:
        return np.zeros(loads.shape[0])
    tiny_frac = np.mean(past_jobs <= 0.25 * Q)
    g = 1.0 / (1.0 + ((1.0 - tiny_frac) / 0.2) ** 4)
    C = max(np.max(loads), job)
    if C <= 0:
        return np.zeros(loads.shape[0])
    post = loads + job
    diff = (post - C) / C
    base = np.where(post <= C, diff, -2.0 - diff)
    return g * base

# f044 tiny_avoid_large_job_machines (deep): Negative tiny-job gate on machines whose post-assignment load exceeds the 0.9-quantile of past jobs.
def _f044(job, loads, past_jobs, jobs_left):
    """Negative tiny-job gate on machines whose post-assignment load exceeds the 0.9-quantile of past jobs."""
    if past_jobs.size == 0:
        return np.zeros(loads.shape[0], dtype=float)
    Q = float(np.quantile(past_jobs, 0.9))
    if Q <= 0.0:
        return np.zeros(loads.shape[0], dtype=float)
    ratio = job / (0.25 * Q)
    ratio = min(ratio, 1e6)
    g = 1.0 / (1.0 + ratio ** 4)
    return (-g * (loads + job > Q)).astype(float)

_TERMS = [(_f003, np.array([0.304484])), (_f045, np.array([1317.399893])), (_f044, np.array([-25.869756]))]

def priority(job, loads, past_jobs, jobs_left):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(job, loads, past_jobs, jobs_left), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(loads))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
