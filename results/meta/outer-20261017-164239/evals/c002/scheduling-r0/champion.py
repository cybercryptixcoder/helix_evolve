# Helix v3 policy: scheduling, gap 11.242%, progress 98.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 projected_final_load_deficit (wide): Deficit of a machine's post-placement load below the projected final average load.
def _f001(job, loads, past_jobs, jobs_left):
    """Deficit of a machine's post-placement load below the projected final average load."""
    m = len(loads)
    mean_past = float(past_jobs.mean()) if past_jobs.size > 0 else float(job)
    # projected total work = assigned so far + this job + expected remaining work
    target = (float(loads.sum()) + float(job) + float(jobs_left) * mean_past) / m
    denom = abs(target) + abs(float(job)) + 1e-9
    vals = (target - (loads + float(job))) / denom
    return np.clip(np.nan_to_num(vals, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)

# f012 horizon_blended_target_fit (wide): Horizon-blended fit to the projected final average load: deficit below it while the run is young, two-sided di
def _f012(job, loads, past_jobs, jobs_left):
    """Horizon-blended fit to the projected final average load: deficit below it while the run is young, two-sided distance to it when few jobs remain."""
    m = len(loads)
    t = int(past_jobs.size)
    mean_past = float(past_jobs.mean()) if t > 0 else float(job)
    # projected total work = assigned so far + this job + expected remaining work
    target = (float(loads.sum()) + float(job) + float(jobs_left) * mean_past) / m
    post = loads + float(job)
    denom = abs(target) + abs(float(job)) + 1e-9
    # share of the instance already seen, in [0, 1): 0 at the first job
    a = t / (t + float(jobs_left) + 1.0)
    deficit = (target - post) / denom            # parent: rank = least loaded
    dist = -np.abs(post - target) / denom        # late: hug the fair-share water level
    vals = (1.0 - a) * deficit + a * dist
    return np.clip(np.nan_to_num(vals, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)

# f013 asymmetric_level_hinge_by_job_size (wide): Two columns: (1) an asymmetric hinge around a level that blends the projected final per-machine share with the
def _f013(job, loads, past_jobs, jobs_left):
    """Two columns: (1) an asymmetric hinge around a level that blends the projected final per-machine share with the current bottleneck load, where the pull from below shrinks and the penalty from above grows as the arriving job gets large relative to the typical job; (2) a penalty for leaving a machine more than one typical job below that level (wasted slack)."""
    loads = np.asarray(loads, dtype=float)
    job = float(job)
    m = loads.size

    # --- projected fair-share level -------------------------------------
    total = float(loads.sum()) + job
    n = int(past_jobs.size)
    if n > 0:
        mean_job = (float(past_jobs.sum()) + job) / (n + 1)
        sd_job = float(np.std(past_jobs))
    else:
        mean_job = job
        sd_job = 0.0
    mean_job = max(mean_job, 1e-9)
    sd_job = max(sd_job, 0.0)

    share = (total + float(jobs_left) * mean_job) / m
    maxload = float(loads.max())
    level = 0.5 * (share + (share if share >= maxload else maxload))
    scale = abs(level) + job + mean_job + 1e-9

    after = loads + job

    # --- column 0: size-conditioned asymmetric hinge --------------------
    big = job / (job + mean_job)                      # 0 = tiny job, 1 = huge job
    w_over = 0.5 + 0.5 * big                          # big jobs: never widen the bottleneck
    w_under = 0.5 - 0.5 * big                         # small jobs: fill toward the level
    over = np.maximum(after - level, 0.0) / scale
    under = np.maximum(level - after, 0.0) / scale
    col0 = -(w_over * over + w_under * under)

    # --- column 1: don't strand a machine far below the level -----------
    band = max(mean_job, sd_job)                      # one typical job of tolerable slack
    col1 = -np.maximum((level - band) - after, 0.0) / scale

    out = np.stack([col0, col1], axis=1)
    out = np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=-1.0)
    return np.clip(out, -1.0, 1.0)

# f017 reserve_pool_for_future_big_jobs (deep): Reserve-pool signal: +1 for non-reserved machines, -1 for machines needed as a future-big-job pool, zero when 
def _f017(job, loads, past_jobs, jobs_left):
    """Reserve-pool signal: +1 for non-reserved machines, -1 for machines needed as a future-big-job pool, zero when no reserve is needed or the current job is big."""
    loads = np.asarray(loads, dtype=float)
    m = loads.size
    zeros = np.zeros(m, dtype=float)
    past = np.asarray(past_jobs, dtype=float)

    if past.size < 8 or m < 2:
        return zeros

    scale = float(np.partition(past, past.size // 4)[past.size // 4])
    scale = max(scale, 1e-9)
    big = 4.0 * scale

    if job > big:
        return zeros

    frac_big = float(np.mean(past > big))
    R = int(np.clip(round(jobs_left * frac_big), 0, m - 2))
    if R < 1:
        return zeros

    cut = float(np.partition(loads, R - 1)[R - 1])
    s = 0.05 * (abs(cut) + scale) + 1e-9
    return np.clip(np.tanh((loads - cut) / s), -1.0, 1.0)

_TERMS = [(_f001, np.array([1.230428])), (_f012, np.array([4.135641])), (_f013, np.array([7.988421, -2.087575])), (_f017, np.array([0.125201]))]

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
