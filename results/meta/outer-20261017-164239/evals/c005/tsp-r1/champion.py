# Helix v3 policy: tsp, gap 9.677%, progress 98.1%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 skip_regret (wide): Measures, for each candidate, how much worse the nearest-neighbour continuation would be if we skipped it now:
def _f002(current, candidates, tour, start):
    """Measures, for each candidate, how much worse the nearest-neighbour continuation would be if we skipped it now: a 'regret' of deferring this candidate."""
    # Vectorised: for each candidate compute its distance to current.
    d_cur = np.linalg.norm(candidates - current[None, :], axis=1)

    # Distances among candidates themselves (k x k).
    diff = candidates[:, None, :] - candidates[None, :, :]
    d_cc = np.linalg.norm(diff, axis=2)
    np.fill_diagonal(d_cc, np.inf)

    # Nearest other unvisited city reachable from each candidate.
    nearest_other = np.min(d_cc, axis=1)

    # Nearest unvisited city from current (the greedy pick).
    greedy_idx = int(np.argmin(d_cur))

    # Regret of not taking each candidate now:
    # if we skip candidate i, the greedy step goes elsewhere, and later reaching i
    # costs at least distance from its nearest unvisited neighbour.
    regret = nearest_other - d_cur

    # Normalise: local scale is the largest relevant distance.
    scale = max(d_cur[greedy_idx], np.max(nearest_other[np.isfinite(nearest_other)]), 1e-9)

    values = regret / scale

    # Highlight the strongest regret relative to the greedy candidate, so the
    # ordering is not just a distance ranking.
    values = values - values[greedy_idx]

    return np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=-1.0)

# f023 closing_aware_regret (deep): Skip-regret of each candidate plus its distance to start weighted by tour progress.
def _f023(current, candidates, tour, start):
    """Skip-regret of each candidate plus its distance to start weighted by tour progress."""
    k = candidates.shape[0]
    m = tour.shape[0]

    # bbox diagonal over all points seen so far (tour + candidates + start)
    pts = np.vstack([tour, candidates, start[None, :]])
    span = pts.max(axis=0) - pts.min(axis=0)
    scale = float(np.hypot(span[0], span[1]))
    if scale <= 0.0:
        scale = 1.0

    # distance from current city to each candidate
    d_cur = np.hypot(candidates[:, 0] - current[0], candidates[:, 1] - current[1])

    # nearest other point (tour cities or other candidates) to each candidate
    others = np.vstack([tour, candidates])
    diff = candidates[:, None, :] - others[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    # exclude self-matches (candidate i vs others row m+i)
    dist[np.arange(k), m + np.arange(k)] = np.inf
    nearest_other = dist.min(axis=1)

    regret = (nearest_other - d_cur) / scale

    late = m / (m + k)
    d_start = np.hypot(candidates[:, 0] - start[0], candidates[:, 1] - start[1]) / scale

    return regret + late * d_start

# f021 start_weighted_savings (deep): Savings (d_cs - d_cur - d_start)/scale gated by 1/(1+(d_start/scale)^2), with the gate applied to the closing-
def _f021(current, candidates, tour, start):
    """Savings (d_cs - d_cur - d_start)/scale gated by 1/(1+(d_start/scale)^2), with the gate applied to the closing-leg term so the start dimension orders candidates."""
    pts = np.vstack([tour, candidates, start[None, :]])
    span = pts.max(axis=0) - pts.min(axis=0)
    scale = float(np.hypot(span[0], span[1]))
    if scale <= 0.0:
        scale = 1.0
    d_cur = np.hypot(candidates[:, 0] - current[0], candidates[:, 1] - current[1])
    d_start = np.hypot(candidates[:, 0] - start[0], candidates[:, 1] - start[1])
    d_cs = float(np.hypot(current[0] - start[0], current[1] - start[1]))
    savings = (d_cs - d_cur - d_start) / scale
    gate = 1.0 / (1.0 + (d_start / scale) ** 2)
    # Apply the gate to the start-dependent part of the savings so that
    # candidates near the start are favoured, rather than scaling the whole
    # (nearest-neighbour-dominated) savings term uniformly.
    return savings - (d_start / scale) * gate

# f026 ratio_anchor_regret_isolation (wide): For each candidate, the increase in nearest-neighbour tour length if we take it now versus the best alternativ
def _f026(current, candidates, tour, start):
    """For each candidate, the increase in nearest-neighbour tour length if we take it now versus the best alternative, measured as a ratio of mutual nearest-neighbour costs (SOP-style regret)."""
    k = candidates.shape[0]
    if k == 1:
        return np.zeros(1)

    # Distance from current to each candidate.
    d_cur = np.linalg.norm(candidates - current[None, :], axis=1)

    # Pairwise distances among candidates.
    diff = candidates[:, None, :] - candidates[None, :, :]
    d_cc = np.linalg.norm(diff, axis=2)
    np.fill_diagonal(d_cc, np.inf)

    # Nearest other unvisited city from each candidate (its "successor" cost).
    nearest_other = np.min(d_cc, axis=1)

    # Second-nearest other unvisited city: how much worse the successor gets
    # if the nearest neighbour is itself consumed first.
    d_sorted = np.sort(d_cc, axis=1)
    second_other = d_sorted[:, 1]

    # For each candidate, the "cost of the local detour it anchors":
    # going current -> candidate -> its nearest neighbour.
    anchor_cost = d_cur + nearest_other

    # The best anchor cost currently available (the greedy-ish local move).
    best_anchor = np.min(anchor_cost)

    # Regret: how much worse this candidate's local detour is than the best one.
    # Ratio form keeps it scale-free and highlights candidates that are close
    # in absolute terms but comparatively bad, unlike a plain difference.
    regret = (anchor_cost - best_anchor) / (anchor_cost + best_anchor + 1e-9)

    # Add a term for candidates whose nearest neighbour is nearly as close as
    # their second nearest: these are "cheap to lose" (isolated-ish in the
    # remaining set) and should be taken before they get stranded.
    isolation = (second_other - nearest_other) / (second_other + nearest_other + 1e-9)

    values = regret - isolation

    return np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=-1.0)

# f031 endgame_greedy_closing_chain (deep): Negative greedy closing-chain length (current->candidate->...->start) when k<=6, else zeros.
def _f031(current, candidates, tour, start):
    """Negative greedy closing-chain length (current->candidate->...->start) when k<=6, else zeros."""
    k = candidates.shape[0]
    if k > 6:
        return np.zeros(k)

    allpts = np.vstack([tour, candidates])
    bbox_diag = np.linalg.norm(allpts.max(axis=0) - allpts.min(axis=0))
    scale = bbox_diag if bbox_diag > 1e-12 else 1.0

    vals = np.empty(k)
    for i in range(k):
        pos = candidates[i]
        chain = np.linalg.norm(pos - current)
        rest = np.delete(candidates, i, axis=0)
        while rest.shape[0] > 0:
            d = np.linalg.norm(rest - pos, axis=1)
            j = int(np.argmin(d))
            chain += d[j]
            pos = rest[j]
            rest = np.delete(rest, j, axis=0)
        chain += np.linalg.norm(pos - start)
        vals[i] = -chain / scale

    return vals

# f037 leg_passby_intrusion_penalty (deep): Negative of the strongest weighted intrusion of any other unvisited city into the interior of the leg current-
def _f037(current, candidates, tour, start):
    """Negative of the strongest weighted intrusion of any other unvisited city into the interior of the leg current->candidate."""
    k = candidates.shape[0]
    if k <= 1:
        return np.zeros(k)
    v = candidates - current  # (k,2)
    L = np.linalg.norm(v, axis=1)
    L = np.maximum(L, 1e-9)
    # nearest-neighbour distance among candidates
    diff = candidates[:, None, :] - candidates[None, :, :]  # (k,k,2)
    d = np.linalg.norm(diff, axis=2)
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)  # (k,)
    R = np.maximum(nn.mean(), 1e-9)
    # t[i,j] = clip(dot(v_j, v_i)/L_i^2, 0, 1)
    dot = v @ v.T  # (k,k): dot[i,j] = v_i . v_j
    t = np.clip(dot / (L ** 2)[:, None], 0.0, 1.0)  # (k,k)
    perp = np.linalg.norm(v[None, :, :] - t[:, :, None] * v[:, None, :], axis=2)  # (k,k)
    w = 4.0 * t * (1.0 - t)
    g = w * np.exp(-(perp / (0.6 * R)) ** 2)
    np.fill_diagonal(g, 0.0)
    return -g.max(axis=1)

_TERMS = [(_f002, np.array([0.650439])), (_f023, np.array([20.283703])), (_f021, np.array([-2.256385])), (_f026, np.array([-0.813483])), (_f031, np.array([846.150962])), (_f037, np.array([1.295412]))]

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
