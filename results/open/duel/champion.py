# Helix v3 policy: duel, gap 56.696%, progress 43.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f007 flip_points_available (deep): (1/5) * sum of points of opponent non-home neighbours that would flip if this candidate is claimed.
def _f007(moves, owner, homes, points, adjacency, turn):
    """(1/5) * sum of points of opponent non-home neighbours that would flip if this candidate is claimed."""
    own = (owner == 1)
    opp = (owner == -1)
    own_nbr = adjacency.astype(np.int32) @ own.astype(np.int32)  # (N,)
    opp_nbr = adjacency.astype(np.int32) @ opp.astype(np.int32)  # (N,)
    opp_home = homes[1]
    # For each candidate v, its opponent-owned neighbours u (u != opp home)
    cand_adj = adjacency[moves]  # (k, N)
    is_opp_nbr = cand_adj & opp[None, :]  # (k, N)
    is_opp_nbr[:, opp_home] = False
    # u flips if own_nbr[u] + 1 >= opp_nbr[u]
    flips = (own_nbr + 1) >= opp_nbr  # (N,)
    qualifies = is_opp_nbr & flips[None, :]  # (k, N)
    vals = (qualifies.astype(np.float64) * points[None, :]).sum(axis=1) / 5.0
    return vals

# f017 contested_value_near_opponent (deep): Points of each candidate (scaled by 1/5) times opponent-neighbour pressure (capped at 3, scaled by 1/3).
def _f017(moves, owner, homes, points, adjacency, turn):
    """Points of each candidate (scaled by 1/5) times opponent-neighbour pressure (capped at 3, scaled by 1/3)."""
    A = adjacency.astype(np.float32)
    opp = (owner == -1).astype(np.float32)
    opp_nbr = A @ opp
    vals = (points[moves].astype(np.float32) / 5.0) * (np.minimum(opp_nbr[moves], 3.0) / 3.0)
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

# f022 exposure_tempo_value (wide): Race to expose: for each candidate, the number of empty cells it 'opens' to me (empty neighbours e where my co
def _f022(moves, owner, homes, points, adjacency, turn):
    """Race to expose: for each candidate, the number of empty cells it 'opens' to me (empty neighbours e where my count would then be strictly greater than the opponent's, i.e. I could claim e next turn uncontested), weighted by points[e], scaled by total points; positive = tempo."""
    pts = points.astype(np.float64)
    total = max(pts.sum(), 1.0)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0).astype(np.float64)
    adj = adjacency.astype(np.float64)

    my_n = adj @ my
    opp_n = adj @ opp

    cand_adj = adj[moves]                       # (k, N)
    my_after = my_n[None, :] + cand_adj         # (k, N)
    # empty cells I would strictly dominate after claiming candidate
    dominate = (my_after > opp_n[None, :]) & (empty[None, :] > 0)
    vals = (dominate.astype(np.float64) * pts[None, :]).sum(axis=1) / total
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

name: exposure_tempo_value

# f033 opp_high_value_mobility (deep): High-value empty cells the opponent can safely claim next, weighted by how many of their neighbours they alrea
def _f033(moves, owner, homes, points, adjacency, turn):
    """High-value empty cells the opponent can safely claim next, weighted by how many of their neighbours they already own (their tempo strength), divided by 3 and clipped to [0,1]."""
    A = adjacency.astype(np.float64)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0)
    w = (points / 5.0) ** 2 * empty
    my_n = A @ my
    opp_n = A @ opp
    cand_adj = A[moves]  # (k, N)
    my_after = my_n[None, :] + cand_adj
    # how strongly the opponent already dominates each empty cell (their tempo on it)
    strength = np.clip(opp_n - my_n, 0.0, None)  # (N,)
    leak = ((opp_n[None, :] > my_after) * w[None, :] * strength[None, :]).sum(axis=1) / 3.0
    return np.clip(leak, 0.0, 1.0)

# f058 lock_out_empty_margin (wide): For each candidate: how much it raises the flip-threshold cost for the opponent on the empty cells it touches 
def _f058(moves, owner, homes, points, adjacency, turn):
    """For each candidate: how much it raises the flip-threshold cost for the opponent on the empty cells it touches — sum over empty neighbours e of points[e]/5 * (my_neighbours[e] after claim) when that would push my count on e strictly above the opponent's, else 0, normalised by board points; measures locking empties out of the opponent's reach by counting, not adjacency."""
    pts = points.astype(np.float64)
    total = max(pts.sum(), 1.0)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0).astype(np.float64)
    A = adjacency.astype(np.float64)

    my_n = A @ my
    opp_n = A @ opp

    cand_adj = A[moves]                       # (k, N)
    my_after = my_n[None, :] + cand_adj       # (k, N)

    # margin over opponent on each cell after the claim
    margin = my_after - opp_n[None, :]        # (k, N)
    # only empty cells, and only those I now strictly dominate (opponent would need 2+ claims to flip)
    locked = (empty[None, :] > 0) & (margin > 0) & (margin <= 1)
    # weight by points and by the size of the margin (how hard to overturn)
    w = locked.astype(np.float64) * (pts[None, :] / 5.0) * margin
    vals = w.sum(axis=1) / total
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

name: lock_out_empty_margin

# f068 hub_gate_denial (deep): Points x degree-fraction of opponent-reachable empties adjacent to the candidate, plus a quarter-weight on dis
def _f068(moves, owner, homes, points, adjacency, turn):
    """Points x degree-fraction of opponent-reachable empties adjacent to the candidate, plus a quarter-weight on distance-2 ones."""
    pts = points.astype(float)
    my = (owner == 1)
    opp = (owner == -1)
    emp0 = (owner == 0)
    A = adjacency.astype(float)
    my_n = A @ my.astype(float)
    opp_n = A @ opp.astype(float)
    deg = A.sum(axis=1)
    N = owner.shape[0]
    A2 = A @ A

    hub = np.clip(deg / 5.0, 0.0, 1.0)
    oppreach = (opp_n >= 1) & emp0
    w = (pts / 5.0) * hub * oppreach.astype(float)
    near = (A[moves] * emp0[None, :]) @ w
    w2 = (pts / 5.0) * oppreach.astype(float)
    far = (A2[moves].astype(float) * emp0[None, :]) @ w2
    return np.clip(near + 0.25 * far, 0.0, 1.0)

# f072 net_tempo_with_flip_fold (wide): Net tempo with flip-fold: for each candidate, points^2-weighted empty cells I would strictly dominate after my
def _f072(moves, owner, homes, points, adjacency, turn):
    """Net tempo with flip-fold: for each candidate, points^2-weighted empty cells I would strictly dominate after my claim, minus those the opponent still dominates/tie, MINUS a half-weight on opponent non-home cells that would actually flip to me (points^2 weighted) — rewards claims whose flips change the tempo balance, scaled by total squared points."""
    pts = points.astype(np.float64)
    w = pts * pts
    total = max(w.sum(), 1.0)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0)
    adj = adjacency.astype(np.float64)

    my_n = adj @ my
    opp_n = adj @ opp

    cand_adj = adj[moves]                       # (k, N)
    my_after = my_n[None, :] + cand_adj         # (k, N)

    win = (my_after > opp_n[None, :]) & empty[None, :]
    lose = (my_after < opp_n[None, :]) & empty[None, :]
    tempo = ((win.astype(np.float64) - lose.astype(np.float64)) * w[None, :]).sum(axis=1)

    # flip term: opponent non-home cells that would flip given the claim
    opp_home = homes[1]
    is_opp_nbr = cand_adj.astype(bool) & (opp[None, :] > 0)
    is_opp_nbr[:, opp_home] = False
    flips = (my_n + 1.0) >= opp_n                # (N,) cells that flip
    flip_w = (is_opp_nbr & flips[None, :]).astype(np.float64) * w[None, :]
    flip_term = flip_w.sum(axis=1)

    vals = (tempo - 0.5 * flip_term) / total
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

name: net_tempo_with_flip_fold

# f074 frontier_split_degree_normalized (wide): Degree-normalised frontier split: for each candidate, (empty neighbours it opens that I dominate) minus (empty
def _f074(moves, owner, homes, points, adjacency, turn):
    """Degree-normalised frontier split: for each candidate, (empty neighbours it opens that I dominate) minus (empty neighbours where opponent still dominates), each weighted by points/5 and by 1/deg of that empty cell, so high-degree junctions count less."""
    pts = points.astype(np.float64)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0)
    A = adjacency.astype(np.float64)
    deg = np.maximum(A.sum(axis=1), 1.0)
    inv_deg = 1.0 / deg

    my_n = A @ my
    opp_n = A @ opp

    cand_adj = A[moves]                        # (k, N)
    my_after = my_n[None, :] + cand_adj        # (k, N)

    win = (my_after > opp_n[None, :]) & empty[None, :]
    lose = (my_after < opp_n[None, :]) & empty[None, :]
    w = (pts / 5.0) * inv_deg
    vals = ((win.astype(np.float64) - lose.astype(np.float64)) * w[None, :]).sum(axis=1)
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

name: frontier_split_degree_normalized

# f090 flip_margin_squared_weighted (wide): Sum over opponent non-home cells adjacent to the candidate of (points/5) * margin^2 * (1 if flipping) where ma
def _f090(moves, owner, homes, points, adjacency, turn):
    """Sum over opponent non-home cells adjacent to the candidate of (points/5) * margin^2 * (1 if flipping) where margin = (my_nbr+1) - opp_nbr, rewarding near-threshold contested flips and penalising hopeless ones; scaled by 1/9."""
    own = (owner == 1)
    opp = (owner == -1)
    A = adjacency.astype(np.int32)
    own_nbr = A @ own.astype(np.int32)   # (N,)
    opp_nbr = A @ opp.astype(np.int32)   # (N,)
    opp_home = homes[1]
    # margin after claim: how many more of u's neighbours I'd own vs opponent
    margin = (own_nbr + 1) - opp_nbr     # (N,) >= 0 means it flips
    # weight: flips get positive pull, non-flips get a small negative pull weighted by closeness
    flip_w = np.where(margin >= 0, margin.astype(np.float64) + 1.0, -1.0 / (1.0 + np.abs(margin.astype(np.float64))))
    cell_w = (points.astype(np.float64) / 5.0) * flip_w  # (N,)

    cand_adj = adjacency[moves].astype(bool)   # (k, N)
    is_opp_nbr = cand_adj & opp[None, :]
    is_opp_nbr[:, opp_home] = False
    vals = (is_opp_nbr.astype(np.float64) * cell_w[None, :]).sum(axis=1) / 9.0
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

# f103 flip_severs_opp_access (deep): Sum over opponent non-home cells u adjacent to candidate v that would flip (margin>=0) of the points/5 of empt
def _f103(moves, owner, homes, points, adjacency, turn):
    """Sum over opponent non-home cells u adjacent to candidate v that would flip (margin>=0) of the points/5 of empty cells e adjacent to u with opp_nbr[e]==1, divided by 2, clipped to [0,1]."""
    p = points.astype(float) / 5.0
    mine = (owner == 1).astype(float)
    opp = (owner == -1).astype(float)
    my_nbr = adjacency @ mine
    opp_nbr = adjacency @ opp
    margin = my_nbr + 1.0 - opp_nbr

    empty = (owner == 0)
    # w[u] = sum over empty e adjacent to u with opp_nbr[e]==1 of p[e]
    sole_access = empty & (opp_nbr == 1)
    w = adjacency @ (p * sole_access.astype(float))

    # flip mask per cell u (independent of candidate except adjacency)
    flippable = (owner == -1) & (margin >= 0)
    flippable[homes[1]] = False

    # value(v) = sum_u adjacency[v,u] * flippable[u] * w[u]
    contrib = flippable.astype(float) * w
    vals = adjacency[np.asarray(moves)] @ contrib
    vals = vals / 2.0
    return np.clip(vals, 0.0, 1.0)

# f066 exclusive_reach_shift (wide): For each candidate: the change it makes to the opponent's future claim options — number of empty cells that on
def _f066(moves, owner, homes, points, adjacency, turn):
    """For each candidate: the change it makes to the opponent's future claim options — number of empty cells that only the opponent (not me) can still reach after the claim, weighted by points, minus those only I can reach; scaled by total points, clipped."""
    pts = points.astype(np.float64)
    total = max(pts.sum(), 1.0)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0)
    A = adjacency.astype(np.float64)

    my_n = A @ my
    opp_n = A @ opp

    cand_adj = A[moves]                       # (k, N)
    my_after = my_n[None, :] + cand_adj       # (k, N)

    # reachability: an empty cell is reachable by a side if that side has >=1 neighbour there
    reach_me = (my_after > 0) & empty[None, :]      # (k, N)
    reach_op = (opp_n[None, :] > 0) & empty[None, :]  # (k, N) broadcast

    only_op = reach_op & ~reach_me                  # opponent-only remaining reach
    only_me = reach_me & ~reach_op                  # my-only remaining reach

    w = pts[None, :]
    vals = ((only_me.astype(np.float64) - only_op.astype(np.float64)) * w).sum(axis=1) / total
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

name: exclusive_reach_shift

# f056 behind_flip_leverage_vs_denial (wide): Behind-only flip leverage: when my score is not above the opponent's, for each candidate sum points of opponen
def _f056(moves, owner, homes, points, adjacency, turn):
    """Behind-only flip leverage: when my score is not above the opponent's, for each candidate sum points of opponent non-home cells that would flip (points/5, capped) minus the opponent's frontier dominance on empties it touches, scaled by total points; 0 when ahead."""
    s_me = points[owner == 1].sum()
    s_op = points[owner == -1].sum()
    if s_me > s_op:
        return np.zeros(len(moves))

    pts = points.astype(np.float64)
    total = max(pts.sum(), 1.0)
    my = (owner == 1).astype(np.float64)
    opp = (owner == -1).astype(np.float64)
    empty = (owner == 0).astype(np.float64)
    A = adjacency.astype(np.float64)

    my_n = A @ my
    opp_n = A @ opp

    cand_adj = A[moves]                        # (k, N)
    my_after = my_n[None, :] + cand_adj        # (k, N)

    # flip gain: opponent non-home cells where my_after >= opp_n
    is_opp = np.broadcast_to((owner == -1)[None, :], my_after.shape).copy()
    is_opp[:, homes[1]] = False
    flips = is_opp & (my_after >= opp_n[None, :])
    gain = (flips.astype(np.float64) * pts[None, :]).sum(axis=1)

    # in tight/behind spots, deny the opponent's easy value: empties where they dominate
    marg = opp_n[None, :] - my_after            # >0 means opponent dominates that cell
    deny = (np.clip(marg, 0.0, None) * empty[None, :] * pts[None, :]).sum(axis=1)

    vals = (gain - deny) / total
    return np.clip(np.nan_to_num(vals), -1.0, 1.0)

_TERMS = [(_f007, np.array([8.7844])), (_f017, np.array([13.160801])), (_f022, np.array([7.55662])), (_f033, np.array([10.267495])), (_f058, np.array([-0.778037])), (_f068, np.array([0.701527])), (_f072, np.array([-1.213688])), (_f074, np.array([-1.180699])), (_f090, np.array([15.897332])), (_f103, np.array([0.65309])), (_f066, np.array([0.137764])), (_f056, np.array([-0.451023]))]

def priority(moves, owner, homes, points, adjacency, turn):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(moves, owner, homes, points, adjacency, turn), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(moves))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
