# Helix v3 policy: scheduling, gap 10.964%, progress 98.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f009 reserve_emptiest_machine (deep): Column 0: negative normalised load deviation (ordinary balance); column 1: -1 on machines at the current minim
def _f009(job, loads, past_jobs, jobs_left):
    """Column 0: negative normalised load deviation (ordinary balance); column 1: -1 on machines at the current minimum load when the job is below the past mean and more than m jobs remain, else 0."""
    mu = float(past_jobs.mean()) if past_jobs.size else job
    ls = loads
    mn = ls.min()
    mx = ls.max()
    base = -(ls - ls.mean()) / (mx - mn + job + 1e-9)
    reserve = -1.0 * (((ls <= mn + 1e-9) & (job < mu) & (jobs_left > len(ls))).astype(float))
    return np.column_stack([base, reserve])

# f001 relative_load_deficit (wide): Negative current load normalised by mean load plus a fraction of the job: favours the currently least-loaded m
def _f001(job, loads, past_jobs, jobs_left):
    """Negative current load normalised by mean load plus a fraction of the job: favours the currently least-loaded machine, scaled to the job size."""
    m = len(loads)
    mean_load = float(np.mean(loads))
    scale = mean_load + job + 1e-9
    # relative deficit of each machine, blended with the job-size pressure
    return (-(loads - mean_load) / scale)

_TERMS = [(_f009, np.array([2.495433, 3.804898])), (_f001, np.array([1.036666]))]

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
