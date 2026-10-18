# Helix v3 policy: tsp, gap 12.059%, progress 97.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 edge_vs_centroid_balance (wide): Squared distance from the current city to each candidate, normalised by the farthest candidate.
def _f003(current, candidates, tour, start):
    """Squared distance from the current city to each candidate, normalised by the farthest candidate."""
    d = candidates - current[None, :]
    sq = np.einsum('ij,ij->i', d, d)
    mx = sq.max()
    if mx <= 0:
        return np.zeros(len(candidates))
    return sq / mx

# f008 candidate_density (deep): Negated mean distance from each candidate to all other unvisited cities, normalised by the max.
def _f008(current, candidates, tour, start):
    """Negated mean distance from each candidate to all other unvisited cities, normalised by the max."""
    k = len(candidates)
    D = np.linalg.norm(candidates[:, None, :] - candidates[None, :, :], axis=2)
    mean_d = D.sum(axis=1) / (k - 1 + 1e-12)
    return -mean_d / (mean_d.max() + 1e-12)

# f012 nearest_neighbour_plus_return_span (wide): Negated distance from each candidate to its own nearest unvisited city, plus the candidate's distance back to 
def _f012(current, candidates, tour, start):
    """Negated distance from each candidate to its own nearest unvisited city, plus the candidate's distance back to the tour start, normalised by their sum's max."""
    k = len(candidates)
    D = np.linalg.norm(candidates[:, None, :] - candidates[None, :, :], axis=2)
    np.fill_diagonal(D, np.inf)
    nn = D.min(axis=1)
    back = np.linalg.norm(candidates - start[None, :], axis=1)
    v = -(nn + back)
    mx = np.abs(v).max()
    if mx <= 0:
        return np.zeros(k)
    return v / mx

_TERMS = [(_f003, np.array([-4.823982])), (_f008, np.array([-0.638763])), (_f012, np.array([-0.165871]))]

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
