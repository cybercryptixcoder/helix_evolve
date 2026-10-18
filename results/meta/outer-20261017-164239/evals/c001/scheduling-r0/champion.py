# Helix v3 policy: scheduling, gap 12.724%, progress 98.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f006 load_rank_signed (wide): How much a candidate's load exceeds the K-th smallest current load, where K scales with remaining jobs.
def _f006(job, loads, past_jobs, jobs_left):
    """How much a candidate's load exceeds the K-th smallest current load, where K scales with remaining jobs."""
    m = len(loads)
    sorted_loads = np.sort(loads)
    # estimate how many machines will tend to stay near the minimum: more machines means more slack
    # rank a machine's current load (0 = lightest)
    order = np.argsort(np.argsort(loads, kind="stable"), kind="stable").astype(float)
    # normalise rank into [-1, 1]: negative for lightly loaded, positive for heavily loaded
    rank_norm = 2.0 * order / max(m - 1, 1) - 1.0
    return rank_norm

name: load_rank_signed

# f012 dispersion_weighted_median_fit (wide): Advantage of placing on a machine so that its post-load is closest to the current median load of the machines,
def _f012(job, loads, past_jobs, jobs_left):
    """Advantage of placing on a machine so that its post-load is closest to the current median load of the machines, weighted by how tightly loads cluster (dispersion-based best-fit)."""
    m = len(loads)
    post = loads + job
    med = np.median(loads)
    # spread of current loads; small spread => tight clustering, prefer near-median placement
    spread = np.std(loads) + 1e-9
    # normalise distance of resulting load from median by spread and job size
    scale = spread + job + 1e-9
    dist = np.abs(post - med) / scale
    # tighter clusters (small spread relative to job) => stronger pull toward median
    tightness = job / (job + spread)
    return -dist * tightness

# f025 post_top_heaviness_penalty (wide): Negative spread of the post-placement load multiset relative to its mean, i.e. how much a placement would incr
def _f025(job, loads, past_jobs, jobs_left):
    """Negative spread of the post-placement load multiset relative to its mean, i.e. how much a placement would increase the gap between the two heaviest and the lightest machines after the job lands."""
    m = len(loads)
    post = loads + job
    mean_post = post.mean()
    # top-heaviness: how far the two largest post-loads sit above the mean, plus how far the lightest sits below
    sorted_post = np.sort(post)
    top_excess = (sorted_post[-1] - mean_post) + (sorted_post[-2] - mean_post if m > 1 else 0.0)
    bottom_deficit = mean_post - sorted_post[0]
    scale = job + np.std(loads) + np.abs(mean_post) + 1e-9
    # for each candidate, we approximate by shifting: candidate c would become one of the loads
    # we can't recompute sorted per candidate without a loop, so use a smooth proxy:
    # distance of this candidate's post-load from the mean, weighted toward the heavy side
    dev = post - mean_post
    heavy_weight = 1.5  # penalise high post-loads more (they set the makespan)
    score = -(np.where(dev > 0, heavy_weight, 1.0) * np.abs(dev)) / scale
    # add a term favouring candidates that fill the lowest slot (reduce bottom deficit)
    min_load = loads.min()
    fill = (min_load - loads) / scale  # positive for the lightest machines
    return score + 0.5 * fill

name: post_top_heaviness_penalty

# f036 giant_band_asymmetric_hinge (wide): Two-sided band: reward post-loads that land inside [floor, cap] where floor = projected mean minus a giant res
def _f036(job, loads, past_jobs, jobs_left):
    """Two-sided band: reward post-loads that land inside [floor, cap] where floor = projected mean minus a giant reserve, cap = projected mean plus a slack allowance; score falls off on both sides but penalises overshoot far more than idle slack, with the band width shrinking as jobs run out."""
    m = len(loads)
    t = len(past_jobs)
    cur = float(np.sum(loads))

    # giant detection on the observed stream
    tau = float(np.max(past_jobs)) if t > 0 else float(job)
    thr = 0.5 * tau
    if t > 0:
        g = past_jobs[past_jobs >= thr]
    else:
        g = np.array([], dtype=float)
    p_g = g.size / max(t, 1)
    g_size = float(g.mean()) if g.size > 0 else tau

    if t > 0:
        mu_small = float(np.mean(past_jobs[past_jobs < thr])) if np.any(past_jobs < thr) else float(np.mean(past_jobs))
    else:
        mu_small = float(job)

    # expected future work, split into giant and non-giant contributions
    exp_giant = jobs_left * p_g * g_size
    exp_small = jobs_left * (1.0 - p_g) * mu_small
    target = (cur + job + exp_giant + exp_small) / m

    # reserve: work we cannot safely pre-place because giants must be spread
    reserve = exp_giant / m
    floor = target - reserve

    # slack allowance: the other machines also carry idle room; a placement may exceed
    # the mean by at most the typical remaining headroom per machine. Shrinks as jobs run out.
    horizon = max(jobs_left, 1)
    headroom = (exp_small + exp_giant) / m / np.sqrt(horizon)
    cap = target + 0.5 * headroom

    post = loads + job
    scale = max(abs(target), tau, 1e-9)

    over = np.maximum(0.0, post - cap)
    under = np.maximum(0.0, floor - post)

    # asymmetric: overshoot hurts ~4x more than leaving idle slack
    return -(4.0 * over + under) / scale

# f042 asymmetric_median_best_fit (wide): Asymmetric best-fit: penalise post-loads above the median much more than below it, with the pull strengt
def _f042(job, loads, past_jobs, jobs_left):
    """Asymmetric best-fit: penalise post-loads above the median much more than below it, with the pull strengt
    scaling by how full the frontier is (remaining work per machine vs current spread)."""
    m = len(loads)
    post = loads + job
    med = np.median(loads)
    spread = np.std(loads)
    order = np.argsort(np.argsort(loads, kind="stable"), kind="stable").astype(float)
    q = order / max(m - 1, 1)  # 0 = lightest, 1 = heaviest

    # remaining work pressure per machine, relative to current spread
    cur = float(np.sum(loads))
    t = len(past_jobs)
    mean_obs = float(np.mean(past_jobs)) if t > 0 else float(job)
    remaining = jobs_left * mean_obs
    pressure = remaining / m
    scale = pressure + spread + job + 1e-9

    dev = post - med
    # above median: cost grows with how heavy the rank already is (heavy machines must not grow)
    upper = np.maximum(0.0, dev) / scale * (1.0 + q)
    lower = np.maximum(0.0, -dev) / scale * (1.0 - q)
    # tighter clusters => sharper best-fit pull; measured by spread relative to mean machine load
    tightness = (job + mean_obs) / (job + mean_obs + spread + 1e-9)
    return -(3.0 * upper + lower) * tightness

_TERMS = [(_f006, np.array([-0.360006])), (_f012, np.array([4.923542])), (_f025, np.array([-0.545113])), (_f036, np.array([0.199034])), (_f042, np.array([-0.107433]))]

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
