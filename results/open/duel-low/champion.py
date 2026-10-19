# Helix v3 policy: duel, gap 54.549%, progress 45.5%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f006 flip_gain_points (deep): Sum of points of opponent cells that this claim would flip (normalised by 15).
def _f006(moves, owner, homes, points, adjacency, turn):
    """Sum of points of opponent cells that this claim would flip (normalised by 15)."""
    A1 = (adjacency & (owner == 1)[None, :]).sum(1)
    Ao = (adjacency & (owner == -1)[None, :]).sum(1)
    cand = adjacency[moves]
    opp_nb = cand & (owner == -1)[None, :]
    flip = opp_nb & (A1[None, :] + 1.0 >= Ao[None, :])
    flip[:, homes[1]] = False
    values = (flip * points[None, :]).sum(1) / 15.0
    return values

# f017 opp_home_distance (deep): Negative BFS graph distance from each candidate to the opponent's home, divided by N.
def _f017(moves, owner, homes, points, adjacency, turn):
    """Negative BFS graph distance from each candidate to the opponent's home, divided by N."""
    N = adjacency.shape[0]
    target = int(homes[1])
    dist = np.full(N, -1, dtype=np.int64)
    dist[target] = 0
    frontier = np.array([target], dtype=np.int64)
    while frontier.size > 0:
        # neighbours of the frontier not yet visited
        nb = adjacency[frontier].any(axis=0)
        nb[dist >= 0] = False
        nxt = np.nonzero(nb)[0]
        dist[nxt] = dist[frontier].min() + 1
        frontier = nxt
    d = dist[moves].astype(np.float64)
    d[d < 0] = N  # unreachable guard (should not happen on a connected board)
    return -d / float(N)

# f018 opponent_pocket_denial (deep): Sum of points of empty opponent-reachable-only neighbours of each candidate, divided by 15.
def _f018(moves, owner, homes, points, adjacency, turn):
    """Sum of points of empty opponent-reachable-only neighbours of each candidate, divided by 15."""
    empty = (owner == 0)
    opp_reach = empty & (adjacency @ (owner == -1).astype(np.int64) > 0)
    mine_reach = empty & (adjacency @ (owner == 1).astype(np.int64) > 0)
    deniable = opp_reach & ~mine_reach
    weighted = points.astype(np.float64) * deniable.astype(np.float64)
    return (adjacency[moves].astype(np.float64) @ weighted) / 15.0

# f026 opp_frontier_value_after_claim (deep): Negative total points of empty cells adjacent to opponent territory after my claim and its flips, divided by 3
def _f026(moves, owner, homes, points, adjacency, turn):
    """Negative total points of empty cells adjacent to opponent territory after my claim and its flips, divided by 30."""
    N = owner.shape[0]
    my_nb = (adjacency & (owner == 1)[None, :]).sum(axis=1)
    opp_nb = (adjacency & (owner == -1)[None, :]).sum(axis=1)

    opp_cells = owner == -1
    empty_cells = owner == 0

    values = np.empty(moves.shape[0], dtype=float)
    for i, c in enumerate(moves):
        # cells adjacent to candidate c that are opponent-owned and not the opponent home
        adj_c = adjacency[:, c]
        flippable = opp_cells & adj_c & (np.arange(N) != homes[1])
        flipped = flippable & (my_nb + 1 >= opp_nb)
        new_opp = opp_cells & ~flipped
        # empty cells (excluding c) adjacent to at least one new_opp cell
        frontier = empty_cells & ~(np.arange(N) == c) & (adjacency[:, new_opp].any(axis=1))
        values[i] = -points[frontier].sum() / 30.0
    return values

# f020 opp_home_path_value_denial (wide): Negative BFS distance from each candidate to the opponent's home, but weighted by the point value of the cells
def _f020(moves, owner, homes, points, adjacency, turn):
    """Negative BFS distance from each candidate to the opponent's home, but weighted by the point value of the cells on that path's frontier: candidates whose short path to the enemy home runs through low-value empty cells are favoured (denial), normalised by N."""
    N = adjacency.shape[0]
    target = int(homes[1])
    dist = np.full(N, -1, dtype=np.int64)
    dist[target] = 0
    frontier = np.array([target], dtype=np.int64)
    while frontier.size > 0:
        nb = adjacency[frontier].any(axis=0)
        nb[dist >= 0] = False
        nxt = np.nonzero(nb)[0]
        dist[nxt] = dist[frontier].min() + 1
        frontier = nxt
    d = dist[moves].astype(np.float64)
    d[d < 0] = N
    # value of empty cells adjacent to each candidate, that lie on a shortest path toward opp home
    dist_all = dist.astype(np.float64)
    dist_all[dist_all < 0] = N
    # candidate's own distance to target
    dm = dist_all[moves]  # (k,)
    # for each candidate, average value of its empty neighbours that are closer to the target
    closer = (dist_all[None, :] < dm[:, None]) & (owner == 0)[None, :]
    nb_mask = adjacency[moves] & closer
    val = (nb_mask * points[None, :]).sum(1)
    cnt = nb_mask.sum(1)
    meanval = val / np.maximum(cnt, 1)
    # combine: favours being close (negative dist) and having low-value approach cells (denial of high-value path)
    return (-d / float(N)) * (0.5 + 0.5 * (1.0 - meanval / 5.0))

# f034 claim_next_turn_exposure (deep): Negative points of each candidate times the capped count of empty neighbours from which the opponent could cla
def _f034(moves, owner, homes, points, adjacency, turn):
    """Negative points of each candidate times the capped count of empty neighbours from which the opponent could claim and flip it next turn."""
    N = owner.shape[0]
    my = (owner == 1)
    opp = (owner == -1)
    empty = (owner == 0)
    opp_home = homes[1]

    A1 = adjacency @ my.astype(np.int64)      # my neighbours per cell
    Ao = adjacency @ opp.astype(np.int64)    # opponent neighbours per cell

    # opponent cells that would flip if I claim c (per candidate)
    # flips[j] = opp cell j adjacent to c, j != opp home, A1[j] + 1 >= Ao[j]
    adj_c = adjacency[moves]                 # (k, N)
    is_opp = opp[None, :]
    not_home = np.ones(N, dtype=bool)
    not_home[opp_home] = False
    flip_cond = (A1[None, :] + 1 >= Ao[None, :])
    flips = adj_c & is_opp & not_home[None, :] & flip_cond   # (k, N)

    f_nb = flips.astype(np.int64)            # (k, N) flipped neighbours of c

    n_my = A1[moves] + f_nb.sum(axis=1)      # (k,)
    n_opp = Ao[moves] - f_nb.sum(axis=1)     # (k,)

    # opp2 = opponent cells not flipped; Aob = their neighbour counts
    opp2 = opp[None, :] & ~flips             # (k, N)
    Aob = opp2.astype(np.int64) @ adjacency.astype(np.int64)  # (k, N)

    threat = empty[None, :] & adj_c & (Aob > 0) & (n_opp[:, None] + 1 >= n_my[:, None])

    tcount = np.minimum(threat.sum(axis=1), 2).astype(np.float64)
    value = -(points[moves].astype(np.float64) / 5.0) * (tcount / 2.0)
    return value

# f031 opp_best_grab_after_claim (deep): Negative (normalised) best one-ply grab value available to the opponent after my claim and its flips.
def _f031(moves, owner, homes, points, adjacency, turn):
    """Negative (normalised) best one-ply grab value available to the opponent after my claim and its flips."""
    N = owner.shape[0]
    my_home = homes[0]
    opp_home = homes[1]
    mine = (owner == 1)
    opp = (owner == -1)
    empty = (owner == 0)
    A1 = adjacency @ mine.astype(np.int64)
    Ao = adjacency @ opp.astype(np.int64)
    pts = points.astype(np.float64)

    out = np.zeros(moves.shape[0], dtype=np.float64)
    for idx in range(moves.shape[0]):
        c = moves[idx]
        # flips: opponent cells adjacent to c, not opp home, with A1[j]+1 >= Ao[j]
        adj_c = adjacency[c]
        flips = adj_c & opp & (np.arange(N) != opp_home) & ((A1 + 1) >= Ao)
        mine2 = mine.copy()
        mine2[c] = True
        mine2 |= flips
        opp2 = opp & ~flips
        A1b = adjacency @ mine2.astype(np.int64)
        Aob = adjacency @ opp2.astype(np.int64)
        legal_e = empty & (Aob > 0)
        if not legal_e.any():
            out[idx] = 0.0
            continue
        # gain[e] = points[e] + sum over j adjacent to e with mine2[j], j != my home, Aob[j]+1 >= A1b[j]
        flip_back_mask = mine2 & (np.arange(N) != my_home) & ((Aob + 1) >= A1b)
        flip_back_pts = np.where(flip_back_mask, pts, 0.0)
        # for each empty e: sum of flip_back_pts over neighbours
        gain = pts + adjacency @ flip_back_pts
        best = gain[legal_e].max()
        out[idx] = -best / 30.0
    return out

# f042 two_step_expansion_value (deep): Sum of points of empty cells reachable in exactly two claims (excluding step-1 cells and c), /30.
def _f042(moves, owner, homes, points, adjacency, turn):
    """Sum of points of empty cells reachable in exactly two claims (excluding step-1 cells and c), /30."""
    E = (owner == 0)
    k = moves.shape[0]
    N = owner.shape[0]
    values = np.zeros(k, dtype=float)
    for i in range(k):
        c = moves[i]
        step1 = E & adjacency[c]
        # union of empty neighbours of step-1 cells
        step2 = np.zeros(N, dtype=bool)
        s1_idx = np.nonzero(step1)[0]
        if s1_idx.size > 0:
            step2 = (adjacency[s1_idx].any(axis=0)) & E
        step2[c] = False
        step2[s1_idx] = False
        values[i] = points[step2].sum() / 30.0
    return values

# f049 three_step_expansion_value (deep): Sum of points of empty cells reachable in exactly three claims (excluding c and the 1- and 2-step shells), /30
def _f049(moves, owner, homes, points, adjacency, turn):
    """Sum of points of empty cells reachable in exactly three claims (excluding c and the 1- and 2-step shells), /30."""
    empty = (owner == 0)
    pts = points.astype(float)
    A = adjacency[moves]  # (k, N) bool
    Af = adjacency.astype(float)
    s1 = A & empty[None, :]
    s2 = ((s1.astype(float) @ Af) > 0) & empty[None, :] & ~s1 & ~A
    s3 = ((s2.astype(float) @ Af) > 0) & empty[None, :] & ~s2 & ~s1 & ~A
    values = (s3.astype(float) @ pts) / 30.0
    return values

# f059 uncontested_two_step_value (deep): Sum of points of empty cells reachable in exactly two claims from the candidate that have no opponent neighbou
def _f059(moves, owner, homes, points, adjacency, turn):
    """Sum of points of empty cells reachable in exactly two claims from the candidate that have no opponent neighbour, divided by 30."""
    N = owner.shape[0]
    E = (owner == 0)
    Ao = adjacency @ (owner == -1).astype(np.int64)
    uncontested = E & (Ao == 0)
    pts = points.astype(np.float64)
    out = np.zeros(moves.shape[0], dtype=np.float64)
    for i, c in enumerate(moves):
        step1 = E & adjacency[c]
        if not step1.any():
            continue
        step2 = E & adjacency[step1].any(axis=0) & ~adjacency[c]
        step2[c] = False
        out[i] = pts[step2 & uncontested].sum() / 30.0
    return out

# f071 soft_flip_pressure (wide): Sum over opponent cells adjacent to the candidate of points * (my-neighbour surplus toward flip), i.e. how clo
def _f071(moves, owner, homes, points, adjacency, turn):
    """Sum over opponent cells adjacent to the candidate of points * (my-neighbour surplus toward flip), i.e. how close each adjacent opponent cell is to flipping, weighted by value, /15."""
    A1 = (adjacency & (owner == 1)[None, :]).sum(1).astype(np.float64)
    Ao = (adjacency & (owner == -1)[None, :]).sum(1).astype(np.float64)
    cand = adjacency[moves]
    opp_nb = cand & (owner == -1)[None, :]
    # margin: A1+1 - Ao  (>=0 means flips).  Use a soft proximity: 1/(1+max(margin,0)) so
    # already-flipping (margin>=0) cells count fully and near-miss cells (margin<0) count partially.
    margin = (A1[None, :] + 1.0) - Ao[None, :]
    prox = np.where(margin >= 0.0, 1.0, 1.0 / (1.0 + (-margin)))
    w = opp_nb.astype(np.float64) * prox * points[None, :].astype(np.float64)
    w[:, homes[1]] = 0.0
    return w.sum(1) / 15.0

# f102 net_flip_value_after_recapture (deep): (gross points flipped by the claim minus points of flipped cells the opponent can recapture next turn) / 15.
def _f102(moves, owner, homes, points, adjacency, turn):
    """(gross points flipped by the claim minus points of flipped cells the opponent can recapture next turn) / 15."""
    N = owner.shape[0]
    k = moves.shape[0]
    mine = (owner == 1)
    opp = (owner == -1)
    empty = (owner == 0)
    opp_home = homes[1]

    A1 = adjacency @ mine.astype(np.int64)   # my neighbour counts
    Ao = adjacency @ opp.astype(np.int64)    # opponent neighbour counts
    E = adjacency @ empty.astype(np.int64)   # empty neighbour counts

    adj_m = adjacency[moves]                 # (k, N)
    pts = points.astype(np.float64)

    # flipped[c,j]: opponent cell j (not opp home) adjacent to c, flips after my claim
    is_opp = opp[None, :] & (np.arange(N)[None, :] != opp_home)
    flips = adj_m & is_opp & ((A1[None, :] + 1) >= Ao[None, :])   # (k, N)

    # after claim: my count of j = A1[j] + adj_m[c,j]; opp count = Ao[j] - flips[c,j]
    my_after = A1[None, :] + adj_m.astype(np.int64)
    opp_after = Ao[None, :] - flips.astype(np.int64)

    # empty neighbours of j excluding c: E[j] - adj_m[c,j] (c is empty before the claim)
    empty_other = E[None, :] - adj_m.astype(np.int64)

    # recapturable: flipped and opponent can reach a flip with one empty neighbour e != c
    recapturable = flips & (empty_other >= 1) & ((opp_after + 1) >= my_after)

    G = (flips * pts[None, :]).sum(axis=1)
    R = (recapturable * pts[None, :]).sum(axis=1)

    return (G - R) / 15.0

_TERMS = [(_f006, np.array([48.811177])), (_f017, np.array([16.737476])), (_f018, np.array([3.104503])), (_f026, np.array([37.928292])), (_f020, np.array([6.633318])), (_f034, np.array([42.043245])), (_f031, np.array([83.277332])), (_f042, np.array([2.025657])), (_f049, np.array([0.628003])), (_f059, np.array([1.014546])), (_f071, np.array([43.063594])), (_f102, np.array([-9.125812]))]

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
