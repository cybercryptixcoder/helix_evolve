# Helix v3 policy: duel, gap 56.794%, progress 43.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 flip_pressure_expansion (wide): Tension: for each candidate, how many of its empty neighbours it would flip-control plus a bonus for being adj
def _f003(moves, owner, homes, points, adjacency, turn):
    """Tension: for each candidate, how many of its empty neighbours it would flip-control plus a bonus for being adjacent to weak enemy cells (flip pressure)."""
    N = len(owner)
    my_cells = owner == 1
    opp_cells = owner == -1
    empties = owner == 0
    opp_home = homes[1]

    # For each cell, count of my neighbours and opp neighbours
    adj_f = adjacency.astype(float)
    my_nb = adj_f @ my_cells.astype(float)
    opp_nb = adj_f @ opp_cells.astype(float)
    empty_nb = adj_f @ empties.astype(float)

    # How many empty neighbours each candidate would open up (expansion potential)
    expansion = empty_nb[moves]

    # After claiming candidate, I own my_nb[c]+1 of its neighbours; count enemy neighbours it could flip:
    # enemy cell e adjacent to candidate flips if my_total >= opp_total at e.
    # Estimate: number of enemy neighbours of candidate that are "vulnerable" (opp_nb - my_nb small)
    cand_opp_nb = adj_f[moves] @ opp_cells.astype(float)  # enemy neighbours of candidate
    # For enemy neighbours, how close we are to flipping them: my_nb at that enemy after claim
    # candidate contributes +1 to my_nb at each of its enemy neighbours
    vuln = (adj_f[moves] @ ((opp_cells).astype(float) * (my_nb + 1 - opp_nb)))  # sum of (my-opp+1) over enemy nbs, positive => flippable
    flippable = (adj_f[moves] @ (opp_cells.astype(float) * ((my_nb + 1) >= opp_nb))).astype(float)

    # Also weight enemy cells by points
    flip_points = adj_f[moves] @ (opp_cells.astype(float) * points * ((my_nb + 1) >= opp_nb))

    denom = float(N) + 1e-9
    return np.stack([
        expansion / denom,
        flippable / 6.0,
        flip_points / 30.0,
        vuln / denom,
    ], axis=1)

# f004 safe_frontier_share (wide): Fraction of a candidate's empty neighbours that would be lost to the opponent's reach next (blocking value).
def _f004(moves, owner, homes, points, adjacency, turn):
    """Fraction of a candidate's empty neighbours that would be lost to the opponent's reach next (blocking value)."""
    N = owner.shape[0]
    mine = owner == 1
    theirs = owner == -1
    empty = owner == 0
    # opponent frontier: empty cells adjacent to any opponent cell
    opp_front = (adjacency[:, theirs].any(axis=1)) & empty
    # my frontier: empty cells adjacent to my cells
    my_front = (adjacency[:, mine].any(axis=1)) & empty
    # for each candidate, count empty neighbours that are opponent-frontier (contested/vulnerable)
    m = np.asarray(moves, dtype=int)
    neigh = adjacency[m][:, :]  # (k, N)
    empty_neigh = neigh & empty[None, :]
    n_empty = empty_neigh.sum(axis=1)
    opp_reach = (empty_neigh & opp_front[None, :]).sum(axis=1)
    safe = (n_empty - opp_reach).astype(float)
    return safe / np.maximum(n_empty, 1.0)

name: safe_frontier_share

# f007 defensive_safety (deep): Own-neighbour surplus around each candidate, normalised by its neighbour count.
def _f007(moves, owner, homes, points, adjacency, turn):
    """Own-neighbour surplus around each candidate, normalised by its neighbour count."""
    nb = adjacency[moves]                      # (k, N) neighbours of each candidate
    deg = nb.sum(axis=1)                       # (k,) neighbour counts
    own = (nb & (owner == 1)[None, :]).sum(axis=1)
    opp = (nb & (owner == -1)[None, :]).sum(axis=1)
    surplus = (own - opp) / np.maximum(1, deg)
    return surplus.astype(float)

# f024 opp_home_distance (deep): 1 - (BFS graph distance from candidate to opponent home) / max finite distance, clipped to [0,1].
def _f024(moves, owner, homes, points, adjacency, turn):
    """1 - (BFS graph distance from candidate to opponent home) / max finite distance, clipped to [0,1]."""
    N = adjacency.shape[0]
    opp_home = int(homes[1])
    # BFS from opponent home over the whole board, vectorised by frontier layers
    dist = np.full(N, -1, dtype=np.int64)
    dist[opp_home] = 0
    frontier = np.array([opp_home], dtype=np.int64)
    d = 0
    while frontier.size > 0:
        d += 1
        # neighbours of the frontier
        nbrs = adjacency[frontier].any(axis=0)
        new = np.nonzero(nbrs & (dist < 0))[0]
        if new.size == 0:
            break
        dist[new] = d
        frontier = new
    finite = dist[dist >= 0]
    max_d = int(finite.max()) if finite.size > 0 else 0
    denom = max(1, max_d)
    dm = dist[moves].astype(np.float64)
    # unreachable candidates (shouldn't happen on connected board) -> treat as far
    dm = np.where(dm < 0, float(denom), dm)
    vals = 1.0 - dm / float(denom)
    return np.clip(vals, 0.0, 1.0)

# f028 tempo_threat_vs_secured (wide): Tempo urgency: weighted points of my vulnerable cells the opponent could flip by expanding next to a candidate
def _f028(moves, owner, homes, points, adjacency, turn):
    """Tempo urgency: weighted points of my vulnerable cells the opponent could flip by expanding next to a candidate's empty neighbours, gated by lateness, minus uncontested value it secures."""
    N = owner.shape[0]
    mine = owner == 1
    theirs = owner == -1
    empty = owner == 0
    adj_f = adjacency.astype(np.float64)
    my_nb = adj_f @ mine.astype(np.float64)
    opp_nb = adj_f @ theirs.astype(np.float64)
    empty_nb = adj_f @ empty.astype(np.float64)

    m = np.asarray(moves, dtype=int)

    empty_neigh = adjacency[m] & empty[None, :]            # (k, N) bool
    opp_front = (adj_f @ theirs.astype(np.float64)) > 0.5  # empty cells adjacent to opponent

    weak_mine = mine & (my_nb <= opp_nb)
    vuln_per_empty = adj_f @ ((weak_mine * points).astype(np.float64))  # points lost if that empty is claimed

    opp_threat = (empty_neigh.astype(np.float64) @ vuln_per_empty) / (
        np.maximum(empty_nb[m], 1.0) + 1.0
    )

    uncontested = empty_neigh & (~opp_front[None, :])
    secured = (uncontested.astype(np.float64) * points[None, :]).sum(axis=1) / (points.sum() + 1e-9)

    empties_left = float(empty.sum())
    total_empty0 = max(1.0, float(N - 2))
    lateness = 1.0 - empties_left / total_empty0
    urgency = (opp_threat * lateness - secured * (1.0 - lateness))
    return np.tanh(urgency)

# f033 contested_corridor_differential (wide): Distance from candidate to opponent home, but measured only through empty cells (contested corridor), inverted
def _f033(moves, owner, homes, points, adjacency, turn):
    """Distance from candidate to opponent home, but measured only through empty cells (contested corridor), inverted and normalised; my-home distance subtracted as a signed differential."""
    N = adjacency.shape[0]
    opp_home = int(homes[1])
    my_home = int(homes[0])
    empty = (owner == 0)

    def bfs(src, passable):
        dist = np.full(N, -1, dtype=np.int64)
        dist[src] = 0
        frontier = np.array([src], dtype=np.int64)
        d = 0
        while frontier.size > 0:
            d += 1
            nbrs = adjacency[frontier].any(axis=0)
            new = np.nonzero(nbrs & (dist < 0) & passable)[0]
            if new.size == 0:
                break
            dist[new] = d
            frontier = new
        return dist

    # corridor through empty cells only (start from opp home which is not empty, but its neighbours must be empty)
    passable = empty.copy()
    passable[opp_home] = True
    passable[my_home] = True
    d_opp = bfs(opp_home, passable)
    d_my = bfs(my_home, passable)

    def norm(d):
        finite = d[d >= 0]
        mx = float(finite.max()) if finite.size > 0 else 1.0
        mx = max(mx, 1.0)
        v = d[moves].astype(np.float64)
        v = np.where(v < 0, mx, v)
        return v / mx

    to_opp = norm(d_opp)
    to_my = norm(d_my)
    # positive when candidate is close to opp home and far from my home
    return np.clip(to_my - to_opp, -1.0, 1.0)

name: contested_corridor_differential

# f049 phase_gated_flip_vs_safety (deep): (1-t)*flip_gain - t*safety, t=turn/(N-2); flip_gain = points of enemy cells flipped by claiming m / total poin
def _f049(moves, owner, homes, points, adjacency, turn):
    """(1-t)*flip_gain - t*safety, t=turn/(N-2); flip_gain = points of enemy cells flipped by claiming m / total points, safety = (my_nb-opp_nb)/max(1,my_nb+opp_nb)."""
    N = owner.shape[0]
    moves = np.asarray(moves, dtype=int)
    k = moves.shape[0]
    t = turn / max(1, N - 2)

    total_points = float(points.sum())
    if total_points <= 0:
        total_points = 1.0

    opp_home = homes[1]

    # Neighbour counts for each candidate (before claim).
    adj_m = adjacency[moves]  # (k, N)
    my_nb = (adj_m & (owner == 1)[None, :]).sum(axis=1).astype(float)
    opp_nb = (adj_m & (owner == -1)[None, :]).sum(axis=1).astype(float)

    # Flip gain: enemy neighbours c of m (excluding opp home) that would flip
    # after claiming m. After claim, m is mine. For each such c, count my
    # neighbours vs owner's neighbours among c's neighbours.
    # owner after claim: m becomes 1.
    owner_after = owner.copy()
    owner_after[moves] = 1  # all candidates become mine (only one is claimed, but
    # for counting neighbours of c, m is the only changed cell; other candidates
    # are not adjacent to c in a way that matters unless they are neighbours of c
    # and were empty. To be faithful, we must not flip other candidates. So handle
    # per-candidate properly below.)

    flip_gain = np.zeros(k, dtype=float)
    for i in range(k):
        m = moves[i]
        # enemy neighbours of m, excluding opp home
        nb = np.where(adjacency[m])[0]
        enemy_nbs = nb[(owner[nb] == -1) & (nb != opp_home)]
        gain = 0.0
        for c in enemy_nbs:
            # after claiming m, count neighbours of c
            c_nb = np.where(adjacency[c])[0]
            my_count = 0
            opp_count = 0
            for d in c_nb:
                if d == m:
                    my_count += 1
                elif owner[d] == 1:
                    my_count += 1
                elif owner[d] == -1:
                    opp_count += 1
            if my_count >= opp_count:
                gain += points[c]
        flip_gain[i] = gain / total_points

    safety = (my_nb - opp_nb) / np.maximum(1.0, my_nb + opp_nb)

    return (1.0 - t) * flip_gain - t * safety

# f043 net_flip_swing (wide): Per-candidate net flip swing: points of enemy cells that would flip minus points of my cells that would flip b
def _f043(moves, owner, homes, points, adjacency, turn):
    """Per-candidate net flip swing: points of enemy cells that would flip minus points of my cells that would flip back, only counting cells contested by the opponent (empty neighbours adjacent to enemy), scaled by how late the game is."""
    N = owner.shape[0]
    mine = owner == 1
    theirs = owner == -1
    empty = owner == 0
    adj_f = adjacency.astype(np.float64)
    m = np.asarray(moves, dtype=int)

    theirs_f = theirs.astype(np.float64)
    mine_f = mine.astype(np.float64)
    opp_nb = adj_f @ theirs_f          # enemy neighbours per cell
    my_nb = adj_f @ mine_f             # my neighbours per cell

    # Claim m: my count at each neighbour becomes my_nb + adjacency[m].
    # Enemy cells flip if my_nb + adj(m,) >= opp_nb.
    add_me = adjacency[m].astype(np.float64)  # (k, N)
    post_my = my_nb[None, :] + add_me         # (k, N)
    flip_enemy = (theirs[None, :] & (post_my >= opp_nb[None, :]))
    # exclude enemy home
    flip_enemy[:, homes[1]] = False
    gain = (flip_enemy.astype(np.float64) * points[None, :]).sum(axis=1)

    # Enemy response threat: my cells adjacent to m's opponent-contested empty neighbours
    opp_front = opp_nb > 0.5                  # cells adjacent to enemy
    empty_neigh = adjacency[m] & empty[None, :]   # (k, N)
    contested = empty_neigh & opp_front[None, :]
    # for each contested empty e, points I could lose = points of my cells adjacent to e
    my_pts_adj = adj_f @ (mine_f * points)
    risk = contested.astype(np.float64) @ my_pts_adj

    empties_left = float(empty.sum())
    lateness = 1.0 - empties_left / max(1.0, float(N - 2))

    total_pts = float(points.sum()) + 1e-9
    net = (gain - risk * lateness) / total_pts
    return np.tanh(net)

name: net_flip_swing

# f058 flip_pressure_per_exposure (deep): pressure / (pressure + exposure + 1), where pressure = empty neighbours of m with my_nb > opp_nb after claim p
def _f058(moves, owner, homes, points, adjacency, turn):
    """pressure / (pressure + exposure + 1), where pressure = empty neighbours of m with my_nb > opp_nb after claim plus 0.5 * enemy neighbours of m with my_nb >= opp_nb after claim, and exposure = my cells adjacent to m's empty neighbours with opp_nb+1 >= my_nb."""
    N = owner.shape[0]
    k = moves.shape[0]
    mine = (owner == 1)
    opp = (owner == -1)
    empty = (owner == 0)

    # neighbour counts per cell (current board)
    my_nb = adjacency @ mine.astype(np.float64)      # (N,)
    opp_nb = adjacency @ opp.astype(np.float64)      # (N,)

    # after claiming m: m becomes mine, so each neighbour of m gains +1 my_nb
    # For a cell c adjacent to m, post-claim my_nb = my_nb[c] + 1 (if c != m)
    # Build per-candidate post-claim counts for neighbours of m.
    adj_m = adjacency[moves]                          # (k, N) neighbours of each candidate
    # post-claim my_nb for any cell c: my_nb[c] + (adjacency[c, m] and c != m)
    # since m is empty, my_nb[m]=0; for neighbours c of m, my_nb[c] += 1
    post_my = my_nb[None, :] + adj_m.astype(np.float64)   # (k, N)
    post_opp = np.broadcast_to(opp_nb[None, :], (k, N))

    # pressure part 1: empty neighbours of m with post my_nb > post opp_nb
    empty_mask = empty[None, :] & adj_m
    p1 = np.sum(empty_mask & (post_my > post_opp), axis=1)

    # pressure part 2: enemy neighbours of m with post my_nb >= post opp_nb
    enemy_mask = opp[None, :] & adj_m
    p2 = np.sum(enemy_mask & (post_my >= post_opp), axis=1)

    pressure = p1 + 0.5 * p2

    # exposure: my cells adjacent to m's empty neighbours with opp_nb+1 >= my_nb
    # empty neighbours of m: cells e with empty[e] and adjacency[m,e]
    # my cells adjacent to such e: cells c with mine[c] and adjacency[c,e]
    # Compute per candidate: for each empty neighbour e of m, check my cells adjacent to e.
    # exposure_count[m] = number of (c) my cells adjacent to some empty neighbour of m
    #   with opp_nb[c]+1 >= my_nb[c]
    # Vectorise: for each candidate, gather empty neighbours, then their neighbours.
    # Use matrix: empty_nb_of_m = empty_mask (k,N). For each cell c (mine), it is exposed
    #   if exists e: empty_mask[m,e] and adjacency[e,c] and opp_nb[c]+1 >= my_nb[c].
    # exposed_cell_mask (N,) independent of m: my cell c with opp_nb[c]+1 >= my_nb[c]
    exposed_cell = mine & (opp_nb + 1 >= my_nb)       # (N,)
    # adjacency from empty neighbours to exposed cells: for candidate m, count exposed cells
    #   adjacent to any empty neighbour of m.
    # empty_nb_adj[m, c] = sum_e empty_mask[m,e] * adjacency[e,c]
    # = (empty_mask @ adjacency)  -> (k, N)
    empty_nb_adj = empty_mask.astype(np.float64) @ adjacency.astype(np.float64)  # (k,N)
    exposure = np.sum((empty_nb_adj > 0) & exposed_cell[None, :], axis=1)

    denom = pressure + exposure + 1.0
    return pressure / denom

# f063 two_hop_denial_value (deep): Drop in opponent's two-hop empty reach value when claiming m, normalised by total points.
def _f063(moves, owner, homes, points, adjacency, turn):
    """Drop in opponent's two-hop empty reach value when claiming m, normalised by total points."""
    N = owner.shape[0]
    empty = (owner == 0)
    opp = (owner == -1)
    total_points = float(points.sum())

    # Empty cells adjacent to an opponent-owned cell (one-hop frontier)
    opp_nb_empty = adjacency[opp].any(axis=0) & empty  # (N,)

    # Two-hop reachable empty cells: empty e with an empty neighbour f adjacent to opp
    # reach2[e] = empty[e] and exists f: empty[f] & opp_nb_empty[f] & adjacency[e,f]
    reach2 = empty & (adjacency[:, opp_nb_empty].any(axis=1))

    V_all = float(points[reach2].sum())

    if V_all == 0.0:
        return np.zeros(len(moves))

    # For each candidate m: recompute reach2 with m removed from empty set.
    # Removing m only affects reach2 via:
    #  - m itself no longer counted (if it was reach2)
    #  - cells e whose only qualifying f was m (m was opp_nb_empty and empty)
    #  - m no longer being a valid e
    # Vectorised: for each candidate, compute reach2_after.
    k = len(moves)
    out = np.zeros(k)

    # Precompute per-cell: is cell a valid "f" (empty & opp_nb_empty)
    f_valid = opp_nb_empty  # already empty & opp-adjacent

    # For each candidate m, we need reach2_after.
    # reach2_after[e] = empty_after[e] & exists f: f_valid_after[f] & adj[e,f]
    # where empty_after = empty & (cell != m), f_valid_after = f_valid & (cell != m)
    # We can compute this per candidate using matrix ops.
    # adjacency[:, f_valid] gives for each e which valid f's it touches.
    f_idx = np.where(f_valid)[0]
    # A[e, j] = adjacency[e, f_idx[j]]
    A = adjacency[:, f_idx]  # (N, nf)
    # For each candidate m, the f's removed are those f_idx == m (if m is f_valid)
    # and e's removed is m itself.
    # reach2_after[e] = empty[e] & (e != m) & any_j (A[e,j] & (f_idx[j] != m))
    # Note: if m is not f_valid, no f removed.
    # Compute count of valid f per e, and whether m is among them.
    counts = A.sum(axis=1)  # (N,)
    # For candidate m, if m is f_valid, find its column index
    # Build mapping cell -> column in f_idx
    col_of = -np.ones(N, dtype=int)
    col_of[f_idx] = np.arange(len(f_idx))

    for i in range(k):
        m = moves[i]
        c = col_of[m]
        if c >= 0:
            # m is a valid f; cells e with A[e,c] lose one valid f
            new_counts = counts - A[:, c].astype(int)
        else:
            new_counts = counts
        reach2_after = empty & (np.arange(N) != m) & (new_counts > 0)
        V_after = float(points[reach2_after].sum())
        out[i] = (V_all - V_after) / (total_points + 1.0)

    return out

# f078 opponent_best_counter_value (wide): For each candidate: the opponent's best immediate counter-claim value in points (a max over empty cells adjace
def _f078(moves, owner, homes, points, adjacency, turn):
    """For each candidate: the opponent's best immediate counter-claim value in points (a max over empty cells adjacent to the candidate's new frontier), scaled by how late the game is and normalised by total board points."""
    N = owner.shape[0]
    mine = owner == 1
    theirs = owner == -1
    empty = owner == 0
    adj_f = adjacency.astype(np.float64)
    m = np.asarray(moves, dtype=int)

    my_nb = adj_f @ mine.astype(np.float64)
    opp_nb = adj_f @ theirs.astype(np.float64)

    # After claiming m: each empty cell e adjacent to m gets my_nb[e]+1 from me.
    # Opponent's next claim: any empty cell adjacent to their cells.
    opp_front = empty & (opp_nb > 0.5)

    # Value the opponent would secure by claiming an empty cell e next (points[e]
    # plus points of my cells it would flip, roughly opp_nb[e]+1 >= my_nb[e]).
    vulnerable = mine & (opp_nb + 1 >= my_nb)
    flip_val = adj_f @ (vulnerable.astype(np.float64) * points.astype(np.float64))
    cell_val = points.astype(np.float64) + flip_val  # value of claiming an empty cell

    # For each candidate m: consider empty cells e adjacent to m (new contested zone)
    # that the opponent could grab. Their best such value, blocked by my presence:
    # if I claim m, my_nb at e increases, making flips less likely -- approximate
    # by counting e as opp-reachable with weight cell_val[e] only where opp_front.
    empty_neigh = adjacency[m] & empty[None, :]                # (k, N)
    opp_grab = empty_neigh & opp_front[None, :]                # (k, N) contested empties
    # best value opponent gets from one of these cells
    vals = np.where(opp_grab, cell_val[None, :], 0.0)
    best = vals.max(axis=1)

    lateness = 1.0 - float(empty.sum()) / max(1.0, float(N - 2))
    total = float(points.sum()) + 1e-9
    return np.tanh(best * lateness / total)

name: opponent_best_counter_value

# f076 value_weighted_surplus_phase (wide): Own-vs-opponent neighbour surplus around each candidate, but weighted by neighbour cell value and gated by the
def _f076(moves, owner, homes, points, adjacency, turn):
    """Own-vs-opponent neighbour surplus around each candidate, but weighted by neighbour cell value and gated by the game phase (early: raw surplus; late: point-weighted surplus)."""
    N = owner.shape[0]
    m = np.asarray(moves, dtype=int)
    nb = adjacency[m]                                # (k, N)
    deg = nb.sum(axis=1).astype(np.float64)          # (k,)
    mine = (owner == 1)[None, :]
    theirs = (owner == -1)[None, :]

    # raw surplus (thread of the parent)
    own = (nb & mine).sum(axis=1).astype(np.float64)
    opp = (nb & theirs).sum(axis=1).astype(np.float64)
    raw = (own - opp) / np.maximum(1.0, deg)

    # point-weighted surplus: high-value neighbours count more
    pt = points.astype(np.float64)[None, :]
    own_p = (nb * mine * pt).sum(axis=1)
    opp_p = (nb * theirs * pt).sum(axis=1)
    denom_p = np.maximum(1.0, (nb * pt).sum(axis=1))
    weighted = (own_p - opp_p) / denom_p

    # phase gate: early we care about raw structure, late about points
    t = turn / max(1.0, float(N - 2))
    t = min(max(t, 0.0), 1.0)
    out = (1.0 - t) * raw + t * weighted
    return np.clip(out, -1.0, 1.0)

name: value_weighted_surplus_phase

# f095 contested_gated_surplus (deep): Contested-gated point-weighted own-vs-opponent neighbour surplus per candidate.
def _f095(moves, owner, homes, points, adjacency, turn):
    """Contested-gated point-weighted own-vs-opponent neighbour surplus per candidate."""
    nb = adjacency[moves]                      # (k, N) neighbours of each candidate
    pts = points.astype(np.float64)            # (N,)
    own_mask = (owner == 1)                    # (N,)
    opp_mask = (owner == -1)                   # (N,)
    own = (nb * own_mask[None, :] * pts[None, :]).sum(axis=1)   # (k,)
    opp = (nb * opp_mask[None, :] * pts[None, :]).sum(axis=1)   # (k,)
    contested = (nb & opp_mask[None, :]).any(axis=1).astype(np.float64)  # (k,)
    denom = np.maximum(1.0, own + opp)
    return contested * (own - opp) / denom

_TERMS = [(_f003, np.array([-15.719898, 27.343335, 190.985902, -108.972483])), (_f004, np.array([5.856094])), (_f007, np.array([-7.931156])), (_f024, np.array([6.761238])), (_f028, np.array([-3.592469])), (_f033, np.array([-0.622632])), (_f049, np.array([9.164943])), (_f043, np.array([247.382633])), (_f058, np.array([-0.852552])), (_f063, np.array([-29.849532])), (_f078, np.array([-5.884459])), (_f076, np.array([0.357102])), (_f095, np.array([3.935023]))]

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
