# Helix v3 policy: scheduling, gap 13.828%, progress 98.6%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 projected_finish_relative_to_mean (wide): Relative predicted-tardiness: projected finish time of this job on each machine divided by the mean projected 
def _f002(job, loads, past_jobs, jobs_left):
    """Relative predicted-tardiness: projected finish time of this job on each machine divided by the mean projected finish time, using an estimate of remaining work per machine from past jobs."""
    m = len(loads)
    if past_jobs.size > 0:
        mean_past = float(np.mean(past_jobs))
    else:
        mean_past = job
    # expected remaining work per machine from future jobs
    remaining_work = jobs_left * mean_past
    per_machine_future = remaining_work / m
    proj = loads + job + per_machine_future
    ref = float(np.mean(proj))
    if ref <= 1e-12:
        return np.zeros(m)
    return (proj - ref) / (abs(ref) + 1e-9)

# f005 load_rank_blended_with_remaining_work_deficit (wide): Fraction of remaining work that would land on each machine if future jobs followed the empirical size distribu
def _f005(job, loads, past_jobs, jobs_left):
    """Fraction of remaining work that would land on each machine if future jobs followed the empirical size distribution, measured as the gap between the machine's load and where an equalising stream would put it."""
    m = len(loads)
    t = len(past_jobs)
    # current load rank position of each machine
    order = np.argsort(np.argsort(loads)).astype(float)
    pos = order / max(m - 1, 1)  # 0 = lightest, 1 = heaviest
    # remaining jobs and mean size; estimate remaining work
    mean_size = float(np.mean(past_jobs)) if t > 0 else job
    remaining_work = mean_size * jobs_left
    # how much each machine must still absorb if work were spread perfectly evenly
    share = (loads + job) - (loads.sum() + job) / m
    # blend: a light machine needs more future work; weight its deficit by remaining work scale
    denom = remaining_work / m + 1e-9
    deficit = -share / denom
    # combine with rank position so heavy machines are penalised strongly
    return np.clip(0.5 * pos + 0.5 * np.tanh(deficit), -1.0, 1.0)

# f039 size_gated_slack_decay_penalty (wide): For large arriving jobs: negative of the machine's slack below the current max load, scaled by job size, so bi
def _f039(job, loads, past_jobs, jobs_left):
    """For large arriving jobs: negative of the machine's slack below the current max load, scaled by job size, so big jobs avoid the front-runners and spread toward mid-loaded machines."""
    m = len(loads)
    if past_jobs.size > 0:
        big = float(np.max(past_jobs))
        med = float(np.median(past_jobs))
    else:
        big = float(job)
        med = float(job)
    scale = big + 1e-9
    # gate: how "large" this job is relative to the observed tail, in [0,1]
    gate = np.clip((job - med) / scale, 0.0, 1.0)
    maxload = float(np.max(loads))
    # slack of each machine below the heaviest load, normalised
    slack = (maxload - loads) / scale
    # penalise machines close to the max (little slack) when the job is big
    return -gate * np.exp(-4.0 * slack)

_TERMS = [(_f002, np.array([-1.611442])), (_f005, np.array([-2.205818])), (_f039, np.array([5.830833]))]

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
