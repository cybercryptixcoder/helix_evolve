# Helix v3 policy: tsp, gap 10.895%, progress 97.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 nearest_neighbour_negdist (deep): Negative Euclidean distance from current city to each candidate, scaled by the max such distance.
def _f005(current, candidates, tour, start):
    """Negative Euclidean distance from current city to each candidate, scaled by the max such distance."""
    d = np.linalg.norm(candidates - current, axis=1)
    return -d / (d.max() + 1e-9)

# f015 local_spacing_neg (deep): Negative mean distance to the p=min(3,k-1) nearest other candidates, scaled by the max such spacing.
def _f015(current, candidates, tour, start):
    """Negative mean distance to the p=min(3,k-1) nearest other candidates, scaled by the max such spacing."""
    k = len(candidates)
    if k == 1:
        spacing = np.linalg.norm(candidates[0] - start)
        spacing = np.array([spacing])
    else:
        diff = candidates[:, None, :] - candidates[None, :, :]
        D = np.sqrt(np.sum(diff * diff, axis=2))
        np.fill_diagonal(D, np.inf)
        p = min(3, k - 1)
        spacing = np.sort(D, axis=1)[:, :p].mean(axis=1)
    return -spacing / (spacing.max() + 1e-9)

# f013 near_and_outward (wide): Negative distance to current, penalised by how far the candidate is from the centroid of the unvisited set (pr
def _f013(current, candidates, tour, start):
    """Negative distance to current, penalised by how far the candidate is from the centroid of the unvisited set (prefer near-and-outward: gobble edge cities first)."""
    d = np.linalg.norm(candidates - current, axis=1)
    d_n = d / (d.max() + 1e-9)
    # spread of unvisited set: distance of each candidate from the unvisited centroid
    cen = candidates.mean(axis=0)
    spread = np.linalg.norm(candidates - cen[None, :], axis=1)
    spread_n = spread / (spread.max() + 1e-9)
    # prefer candidates that are near current AND far from the centroid (rim cities first)
    return -d_n + 0.5 * spread_n

# f033 abs_turn_soft_straight (deep): Negative absolute turn angle (radians/pi) between incoming heading and each candidate direction, with a smooth
def _f033(current, candidates, tour, start):
    """Negative absolute turn angle (radians/pi) between incoming heading and each candidate direction, with a smooth straightness term that stays monotone in |turn| and is scaled by how far the candidate is from the current city."""
    k = candidates.shape[0]
    if tour.shape[0] < 2:
        return np.zeros(k)
    inc = current - tour[-2]
    n = np.linalg.norm(inc)
    if n < 1e-9:
        return np.zeros(k)
    inc = inc / (n + 1e-9)
    vec = candidates - current
    vn = np.linalg.norm(vec, axis=1)
    vu = vec / (vn[:, None] + 1e-9)
    c = np.clip(vu @ inc, -1.0, 1.0)
    ang = np.arccos(c)
    # straightness in [0,1], monotone decreasing in |turn|, smooth everywhere
    straight = 0.5 * (1.0 + c)
    # weight by proximity so the term also prefers near candidates along the heading
    prox = 1.0 / (1.0 + vn)
    return -(ang / np.pi) * straight * prox

_TERMS = [(_f005, np.array([7.26978])), (_f015, np.array([-0.80761])), (_f013, np.array([6.160767])), (_f033, np.array([0.722328]))]

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
