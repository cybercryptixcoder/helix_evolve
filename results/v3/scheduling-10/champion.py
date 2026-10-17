# Helix v3 policy: scheduling, gap 7.025%, progress 99.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f011 size_gated_spread_vs_fill (deep): Two gated columns: big jobs spread to the emptiest machine (-normalised load), small jobs best-fit under the e
def _f011(job, loads, past_jobs, jobs_left):
    """Two gated columns: big jobs spread to the emptiest machine (-normalised load), small jobs best-fit under the estimated final average T."""
    m = loads.shape[0]
    mean_past = past_jobs.mean() if past_jobs.size else job
    T = max((loads.sum() + job + jobs_left * mean_past) / m, 1e-9)
    x = loads + job
    xn = x / (x.max() + 1e-9)
    big = 1.0 if job >= T else 0.0
    col_big = -xn
    col_small = np.where(x <= T, xn, -xn)
    return np.stack([big * col_big, (1.0 - big) * col_small], axis=1)

# f003 centered_load_over_mean_plus_job (wide): Negative load of each machine, normalised by mean load plus job, so emptier machines score higher.
def _f003(job, loads, past_jobs, jobs_left):
    """Negative load of each machine, normalised by mean load plus job, so emptier machines score higher."""
    m = len(loads)
    denom = loads.mean() + job + 1e-9
    return -(loads - loads.mean()) / denom

# f036 relative_second_max_hinge (deep): Two columns: -e and -e^2 where e = max(x - sec, 0)/T, x = loads+job, sec = largest other post-load, T = projec
def _f036(job, loads, past_jobs, jobs_left):
    """Two columns: -e and -e^2 where e = max(x - sec, 0)/T, x = loads+job, sec = largest other post-load, T = projected final average."""
    m = loads.shape[0]
    x = loads + job
    mean_past = past_jobs.mean() if past_jobs.size else job
    T = max((loads.sum() + job + jobs_left * mean_past) / m, 1e-9)

    if m == 1:
        sec = np.zeros(1)
    else:
        order = np.argsort(x)
        largest = x[order[-1]]
        second = x[order[-2]]
        sec = np.full(m, largest)
        sec[order[-1]] = second

    e = np.maximum(x - sec, 0.0) / (T + 1e-9)
    return np.stack([-e, -(e ** 2)], axis=1)

# f090 tiny_fill_to_current_mean_not_projected (deep): Negative clipped overshoot of post-load above the current mean load, for tiny jobs only.
def _f090(job, loads, past_jobs, jobs_left):
    """Negative clipped overshoot of post-load above the current mean load, for tiny jobs only."""
    m = loads.shape[0]
    mean_past = past_jobs.mean() if past_jobs.size else job
    if past_jobs.size < 5 or job > 0.25 * mean_past:
        return np.zeros(m)
    L = max(loads.mean(), 1e-9)
    x = loads + job
    return -np.clip((x - L) / L, -1.0, 1.0)

# f100 reserve_expected_big_load_per_machine (deep): Negative post-load plus per-machine expected future big-job reserve, gated to small jobs and scaled to [-1, 1]
def _f100(job, loads, past_jobs, jobs_left):
    """Negative post-load plus per-machine expected future big-job reserve, gated to small jobs and scaled to [-1, 1]."""
    m = loads.shape[0]
    mean_past = float(past_jobs.mean()) if past_jobs.size else float(job)
    T = max((float(loads.sum()) + job + jobs_left * mean_past) / m, 1e-9)
    x = loads + job
    med = float(np.median(past_jobs)) if past_jobs.size else mean_past
    thr = max(5.0 * med, 0.25 * T)
    if past_jobs.size:
        big = past_jobs >= thr
        n_big = int(big.sum())
        rate = n_big / float(past_jobs.size)
        mean_big = float(past_jobs[big].mean()) if n_big else thr
    else:
        rate, mean_big = 0.0, thr
    exp_future = rate * jobs_left * mean_big          # total expected future big load
    g = exp_future / (exp_future + T)                 # 0 when no monster has been seen
    free = loads < thr                                # machine carries no big job yet
    n_free = max(int(free.sum()), 1)
    reserve = np.where(free, exp_future / n_free, 0.0)
    small = 1.0 if job < thr else 0.0
    col = -g * small * (x + reserve) / (T + float(reserve.max()))
    return col.reshape(-1, 1)

_TERMS = [(_f011, np.array([0.84219, 1.644028])), (_f003, np.array([1.259772])), (_f036, np.array([2.923858, 0.736079])), (_f090, np.array([-1.726843])), (_f100, np.array([-1.252246]))]

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
