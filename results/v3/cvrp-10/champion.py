# Helix v3 policy: cvrp, gap 13.871%, progress 93.5%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 nn_distance (deep): Negative Euclidean distance from the current position to each candidate, scaled by 1/sqrt(2).
def _f005(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    """Negative Euclidean distance from the current position to each candidate, scaled by 1/sqrt(2)."""
    return -np.linalg.norm(candidates - current, axis=1) / np.sqrt(2.0)

# f022 closing_cost_gate (deep): Gated negative (leg to candidate + candidate's drive home), 0 for depot row and when remaining > 0.3*capacity.
def _f022(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    """Gated negative (leg to candidate + candidate's drive home), 0 for depot row and when remaining > 0.3*capacity."""
    g = 1.0 if remaining <= 0.3 * capacity else 0.0
    d_cur = np.linalg.norm(candidates - current, axis=1)
    d_dep = np.linalg.norm(candidates - depot, axis=1)
    values = -g * (d_cur + d_dep) / (2.0 * np.sqrt(2.0))
    values = np.where(demands == 0, 0.0, values)
    return values

# f027 slack_conditional_forward_bridge (wide): Slack-conditional forward-partner gain: for each candidate, the best reduction in distance to the next feasibl
def _f027(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    """Slack-conditional forward-partner gain: for each candidate, the best reduction in distance to the next feasible stop (or depot) it opens up, weighted by how tight the remaining capacity is after taking it, normalized, 0 for the depot option (which instead is credited when slack is high and no good forward partner exists)."""
    k = len(candidates)
    is_depot = (demands == 0).astype(float)
    m = unvisited.shape[0]

    d_cur = np.linalg.norm(candidates - current, axis=1)

    # Distance from each candidate to every other unvisited customer
    d_cu = np.linalg.norm(candidates[:, None, :] - unvisited[None, :, :], axis=2)
    same = np.all(np.abs(candidates[:, None, :] - unvisited[None, :, :]) < 1e-12, axis=2)

    aft = remaining - demands
    fits = (unvisited_demands[None, :] <= aft[:, None]) & ~same
    # Forward reach: distance from candidate to its cheapest feasible next stop
    d_fit = np.where(fits, d_cu, np.inf)
    best_partner = np.min(d_fit, axis=1)
    has_partner = np.isfinite(best_partner)
    best_partner = np.where(has_partner, best_partner, 0.0)

    # Slack after taking this candidate, clipped
    slack_after = np.clip(aft / max(capacity, 1), 0.0, 1.0)

    # Immediate gain: how much shorter is current->candidate->partner vs current->partner
    # (we approximate the "would-be next" as the candidate's cheapest partner)
    # If a candidate is a good bridge, its d_cur is offset by the shorter remaining hop.
    # Reward: -d_cur + (something that reflects forward progress) but we keep it distinct:
    # We reward small d_cur AND small best_partner when slack is tight (pack tightly),
    # and reward small d_cur when slack is loose (cheap to visit anything).
    tight = 1.0 - slack_after               # 1 when must fill, 0 when roomy
    combo = -d_cur - tight * best_partner * has_partner
    # When no partner exists, candidate closes a route: penalize d_cur + d_depot lightly
    d_dep = np.linalg.norm(candidates - depot, axis=1)
    close_pen = np.where(has_partner, 0.0, d_dep)

    span = unvisited.max(axis=0) - unvisited.min(axis=0)
    scale = np.linalg.norm(span) + 1e-9

    val = (combo - close_pen) / scale

    # Depot option: closing now is attractive when slack is high (won't fill anyway)
    # and no forward partner would help.
    depot_val = slack_after * 0.5
    val = val * (1.0 - is_depot) + is_depot * depot_val
    return np.nan_to_num(val, nan=0.0, posinf=1.0, neginf=-1.0)

# f058 insertion_saving_vs_nearest_remainder (deep): Saving of inserting each candidate now vs. entering it from its nearest other unvisited customer, weighted by 
def _f058(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    """Saving of inserting each candidate now vs. entering it from its nearest other unvisited customer, weighted by how tight the remaining capacity is: (d_partner - d(current,c))/sqrt(2) * (1 - remaining/capacity), 0 for depot row, clipped to [-1,1]."""
    k = candidates.shape[0]
    m = unvisited.shape[0]
    if m == 0:
        return np.zeros(k)

    # D[i, j] = distance from candidate i to unvisited customer j
    diff = candidates[:, None, :] - unvisited[None, :, :]
    D = np.sqrt(np.sum(diff * diff, axis=2))

    # mask self (identical points) with +inf
    self_mask = D < 1e-12
    D_masked = np.where(self_mask, np.inf, D)

    if m == 1:
        d_partner = np.zeros(k)
    else:
        d_partner = np.min(D_masked, axis=1)
        d_partner = np.where(np.isfinite(d_partner), d_partner, 0.0)

    # distance from current position to each candidate
    d_cur = np.sqrt(np.sum((candidates - current[None, :]) ** 2, axis=1))

    v = (d_partner - d_cur) / np.sqrt(2.0)

    # depot row (demands == 0) -> 0
    depot_mask = demands == 0
    v = np.where(depot_mask, 0.0, v)

    # smooth capacity-tightness gate: 0 when full, ->1 as capacity runs out
    tightness = 1.0 - np.clip(remaining / max(capacity, 1), 0.0, 1.0)
    v = v * tightness

    v = np.clip(v, -1.0, 1.0)
    return v

# f082 phase_mixed_depot_reach (deep): Phase-mixed geometry: (phase*d_depot - (1-phase)*d_current)/sqrt(2), phase = remaining/capacity.
def _f082(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    """Phase-mixed geometry: (phase*d_depot - (1-phase)*d_current)/sqrt(2), phase = remaining/capacity."""
    d_cur = np.sqrt(np.sum((candidates - current) ** 2, axis=1))
    d_dep = np.sqrt(np.sum((candidates - depot) ** 2, axis=1))
    phase = np.clip(remaining / max(capacity, 1), 0.0, 1.0)
    values = (phase * d_dep - (1.0 - phase) * d_cur) / np.sqrt(2.0)
    return values

_TERMS = [(_f005, np.array([4.373357])), (_f022, np.array([5.254929])), (_f027, np.array([-0.0])), (_f058, np.array([4.397087])), (_f082, np.array([6.29945]))]

def priority(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(candidates))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
