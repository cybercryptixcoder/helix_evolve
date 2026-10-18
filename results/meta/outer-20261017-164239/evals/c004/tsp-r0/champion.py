# Helix v3 policy: tsp, gap 10.645%, progress 97.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 halfplane_sweep_fraction (wide): Regret of a candidate: its distance minus the distance from it to the nearest unvisited city, normalised by th
def _f001(current, candidates, tour, start):
    """Regret of a candidate: its distance minus the distance from it to the nearest unvisited city, normalised by the spread."""
    k = len(candidates)
    # distance from current to each candidate
    d_cur = np.linalg.norm(candidates - current, axis=1)
    # nearest other unvisited city for each candidate (excluding itself)
    diff = candidates[:, None, :] - candidates[None, :, :]
    dmat = np.sqrt(np.sum(diff * diff, axis=2))
    np.fill_diagonal(dmat, np.inf)
    d_near = np.min(dmat, axis=1)
    # regret: going here now costs d_cur but saves d_near later
    regret = d_near - d_cur
    scale = np.mean(d_cur) + 1e-9
    return np.clip(regret / scale, -1.0, 1.0)

# f004 two_opt_savings_via_nearest_unvisited (wide): Savings from joining candidate into the tour via nearest-neighbour 2-opt: distance(current,next) + distance(ne
def _f004(current, candidates, tour, start):
    """Savings from joining candidate into the tour via nearest-neighbour 2-opt: distance(current,next) + distance(next,cand) - distance(current,cand) where next is nearest unvisited to candidate."""
    k = len(candidates)
    if k == 0:
        return np.zeros(0)
    # pairwise distances among candidates
    diff = candidates[:, None, :] - candidates[None, :, :]
    d = np.sqrt(np.sum(diff * diff, axis=2) + 1e-12)
    np.fill_diagonal(d, np.inf)
    # nearest other unvisited neighbour of each candidate
    nn = np.argmin(d, axis=1)
    d_nn = d[np.arange(k), nn]
    # distance from current to candidate and to its nearest neighbour
    dc = np.sqrt(np.sum((candidates - current) ** 2, axis=1) + 1e-12)
    dcn = np.sqrt(np.sum((candidates - candidates[nn]) ** 2, axis=1) + 1e-12)
    # 2-opt style savings: going current->cand->nn(ish) vs current->nn then nn->cand
    savings = d_nn + dc - dcn
    scale = np.max(savings) - np.min(savings) + 1e-9
    return (savings - np.mean(savings)) / scale

# f013 hull_radial_extremity (deep): Radial extremity of each candidate w.r.t. the centroid of the remaining cities, normalised.
def _f013(current, candidates, tour, start):
    """Radial extremity of each candidate w.r.t. the centroid of the remaining cities, normalised."""
    cent = candidates.mean(axis=0)
    d = np.linalg.norm(candidates - cent, axis=1)
    return (d - d.mean()) / (d.max() + 1e-9)

_TERMS = [(_f001, np.array([1.050079])), (_f004, np.array([-4.009502])), (_f013, np.array([2.422]))]

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
