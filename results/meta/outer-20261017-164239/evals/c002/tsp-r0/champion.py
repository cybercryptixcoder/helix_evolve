# Helix v3 policy: tsp, gap 8.537%, progress 98.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 multi_signal_tsp_step (wide): Multi-signal next-city score: proximity to current, insertion detour, isolation among
def _f004(current, candidates, tour, start):
    """Multi-signal next-city score: proximity to current, insertion detour, isolation among
    remaining cities, one-step lookahead cost, and a time-scaled pull toward the start city."""
    cand = np.asarray(candidates, dtype=float)
    cur = np.asarray(current, dtype=float)
    st = np.asarray(start, dtype=float)
    k = len(cand)
    m = len(tour)
    s2 = math.sqrt(2.0)

    d_cur = np.linalg.norm(cand - cur, axis=1)
    d_start = np.linalg.norm(cand - st, axis=1)
    d_cur_start = float(np.linalg.norm(cur - st))

    # pairwise distances among the still-unvisited candidates (diagonal -> inf so min skips self)
    diff = cand[:, None, :] - cand[None, :, :]
    D = np.linalg.norm(diff, axis=2)
    np.fill_diagonal(D, np.inf)
    nearest_other = D.min(axis=1)
    nearest_other = np.where(np.isfinite(nearest_other), nearest_other, 0.0)

    detour = d_cur + d_start - d_cur_start          # cost added to trip if we go via this city
    look = d_cur + nearest_other                    # greedy with one-step lookahead
    t = m / (m + k)                                 # progress fraction in (0, 1)

    return np.stack([
        -d_cur / s2,               # closer to current is better
        -detour / (2.0 * s2),      # avoid big insertion detours (incl. return to start)
        nearest_other / s2,        # isolated cities deserve to be visited sooner
        -look / (2.0 * s2),        # lookahead-aware greedy cost
        -t * d_start / s2,         # late in the tour, drift back toward the start city
    ], axis=1)

# f024 ray_occlusion_and_periphery_priority (wide): Directional-occlusion priority: for each unvisited city, how much of the remaining
def _f024(current, candidates, tour, start):
    """Directional-occlusion priority: for each unvisited city, how much of the remaining
    mass is 'shadowed' behind it along the ray from the current city (soft lateral cone),
    plus its peripheral distance from the centroid of the unvisited set, plus raw proximity."""
    cand = np.asarray(candidates, dtype=float)
    cur = np.asarray(current, dtype=float)
    k = len(cand)
    s2 = math.sqrt(2.0)

    L = cand - cur                                  # k x 2 legs from current
    d = np.linalg.norm(L, axis=1)
    ds = np.maximum(d, 1e-9)
    U = L / ds[:, None]                             # unit ray for each candidate

    Proj = L @ U.T                                  # Proj[i, j] = (c_j - cur) . u_i
    Lsq = np.einsum('ij,ij->i', L, L)               # |L_j|^2
    lat2 = np.maximum(Lsq[None, :] - Proj ** 2, 0.0)  # squared lateral offset of j from ray i
    beyond = Proj - ds[:, None]                     # how far past candidate i the city j sits

    sigma2 = 2.0 * 0.075 ** 2
    wgt = np.exp(-lat2 / sigma2) * (beyond > 0.0)   # soft cone in front of / behind i
    shadow = (wgt * np.maximum(beyond, 0.0)).sum(axis=1) / max(k, 1)

    cent = cand.mean(axis=0)
    periph = np.linalg.norm(cand - cent, axis=1) / (0.5 * s2)

    return np.stack([
        -d / s2,                    # closer to current is better (anchor)
        shadow / (0.25 * s2),       # signed: mass lying just beyond this city on the same ray
        periph,                     # outer cities of the remaining cloud first
    ], axis=1)

# f021 late_closing_detour_ratio_gated (wide): Progress-gated closing diversion: each candidate's detour relative to heading straight
def _f021(current, candidates, tour, start):
    """Progress-gated closing diversion: each candidate's detour relative to heading straight
    home, as a fraction of the legs involved, switched on sharply only late in the tour."""
    cand = np.asarray(candidates, dtype=float)
    cur = np.asarray(current, dtype=float)
    st = np.asarray(start, dtype=float)
    k = cand.shape[0]
    m = len(tour)

    d_cur = np.linalg.norm(cand - cur, axis=1)
    d_start = np.linalg.norm(cand - st, axis=1)
    d_cs = float(np.linalg.norm(cur - st))

    # extra path length of going via the candidate compared with returning home directly
    detour = np.maximum(d_cur + d_start - d_cs, 0.0)
    denom = d_cur + d_start + 1e-9

    t = m / (m + k)            # progress fraction in (0, 1)
    gate = t * t * t           # ~0 early, ~1 near the end

    return -gate * detour / denom

# f033 endgame_exact_completion (deep): Negative exact optimal completion cost (remaining cities + return to start), scaled; 0 unless <=5 cities remai
def _f033(current, candidates, tour, start):
    """Negative exact optimal completion cost (remaining cities + return to start), scaled; 0 unless <=5 cities remain."""
    cand = np.asarray(candidates, float)
    cur = np.asarray(current, float)
    st = np.asarray(start, float)
    k = len(cand)
    if k == 0:
        return np.zeros(0)
    if k > 5:
        return np.zeros(k)                       # inactive until the endgame

    pts = np.vstack([cur, cand, st])             # 0 = current, 1..k = candidates, k+1 = start
    D = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))

    full = (1 << k) - 1
    memo = {}

    def best(mask, last):                        # min cost from node 'last' through 'mask', then back to start
        if mask == 0:
            return D[last, k + 1]
        key = (mask, last)
        if key in memo:
            return memo[key]
        v = min(D[last, j + 1] + best(mask ^ (1 << j), j + 1)
                for j in range(k) if mask >> j & 1)
        memo[key] = v
        return v

    out = np.array([D[0, i + 1] + best(full ^ (1 << i), i + 1) for i in range(k)])
    scale = max((k + 1) * float(np.mean(D[0, 1:k + 1])), 1e-9)
    return -(out / scale)                        # large = cheap exact completion incl. the return leg

_TERMS = [(_f004, np.array([26.950268, 2.667825, 15.398956, 1.414878])), (_f024, np.array([60.897023, 2.451109, 21.561722])), (_f021, np.array([-10.596357])), (_f033, np.array([615.840538]))]

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
