# Helix v3 policy: duel, gap 55.105%, progress 44.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f007 claimed_cell_safety (deep): Normalised neighbour margin (my_nb - op_nb)/(my_nb + op_nb + 1) of each candidate, scaled by its point value /
def _f007(moves, owner, homes, points, adjacency, turn):
    """Normalised neighbour margin (my_nb - op_nb)/(my_nb + op_nb + 1) of each candidate, scaled by its point value / 5."""
    mine = (owner == 1).astype(float)
    theirs = (owner == -1).astype(float)
    my_nb = adjacency @ mine
    op_nb = adjacency @ theirs
    margin = my_nb[moves] - op_nb[moves]
    tot = my_nb[moves] + op_nb[moves]
    return (margin / (tot + 1.0)) * (points[moves] / 5.0)

# f001 flip_cascade_gain (wide): Score of the flip cascade a claim could trigger: opponent cells adjacent to the claim weighted by their points
def _f001(moves, owner, homes, points, adjacency, turn):
    """Score of the flip cascade a claim could trigger: opponent cells adjacent to the claim weighted by their points, minus own cells that would be outnumbered and lost."""
    N = len(owner)
    my_count = (owner == 1).astype(int)
    opp_count = (owner == -1).astype(int)
    adj = adjacency.astype(int)
    # after claiming each candidate, my neighbour count on that cell's neighbours
    # candidate claim: add 1 to my_count at that cell
    # for each candidate m, compute hypothetical my neighbour counts of opponent cells adjacent to m
    k = len(moves)
    out = np.zeros(k)
    total_points = float(points.sum()) or 1.0
    own_home = homes[0]
    opp_home = homes[1]
    for i, m in enumerate(moves):
        # neighbours of m
        nb = np.where(adjacency[m])[0]
        gain = 0.0
        for c in nb:
            if c == opp_home or owner[c] != -1:
                continue
            # after claim, my neighbour count of c includes m as owned
            nbrs_c = np.where(adjacency[c])[0]
            my_n = my_count[nbrs_c].sum() + (1 if m not in nbrs_c else 0)  # m is a neighbour of c
            # m is neighbour of c, and m becomes owned -> my_count already counts owners; add 1
            my_n = my_count[nbrs_c].sum()
            if m in nbrs_c:
                my_n += 1
            opp_n = opp_count[nbrs_c].sum()
            if my_n >= opp_n:
                gain += points[c]
        out[i] = gain
    # normalise
    return out / total_points

# f002 claim_flip_point_swing (wide): Net point swing of the immediate claim+flip: points gained by me minus points the opponent loses, per candidat
def _f002(moves, owner, homes, points, adjacency, turn):
    """Net point swing of the immediate claim+flip: points gained by me minus points the opponent loses, per candidate, normalised."""
    N = owner.shape[0]
    my = (owner == 1)
    opp = (owner == -1)
    # neighbours counts for each cell
    # For each candidate c: after claiming c, my ownership gains 1 at c.
    # A neighbour v of c owned by opponent flips if my_neighbours(v) >= opp_neighbours(v) after claim,
    # and v is not opponent's home.
    adj = adjacency.astype(np.int32)
    my_count = adj @ my.astype(np.int32)      # (N,) my neighbours per cell
    opp_count = adj @ opp.astype(np.int32)    # (N,) opp neighbours per cell
    # after claiming candidate c, my_count at neighbour v increases by 1 if adj[v,c]
    cand = moves
    # my_count_after[v, c] = my_count[v] + adj[v,c]
    # flip condition at v given candidate c: v opponent, v != opp home, and my_count[v]+adj[v,c] >= opp_count[v]
    opp_home = homes[1]
    is_opp_cell = opp & (np.arange(N) != opp_home)
    # build (N, k)
    adj_c = adj[:, cand].astype(np.int32)             # (N, k)
    my_after = my_count[:, None] + adj_c              # (N, k)
    flips = is_opp_cell[:, None] & (my_after >= opp_count[:, None]) & (adj_c > 0)
    flip_pts = (flips * points[:, None]).sum(axis=0)  # (k,)
    claim_pts = points[cand].astype(float)
    total_pts = float(points.sum()) + 1e-9
    return (claim_pts + flip_pts) / total_pts

# f008 denial_by_opponent_simulation (deep): Simulated opponent value of each candidate: its points plus the points of my non-home cells it would flip if t
def _f008(moves, owner, homes, points, adjacency, turn):
    """Simulated opponent value of each candidate: its points plus the points of my non-home cells it would flip if the opponent claimed it, normalised by total board points."""
    mine = (owner == 1).astype(float)
    theirs = (owner == -1).astype(float)
    my_nb = adjacency @ mine
    op_nb = adjacency @ theirs
    adj_m = adjacency[moves]                      # (k, N)
    my_cell = (owner == 1)[None, :]               # (1, N)
    allow = np.ones(owner.shape[0], bool)
    allow[homes[0]] = False
    op_after = op_nb[None, :] + adj_m             # (k, N)
    flips = my_cell & adj_m & allow[None, :] & (op_after >= my_nb[None, :])
    loss = points[moves] + (flips * points[None, :]).sum(axis=1)
    return loss / max(points.sum(), 1.0)

# f015 access_race_empty_points (deep): Points of empty cells I reach strictly sooner than the opponent after claiming each candidate, normalised by t
def _f015(moves, owner, homes, points, adjacency, turn):
    """Points of empty cells I reach strictly sooner than the opponent after claiming each candidate, normalised by total points."""
    pts = points.astype(float)
    tot = points.sum() + 1.0
    INF = 1e6
    adj = adjacency.astype(float)
    N = owner.shape[0]
    my = (owner == 1)
    opp = (owner == -1)
    emp = (owner == 0)

    def bfs(sources, allowed):
        d = np.full(N, INF, dtype=float)
        d[sources] = 0.0
        for step in range(1, N + 1):
            frontier = (d == step - 1)
            if not frontier.any():
                break
            nb = frontier.astype(float) @ adj
            new = (nb > 0) & (d > step) & allowed
            if not new.any():
                break
            d[new] = step
        return d

    d_me = bfs(my, emp | my)
    d_op = bfs(opp, emp | opp)

    k = moves.shape[0]
    d_m = np.full((k, N), INF, dtype=float)
    d_m[np.arange(k), moves] = 0.0
    for step in range(1, N + 1):
        frontier = (d_m == step - 1)
        if not frontier.any():
            break
        nb = frontier.astype(float) @ adj
        new = (nb > 0) & (d_m > step) & emp[None, :]
        if not new.any():
            break
        d_m[new] = step

    d_new = np.minimum(d_me[None, :], d_m)
    margin = d_op[None, :] - d_new
    weight = (margin > 0).astype(float) + 0.5 * (margin == 0).astype(float)
    val = pts[None, :] * weight * emp[None, :]
    return val.sum(axis=1) / tot

# f013 two_ply_best_reply_swing (deep): Immediate claim+flip point gain minus the opponent's best immediate claim+flip reply, normalised by total poin
def _f013(moves, owner, homes, points, adjacency, turn):
    """Immediate claim+flip point gain minus the opponent's best immediate claim+flip reply, normalised by total points."""
    pts = points.astype(float)
    tot = points.sum() + 1.0
    adj = adjacency.astype(float)
    k = moves.shape[0]
    N = owner.shape[0]

    A = adj[moves]                                   # (k,N)
    my_nb = adj @ (owner == 1).astype(float)         # (N,)
    opp_nb = adj @ (owner == -1).astype(float)       # (N,)

    opp_nonhome = (owner == -1).copy()
    opp_nonhome[homes[1]] = False

    flips = (A > 0) & opp_nonhome[None, :] & (my_nb[None, :] + A >= opp_nb[None, :])  # (k,N)
    my_gain = pts[moves] + flips.astype(float) @ pts  # (k,)

    # Post-claim boards
    new_my = np.tile((owner == 1)[None, :], (k, 1))
    new_my[np.arange(k), moves] = True
    new_my |= flips
    new_opp = np.tile((owner == -1)[None, :], (k, 1)) & ~flips

    my_cnt = new_my.astype(float) @ adj               # (k,N)
    opp_cnt = new_opp.astype(float) @ adj             # (k,N)

    # Opponent legal replies: empty cells adjacent to opponent cells, excluding the just-claimed cell
    legal = ((new_opp.astype(float) @ adj) > 0) & (owner == 0)[None, :]
    legal[np.arange(k), moves] = False

    my_nonhome = (owner == 1).copy()
    my_nonhome[homes[0]] = False

    # cond[i,e,d]: opponent claiming e flips my cell d
    cond = (opp_cnt[:, None, :] + adj[None, :, :] >= my_cnt[:, None, :]) & my_nonhome[None, None, :]
    reply = pts[None, :] + np.einsum('ied,d->ie', cond.astype(float), pts)  # (k,N)
    reply = np.where(legal, reply, 0.0)
    best_reply = reply.max(axis=1)                    # (k,)

    return (my_gain - best_reply) / tot

# f047 opponent_mobility_denial (deep): Points of empty cells removed from the opponent's frontier by claiming each candidate, plus 1 if it leaves the
def _f047(moves, owner, homes, points, adjacency, turn):
    """Points of empty cells removed from the opponent's frontier by claiming each candidate, plus 1 if it leaves them with no options, normalised by total points."""
    N = owner.shape[0]; pts = points.astype(float); tot = pts.sum() + 1.0
    adj = adjacency.astype(float)
    mine = (owner == 1); opp = (owner == -1); emp = (owner == 0)
    my_nb = adj @ mine.astype(float); op_nb = adj @ opp.astype(float)
    opp_nonhome = opp.copy(); opp_nonhome[homes[1]] = False
    A = adjacency[moves].astype(float); k = moves.shape[0]
    cand = np.zeros((k, N), bool); cand[np.arange(k), moves] = True
    flipped = (A > 0) & opp_nonhome[None, :] & ((my_nb[None, :] + A) >= op_nb[None, :])
    opp_opts = emp & (op_nb > 0)
    emp2 = emp[None, :] & ~cand
    opp2 = opp[None, :] & ~flipped
    op_nb2 = opp2.astype(float) @ adj
    opts2 = emp2 & (op_nb2 > 0)
    removed = opp_opts[None, :] & ~opts2
    denial = (removed * pts[None, :]).sum(axis=1) / tot
    return denial + (opts2.sum(axis=1) == 0).astype(float)

# f049 endgame_contested_grab (deep): Endgame contested-grab priority: point value of each candidate weighted by opponent contact, gated to the endg
def _f049(moves, owner, homes, points, adjacency, turn):
    """Endgame contested-grab priority: point value of each candidate weighted by opponent contact, gated to the endgame and boosted when the opponent gets the last claim."""
    pts = points.astype(float); adj = adjacency.astype(float)
    mine = (owner == 1).astype(float); opp = (owner == -1).astype(float)
    E = float((owner == 0).sum())
    my_nb = adj @ mine; op_nb = adj @ opp
    gate = 1.0 / (1.0 + np.exp((E - 6.0) / 1.5))
    par = 2.0 if (int(E) % 2 == 0) else 1.0
    c_my = my_nb[moves]; c_op = op_nb[moves]
    contest = c_op / (c_my + c_op + 1.0)
    return gate * (pts[moves] / 5.0) * (1.0 + par * contest) / 3.0

# f053 cut_vertex_opponent_access_block (wide): Cut-vertex pressure: for each candidate, how many empty 5/2-point cells become reachable only through the oppo
def _f053(moves, owner, homes, points, adjacency, turn):
    """Cut-vertex pressure: for each candidate, how many empty 5/2-point cells become reachable only through the opponent's territory (or become unreachable) if I claim it, i.e. its blocking value to the opponent's expansion."""
    N = owner.shape[0]
    pts = points.astype(float)
    tot = pts.sum() + 1.0
    adj = adjacency.astype(float)
    emp = (owner == 0)
    opp = (owner == -1)
    mine = (owner == 1)

    # Distance from opponent cells (through empty cells only) without any change
    def bfs_from(seed_mask):
        dist = np.full(N, np.inf)
        dist[seed_mask] = 0.0
        for _ in range(N):
            cand = np.where(adj > 0, dist[None, :] + 1.0, np.inf).min(axis=1)
            nd = np.minimum(cand, dist)
            if np.array_equal(nd, dist):
                break
            dist = nd
        return dist

    d_op = bfs_from(opp)

    k = moves.shape[0]
    out = np.zeros(k)
    # After I claim candidate c, c is mine: opponent reachability through empty cells changes
    for i in range(k):
        c = moves[i]
        blocked = emp | opp
        blocked[c] = False  # c is now mine, an obstacle
        dist = np.full(N, np.inf)
        dist[opp] = 0.0
        for _ in range(N):
            cand = np.where(adj > 0, dist[None, :] + 1.0, np.inf).min(axis=1)
            nd = np.minimum(cand, dist)
            nd = np.where(blocked | (dist < np.inf), nd, np.inf)
            if np.array_equal(nd, dist):
                break
            dist = nd
        # empty cells the opponent loses access to
        lost = emp & np.isfinite(d_op) & ~np.isfinite(dist)
        out[i] = pts[lost].sum()
    return out / tot

# f098 preempt_opponent_best_claim (deep): Two columns: value of the opponent's pre-claim best option that my claim kills/degrades, and minus their best 
def _f098(moves, owner, homes, points, adjacency, turn):
    """Two columns: value of the opponent's pre-claim best option that my claim kills/degrades, and minus their best remaining option, both normalised by total points."""
    N = owner.shape[0]
    total = float(points.sum())
    if total <= 0:
        total = 1.0
    my_home = homes[0]
    k = moves.shape[0]

    # Precompute per-cell neighbour counts against owner states.
    # adjacency as float for matmul.
    A = adjacency.astype(np.float64)
    pts = points.astype(np.float64)

    def opp_legal_and_values(own):
        """Return (legal_mask, V) for opponent claims given owner array own."""
        opp_cells = (own == -1)
        my_cells = (own == 1)
        empty = (own == 0)
        # opponent-legal: empty cell adjacent to at least one opponent cell
        opp_nb_count = A @ opp_cells.astype(np.float64)  # per cell, # opp neighbours
        legal = empty & (opp_nb_count > 0)
        # V(e) = points[e] + sum over my non-home cells x adjacent to e
        #   where (#opp neighbours of x, counting e as opp) >= (#my neighbours of x)
        # For each empty e, consider my non-home neighbours x of e.
        # For such x: opp_nb_x = opp_nb_count[x] + 1 (e counted as opp)
        #             my_nb_x = my_nb_count[x]
        my_nb_count = A @ my_cells.astype(np.float64)
        # Build V for all cells; only meaningful for legal empty cells.
        V = pts.copy()
        # For each empty cell e, sum over my non-home neighbours x satisfying condition.
        # Vectorise: for each x (my non-home), determine which empty neighbours e qualify.
        # condition: opp_nb_count[x] + 1 >= my_nb_count[x]  (independent of e!)
        # So it's a per-x condition, not per-e. Good.
        my_nonhome = my_cells.copy()
        my_nonhome[my_home] = False
        cond_x = (opp_nb_count + 1.0) >= my_nb_count  # per x
        contrib_x = np.where(my_nonhome & cond_x, pts, 0.0)  # value contributed by x if it qualifies
        # For each empty e, V(e) += sum of contrib_x over my non-home neighbours x of e
        V = V + A @ contrib_x
        return legal, V

    # Pre state
    legal_pre, V_pre = opp_legal_and_values(owner)
    if legal_pre.any():
        idx_pre = np.flatnonzero(legal_pre)
        # argmax with first index on ties
        vals_pre = V_pre[idx_pre]
        best_local = int(np.argmax(vals_pre))
        e_star = int(idx_pre[best_local])
        v_pre_star = float(V_pre[e_star])
    else:
        e_star = -1
        v_pre_star = 0.0

    out = np.zeros((k, 2), dtype=np.float64)

    for i in range(k):
        c = int(moves[i])
        own = owner.copy()
        own[c] = 1
        # flips: opponent cells adjacent to c (except opp home) flip if
        #   my_nb >= opp_nb counting after claim
        opp_home = homes[1]
        # neighbours of c
        nb = np.flatnonzero(adjacency[c])
        # recompute counts after claim
        my_cells = (own == 1)
        opp_cells = (own == -1)
        my_nb_count = A @ my_cells.astype(np.float64)
        opp_nb_count = A @ opp_cells.astype(np.float64)
        for x in nb:
            if own[x] == -1 and x != opp_home:
                if my_nb_count[x] >= opp_nb_count[x]:
                    own[x] = 1
        # recompute after flips
        my_cells = (own == 1)
        opp_cells = (own == -1)
        my_nb_count = A @ my_cells.astype(np.float64)
        opp_nb_count = A @ opp_cells.astype(np.float64)

        legal_post, V_post = opp_legal_and_values(own)

        # col0: value of e* killed/degraded
        if e_star >= 0:
            if own[e_star] == 0 and legal_post[e_star]:
                col0 = (v_pre_star - float(V_post[e_star])) / total
            else:
                col0 = v_pre_star / total
        else:
            col0 = 0.0

        # col1: -post_max
        if legal_post.any():
            post_max = float(V_post[legal_post].max())
            col1 = -post_max / total
        else:
            col1 = 0.0

        out[i, 0] = col0
        out[i, 1] = col1

    return out

_TERMS = [(_f007, np.array([-13.75235])), (_f001, np.array([190.518209])), (_f002, np.array([49.494358])), (_f008, np.array([-19.628435])), (_f015, np.array([82.864509])), (_f013, np.array([58.341642])), (_f047, np.array([30.325218])), (_f049, np.array([33.610985])), (_f053, np.array([7.731264])), (_f098, np.array([241.283325, 103.104386]))]

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
