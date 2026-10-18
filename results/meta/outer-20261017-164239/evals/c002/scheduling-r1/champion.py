# Helix v3 policy: scheduling, gap 8.662%, progress 99.1%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f012 future_target (deep): Signed normalised deviation (col 0) and its negative square (col 1) of each machine's post-assignment load fro
def _f012(job, loads, past_jobs, jobs_left):
    """Signed normalised deviation (col 0) and its negative square (col 1) of each machine's post-assignment load from the remaining-work-inflated projected final mean."""
    m = loads.shape[0]
    mu = float(past_jobs.mean()) if past_jobs.size > 0 else float(job)   # first decision: fall back to job
    target = (loads.sum() + job + jobs_left * mu) / m                     # projected final mean
    denom = target + job + 1.0                                           # per-decision constant, keeps values bounded
    dev = (loads + job - target) / denom                                 # post-load minus projected mean, scaled
    return np.column_stack([dev, -dev * dev])

# f015 ceiling_fit_headroom (wide): Folded headroom around an optimistic makespan ceiling: prefer the fullest machine that still fits under the ce
def _f015(job, loads, past_jobs, jobs_left):
    """Folded headroom around an optimistic makespan ceiling: prefer the fullest machine that still fits under the ceiling, with a saturating penalty far below it and a job-size-scaled penalty for overflowing it."""
    loads = np.asarray(loads, dtype=float)
    past = np.asarray(past_jobs, dtype=float)
    m = loads.shape[0]
    job = float(job)
    if past.size > 0:
        mp = float(past.mean())          # typical job size seen so far
        mx = float(past.max())           # largest job seen so far
    else:
        mp = mx = job
    post = loads + job
    total = float(loads.sum()) + job
    target = (total + float(jobs_left) * mp) / max(m, 1)   # projected final mean load
    ceiling = max(target, mx)                               # optimistic final makespan
    scale = max(ceiling, job, 1e-9)
    slack = (ceiling - post) / scale                        # >0: still fits under the ceiling
    # fullest machine that still fits scores best; far-below machines saturate (not linear)
    fit = -np.tanh(0.8 * np.clip(slack, 0.0, 20.0))
    over = np.maximum(-slack, 0.0)                          # overflow past the ceiling
    big = min(max(job / max(mp, 1e-9), 0.0), 3.0)           # arriving job size vs typical
    pen = (1.5 + 0.5 * big) * np.tanh(3.0 * over)
    conf = 1.0 / (1.0 + 0.01 * float(jobs_left))            # trust the ceiling less early on
    return np.tanh(conf * (fit - pen))

# f021 phase_blend_least_to_target (deep): Elapsed-weighted blend of negative post-load (early, least-loaded) and negative distance to the projected fina
def _f021(job, loads, past_jobs, jobs_left):
    """Elapsed-weighted blend of negative post-load (early, least-loaded) and negative distance to the projected final mean load (late, packing)."""
    loads = np.asarray(loads, dtype=float)
    past = np.asarray(past_jobs, dtype=float)
    job = float(job)
    m = loads.shape[0]
    t = past.size
    mu = float(past.mean()) if t > 0 else job
    total = float(loads.sum()) + job
    target = (total + float(jobs_left) * mu) / max(m, 1)
    scale = max(abs(target), abs(job), 1e-9)
    post = loads + job
    elapsed = t / (t + float(jobs_left) + 1.0)  # 0 at the first job, -> 1 at the last
    return (-(1.0 - elapsed) * post - elapsed * np.abs(post - target)) / scale

# f001 greedy_least_loaded (wide): Greedy least-loaded preference: negative current load scaled by (max load + arriving job).
def _f001(job, loads, past_jobs, jobs_left):
    """Greedy least-loaded preference: negative current load scaled by (max load + arriving job)."""
    scale = float(np.max(loads)) + float(job) + 1e-9
    return -loads / scale

# f007 expected_target_proximity (wide): Negative distance from a machine's post-assignment load to the expected final average load.
def _f007(job, loads, past_jobs, jobs_left):
    """Negative distance from a machine's post-assignment load to the expected final average load."""
    m = loads.shape[0]
    total = float(loads.sum())
    if past_jobs.size > 0:
        mu = float(past_jobs.mean())
    else:
        mu = float(job)
    target = (total + float(job) + mu * float(jobs_left)) / float(m)
    new_load = loads + float(job)
    scale = max(abs(target), float(job), 1.0)
    return -np.abs(new_load - target) / scale

# f027 median_anchor_target (wide): Negative normalised distance of each machine's post-assignment load to the median of all post-assignment loads
def _f027(job, loads, past_jobs, jobs_left):
    """Negative normalised distance of each machine's post-assignment load to the median of all post-assignment loads (col 0) and its negative square around that median (col 1): prefer the machine that lands in the middle of the pack, not merely the emptiest."""
    loads = np.asarray(loads, dtype=float)
    job = float(job)
    post = loads + job
    m = post.shape[0]
    if m <= 1:
        return np.zeros((m, 2))
    # per-decision scale: typical post-load unit, floored away from zero
    scale = float(np.mean(np.abs(post))) + job + 1.0
    med = float(np.median(post))            # interior anchor, data dependent
    d = (post - med) / scale
    return np.column_stack([-np.abs(d), -(d * d)])

# f022 quantile_ceiling_asymmetric_well (wide): Folded asymmetric quadratic well: penalise each machine's post-load for sitting too far below a spread-inflate
def _f022(job, loads, past_jobs, jobs_left):
    """Folded asymmetric quadratic well: penalise each machine's post-load for sitting too far below a spread-inflated, quantile-based optimistic ceiling (a shallow well, so much emptier machines are not rewarded) and much more for rising above it, with the overflow cost scaled by how large this job is versus a typical past job."""
    loads = np.asarray(loads, dtype=float)
    past = np.asarray(past_jobs, dtype=float)
    m = loads.shape[0]
    job = float(job)
    if past.size > 0:
        mp = float(past.mean())                       # typical job size so far
        mx = float(past.max())                        # largest job so far
        q = float(np.quantile(past, 0.9)) if past.size >= 3 else mx   # near-tail job size
    else:
        mp = mx = q = job
    post = loads + job
    total = float(loads.sum()) + job
    target = (total + float(jobs_left) * mp) / max(m, 1)   # projected final mean load
    spread = float(loads.max() - loads.min()) if m > 1 else 0.0
    # optimistic final makespan: mean projection, at least a near-tail job, nudged up by imbalance already locked in
    ceiling = max(target, q) + 0.25 * spread
    scale = max(ceiling, job, 1e-9)
    aim = ceiling - 0.5 * max(mp, 0.0)                # sit slightly under the ceiling so one more typical job still fits
    d = (post - aim) / scale
    below = np.maximum(-d, 0.0)                       # room left under the aim (bounded by 1)
    above = np.maximum(d, 0.0)                        # distance past the aim
    over = np.maximum((post - ceiling) / scale, 0.0)  # genuine overflow past the ceiling
    big = min(max(job / max(mp, 1e-9), 0.0), 3.0)     # arriving job size vs typical
    # shallow quadratic well below the aim, steep well above it, plus an explicit saturating ceiling breach
    val = -(0.35 * below * below
            + (1.2 + 0.6 * big) * above * above
            + (1.0 + 0.5 * big) * np.tanh(3.0 * over))
    return np.tanh(val)

# f030 second_peak_headroom (deep): Negative resulting second-largest machine load after hypothetically assigning the job to each machine, normali
def _f030(job, loads, past_jobs, jobs_left):
    """Negative resulting second-largest machine load after hypothetically assigning the job to each machine, normalised by the largest post-assignment load."""
    loads = np.asarray(loads, dtype=float)
    m = loads.shape[0]
    post = np.tile(loads, (m, 1))
    post[np.arange(m), np.arange(m)] += job
    if m >= 2:
        sec = np.partition(post, m - 2, axis=1)[:, m - 2]
    else:
        sec = post[:, 0]
    scale = max(float(np.max(loads)) + job, 1.0)
    return -sec / scale

_TERMS = [(_f012, np.array([-3.816347, -1.056768])), (_f015, np.array([18.538301])), (_f021, np.array([3.773249])), (_f001, np.array([4.145454])), (_f007, np.array([1.85837])), (_f027, np.array([-0.686147, 0.06565])), (_f022, np.array([2.329267])), (_f030, np.array([-7.967535]))]

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
