# Helix v3 policy: tsp, gap 12.713%, progress 97.5%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f006 neg_dist_from_current (deep): Negative Euclidean distance from the current city to each candidate, normalised by the mean candidate distance
def _f006(current, candidates, tour, start):
    """Negative Euclidean distance from the current city to each candidate, normalised by the mean candidate distance."""
    d = np.linalg.norm(candidates - current, axis=1)
    return -d / (d.mean() + 1e-9)

# f002 distance_to_start_normalized (wide): Distance from each candidate to the start city, normalized by the farthest candidate-to-start distance.
def _f002(current, candidates, tour, start):
    """Distance from each candidate to the start city, normalized by the farthest candidate-to-start distance."""
    d_start = np.linalg.norm(candidates - start[None, :], axis=1)
    scale = np.max(d_start)
    if scale < 1e-9:
        return np.zeros(len(candidates))
    return d_start / scale

# f004 last_leg_saving (wide): Saving from taking the candidate as the last leg back to start instead of via current, relative to distance fr
def _f004(current, candidates, tour, start):
    """Saving from taking the candidate as the last leg back to start instead of via current, relative to distance from current."""
    d_cur = np.linalg.norm(candidates - current, axis=1)
    d_start = np.linalg.norm(candidates - start, axis=1)
    denom = d_cur + d_start + 1e-9
    # If we go current->candidate now, and later candidate->start; measure improvement over current->start directly
    saving = (np.linalg.norm(current - start) - d_start) / denom
    return saving

_TERMS = [(_f006, np.array([4.216343])), (_f002, np.array([4.804883])), (_f004, np.array([0.980282]))]

def priority(current, candidates, tour, start):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(current, candidates, tour, start), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(candidates))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
