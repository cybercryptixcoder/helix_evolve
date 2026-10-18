# Helix v3 policy: tsp, gap 9.472%, progress 98.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 start_closing_balance (wide): Measures how much closer a candidate's insertion into the remaining-start link helps: distance from candidate 
def _f004(current, candidates, tour, start):
    """Measures how much closer a candidate's insertion into the remaining-start link helps: distance from candidate to start minus distance from current to candidate."""
    # Euclidean distance from each candidate to the start (closing leg potential)
    to_start = np.sqrt(((candidates - start) ** 2).sum(axis=1))
    # Euclidean distance from current to each candidate
    from_current = np.sqrt(((candidates - current) ** 2).sum(axis=1))
    # Candidates closer to start are preferred, but only after accounting for travel cost
    return (from_current - to_start) / (from_current + to_start + 1e-9)

# f001 return_leg_minus_step (wide): Distance from each candidate to the start city, minus its distance to the current city (return-leg anticipatio
def _f001(current, candidates, tour, start):
    """Distance from each candidate to the start city, minus its distance to the current city (return-leg anticipation)."""
    d_cur = np.linalg.norm(candidates - current[None, :], axis=1)
    d_start = np.linalg.norm(candidates - start[None, :], axis=1)
    span = 0.5 * np.sqrt(2.0)
    return (d_cur - d_start) / span

# f005 nearest_neighbour_distance (deep): Negative Euclidean distance from the current city to each candidate, scaled by 1/sqrt(2).
def _f005(current, candidates, tour, start):
    """Negative Euclidean distance from the current city to each candidate, scaled by 1/sqrt(2)."""
    return -np.linalg.norm(candidates - current, axis=1) / np.sqrt(2.0)

# f027 homesick_vs_isolation_ratio (deep): (nn - d_start) / (nn + d_start): closeness to start relative to the candidate's own nearest unvisited neighbou
def _f027(current, candidates, tour, start):
    """(nn - d_start) / (nn + d_start): closeness to start relative to the candidate's own nearest unvisited neighbour."""
    candidates = np.asarray(candidates, dtype=float)
    start = np.asarray(start, dtype=float)
    k = candidates.shape[0]
    d_start = np.linalg.norm(candidates - start[None, :], axis=1)
    if k == 1:
        nn = np.zeros(1, dtype=float)
    else:
        diff = candidates[:, None, :] - candidates[None, :, :]
        D = np.linalg.norm(diff, axis=2)
        np.fill_diagonal(D, np.inf)
        nn = D.min(axis=1)
    denom = nn + d_start + 1e-9
    return (nn - d_start) / denom

_TERMS = [(_f004, np.array([-1.552523])), (_f001, np.array([-2.952699])), (_f005, np.array([3.731151])), (_f027, np.array([1.132865]))]

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
