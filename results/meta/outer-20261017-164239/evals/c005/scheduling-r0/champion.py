# Helix v3 policy: scheduling, gap 11.655%, progress 98.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 equalizing_slack_ratio (wide): Slack of each machine relative to the average eventual load if the remaining work were spread evenly.
def _f003(job, loads, past_jobs, jobs_left):
    """Slack of each machine relative to the average eventual load if the remaining work were spread evenly."""
    m = len(loads)
    past = np.asarray(past_jobs, dtype=float)
    done = past.sum() if past.size else 0.0
    # remaining jobs: this one plus jobs_left; estimate future work from observed mean
    mean_past = done / past.size if past.size else job
    remaining_work = job + jobs_left * mean_past
    target = (done + remaining_work) / m  # ideal equal final load
    denom = target if target > 1e-9 else 1.0
    return (target - loads) / denom

# f013 rank_tilted_slack (wide): Slack of each machine relative to a target that weights machines by their current load rank: later-idle machin
def _f013(job, loads, past_jobs, jobs_left):
    """Slack of each machine relative to a target that weights machines by their current load rank: later-idle machines get more slack, early-loaded ones less, using an exponential tilt on load rank."""
    m = len(loads)
    past = np.asarray(past_jobs, dtype=float)
    done = past.sum() if past.size else 0.0
    mean_past = done / past.size if past.size else job
    remaining_work = job + jobs_left * mean_past
    target = (done + remaining_work) / m
    denom = target if target > 1e-9 else 1.0
    slack = (target - loads) / denom
    # rank of each machine by current load (0 = least loaded); tilt so lightly loaded
    # machines are rewarded more strongly once many jobs remain
    order = np.argsort(np.argsort(loads)).astype(float)
    tilt = (order - (m - 1) / 2.0) / (m / 2.0 if m > 1 else 1.0)
    horizon = jobs_left / (jobs_left + 1.0)
    return np.tanh(slack) * (1.0 + horizon * tilt)

# f023 top_two_spread_delta (wide): Relative reduction in the largest pairwise load gap if this machine gets the job: measures whether placing her
def _f023(job, loads, past_jobs, jobs_left):
    """Relative reduction in the largest pairwise load gap if this machine gets the job: measures whether placing here avoids widening the top-two spread."""
    m = len(loads)
    loads = np.asarray(loads, dtype=float)
    if m < 2:
        return np.zeros(m)
    new = loads + job
    # current spread relevant to the worst machine: gap between largest and smallest load
    lo = loads.min()
    top2 = np.sort(loads)[-2:]
    # after placing on candidate i, recompute top-two spread of the resulting load vector
    # vectorised: new sorted top-two spread approximated by the two largest of (new, other loads)
    # other loads = loads with candidate removed -> for each i, the largest among loads[j!=i]
    second_of_others = np.where(np.arange(m) == np.argmax(loads), np.sort(loads)[-2], loads.max())
    new_top = np.maximum(new, second_of_others)
    new_second = np.minimum(new, second_of_others)
    spread_after = new_top - new_second
    spread_before = top2[1] - top2[0]
    denom = spread_before if spread_before > 1e-9 else 1.0
    return np.tanh((spread_before - spread_after) / denom)

# f032 leader_isolation_margin (wide): Confidence of the largest loaded machine staying dominant: negative of its post-load minus the second-largest 
def _f032(job, loads, past_jobs, jobs_left):
    """Confidence of the largest loaded machine staying dominant: negative of its post-load minus the second-largest post-load, but only when this candidate is that largest machine; otherwise small positive tie-breaker by post-load rank."""
    m = len(loads)
    loads = np.asarray(loads, dtype=float)
    if m < 2:
        return np.zeros(m)
    new = loads + job
    s = np.sort(new)
    top, second = s[-1], s[-2]
    # margin by which the eventual max exceeds the runner-up if this candidate were the max
    margin = (top - second)
    scale = top if top > 1e-9 else 1.0
    is_top = (new >= top - 1e-12)
    # penalise making the leader stick out; small reward for being the runner-up region
    base = -(margin / scale)
    out = np.where(is_top, base, 0.5 * base)
    return np.tanh(out)

_TERMS = [(_f003, np.array([3.012787])), (_f013, np.array([2.881795])), (_f023, np.array([2.011829])), (_f032, np.array([17.764675]))]

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
