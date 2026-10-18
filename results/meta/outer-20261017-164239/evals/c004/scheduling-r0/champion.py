# Helix v3 policy: scheduling, gap 13.616%, progress 98.6%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 post_placement_excess_over_mean (wide): Relative load of each machine after hypothetically placing the job, measured against the mean of the m largest
def _f004(job, loads, past_jobs, jobs_left):
    """Relative load of each machine after hypothetically placing the job, measured against the mean of the m largest possible future contributions."""
    m = len(loads)
    total = float(np.sum(loads)) + job
    # target average load if we could perfectly balance all work seen so far
    avg = total / m
    post = loads + job
    # how far above the target each machine would sit after the placement
    excess = post - avg
    scale = float(np.mean(past_jobs)) if past_jobs.size else job
    scale = max(scale, 1e-9)
    return -excess / (scale + job)

# f039 gated_k_emptiest_reservation_step (deep): Step penalty (-1) on the k emptiest post-load machines, gated by heavy-tailed past sizes and a non-giant arriv
def _f039(job, loads, past_jobs, jobs_left):
    """Step penalty (-1) on the k emptiest post-load machines, gated by heavy-tailed past sizes and a non-giant arriving job."""
    m = len(loads)
    post = loads + job
    t = past_jobs.size
    out = np.zeros(m)
    if t < 20 or jobs_left <= 0:
        return out
    med = np.median(past_jobs)
    mx = np.max(past_jobs)
    gate = min(max((mx / (med + 1e-9) - 15.0) / 30.0, 0.0), 1.0)
    if gate == 0.0:
        return out
    frac_g = np.mean(past_jobs > 5.0 * med)
    exp_g = frac_g * jobs_left
    k = int(min(round(exp_g), m - 1))
    if k < 1:
        return out
    small = 1.0 if job <= 2.0 * med else 0.0
    order = np.argsort(post, kind='stable')
    out[order[:k]] = -1.0
    return gate * small * out

_TERMS = [(_f004, np.array([0.160659])), (_f039, np.array([2.342534]))]

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
