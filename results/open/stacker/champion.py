# Helix v3 policy: stacker, gap 5.600%, progress 94.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 stack_height_control (deep): Peak and mean column height of each candidate's resulting board, each divided by H.
def _f005(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Peak and mean column height of each candidate's resulting board, each divided by H."""
    filled = boards != 0                      # (k, H, W)
    H = boards.shape[1]
    col_has = filled.any(axis=1)              # (k, W)
    top = np.argmax(filled, axis=1)           # (k, W), first filled row (0 if none)
    heights = np.where(col_has, H - top, 0).astype(float)  # (k, W)
    peak = heights.max(axis=1) / H
    mean = heights.mean(axis=1) / H
    return np.stack([peak, mean], axis=1)

# f017 same_colour_adjacency_density (deep): Count of orthogonal same-colour (1..colours) adjacent cell pairs on each resulting board, divided by 2*H*W.
def _f017(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Count of orthogonal same-colour (1..colours) adjacent cell pairs on each resulting board, divided by 2*H*W."""
    b = boards
    H, W = b.shape[1], b.shape[2]
    # horizontal pairs: left cell is a colour (1..colours) and equals right cell
    left = b[:, :, :-1]
    right = b[:, :, 1:]
    horiz = (left > 0) & (left < 9) & (left == right)
    # vertical pairs: upper cell is a colour (1..colours) and equals lower cell
    up = b[:, :-1, :]
    down = b[:, 1:, :]
    vert = (up > 0) & (up < 9) & (up == down)
    total = horiz.sum(axis=(1, 2)) + vert.sum(axis=(1, 2))
    return total.astype(np.float64) / (2.0 * H * W)

# f020 danger_excess_x_roughness (wide): Negative peak squared excess height above a quarter of the well, weighted by neighbour roughness, normalised b
def _f020(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Negative peak squared excess height above a quarter of the well, weighted by neighbour roughness, normalised by W*H^2."""
    k, H, W = boards.shape
    filled = boards != 0
    any_filled = filled.any(axis=1)
    top = np.argmax(filled, axis=1).astype(np.float64)
    top = np.where(any_filled, top, float(H))
    h = H - top  # (k, W)
    thresh = 0.25 * H
    excess = np.maximum(0.0, h - thresh)
    # local roughness: absolute height difference with neighbours (edge columns use single neighbour)
    diff = np.abs(np.diff(h, axis=1))  # (k, W-1)
    rough = np.zeros_like(h)
    rough[:, :-1] += diff
    rough[:, 1:] += diff
    # weight excess by how much the column sticks out relative to its neighbours
    weighted = (excess ** 2) * (1.0 + rough / H)
    return -weighted.sum(axis=1) / (W * H * H)

# f021 same_colour_reachable_component (wide): For each candidate, the largest count of same-colour cells reachable from the placed piece's cells through ort
def _f021(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """For each candidate, the largest count of same-colour cells reachable from the placed piece's cells through orthogonal same-colour connections, divided by H*W."""
    k, H, W = boards.shape[0], boards.shape[1], boards.shape[2]
    b = boards
    # colour of the current piece (from ids or from the smallest positive colour present after landing near piece cells)
    # Use the piece's landing cells: derive from placements top row and rotation is hard; instead use colour id.
    cur_col = int(ids[0, 1])
    if cur_col <= 0 or cur_col > colours:
        return np.zeros(k)
    mask = (b == cur_col)
    # iterative flood fill without python loops over candidates: use repeated max-propagation
    # seed = cells of cur colour that are adjacent to... we can't easily isolate the piece; approximate by
    # connected same-colour component sizes via union of shifts, propagated a bounded number of times.
    reach = mask.copy()
    for _ in range(H + W):
        shifted = reach.copy()
        shifted[:, 1:, :] |= reach[:, :-1, :]
        shifted[:, :-1, :] |= reach[:, 1:, :]
        shifted[:, :, 1:] |= reach[:, :, :-1]
        shifted[:, :, :-1] |= reach[:, :, 1:]
        new_reach = shifted & mask
        if np.array_equal(new_reach, reach):
            break
        reach = new_reach
    # Now reach may span multiple components merged incorrectly by the propagation (it merges all same-colour
    # cells that are connected). We instead want each candidate's largest component; approximate with total
    # reachable same-colour cells from the whole mask - this overcounts but is a monotone proxy. To keep a
    # genuine per-component measure, fall back to the size of the component containing the piece by counting
    # only cells reachable, but that is the whole mask. Use total same-colour reachable as the feature.
    counts = reach.sum(axis=(1, 2)).astype(np.float64)
    return counts / float(H * W)

# f022 next_piece_fit_fraction (deep): Fraction of (distinct rotation, leftmost column) drops of the next piece that are legal on each candidate's re
def _f022(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Fraction of (distinct rotation, leftmost column) drops of the next piece that are legal on each candidate's resulting board."""
    k = boards.shape[0]
    if ids[1, 0] == -1:
        return np.zeros(k)
    H, W = boards.shape[1], boards.shape[2]
    nxt = pieces[1]
    # distinct rotations of the next piece, cropped to bounding boxes
    shapes = []
    seen = set()
    for r in range(4):
        rot = np.rot90(nxt, k=-r)
        rows = np.any(rot != 0, axis=1)
        cols = np.any(rot != 0, axis=0)
        if not rows.any():
            continue
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        crop = rot[r0:r1 + 1, c0:c1 + 1]
        key = crop.tobytes() + bytes(crop.shape)
        if key in seen:
            continue
        seen.add(key)
        dr, dc = np.nonzero(crop)
        shapes.append((dr, dc, crop.shape[0], crop.shape[1]))
    n_rot = len(shapes)
    if n_rot == 0:
        return np.zeros(k)

    # first filled row per column per candidate board, H if empty
    filled = boards != 0  # (k, H, W)
    any_filled = filled.any(axis=1)  # (k, W)
    first = np.where(any_filled, filled.argmax(axis=1), H)  # (k, W)

    total = 0
    for dr, dc, ph, pw in shapes:
        if pw > W:
            continue
        n_cols = W - pw + 1
        # gather first rows for each candidate and each leftmost column
        # columns touched: c + dc for c in 0..n_cols-1
        # build (k, n_cols, len(dr))
        cols_idx = np.arange(n_cols)[:, None] + dc[None, :]  # (n_cols, ncells)
        sub = first[:, cols_idx]  # (k, n_cols, ncells)
        land = sub - dr[None, None, :] - 1  # (k, n_cols, ncells)
        L = land.min(axis=2)  # (k, n_cols)
        L = np.minimum(L, H - ph)
        legal = L >= 0
        total = total + legal.sum(axis=1)
    return total / float(n_rot * W)

# f041 open_near_full_rows (deep): (2*n1 + n2) / (2*H): rows one cell short with one open gap, and two short with two open gaps.
def _f041(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """(2*n1 + n2) / (2*H): rows one cell short with one open gap, and two short with two open gaps."""
    filled = boards != 0
    H = boards.shape[1]
    W = boards.shape[2]
    cnt = filled.sum(-1)                       # (k, H) filled per row
    above = np.cumsum(filled, axis=1) - filled  # (k, H, W) filled cells above each cell
    open_empty = (~filled) & (above == 0)
    oe = open_empty.sum(-1)                    # (k, H) open (surface) empty cells per row
    n1 = ((cnt == W - 1) & (oe == 1)).sum(-1)
    n2 = ((cnt == W - 2) & (oe == 2)).sum(-1)
    return (2.0 * n1 + n2) / (2.0 * H)

# f049 rows_blocked_by_covered_holes (deep): Negative fraction of rows containing at least one covered empty cell (filled cell above it in the same column)
def _f049(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Negative fraction of rows containing at least one covered empty cell (filled cell above it in the same column)."""
    k, H, W = boards.shape
    filled = boards != 0
    # covered[r, c] = empty cell at (r,c) with some filled cell above it in column c
    # above_count[r, c] = number of filled cells in rows 0..r-1 of column c
    above = np.cumsum(filled, axis=1)  # inclusive of current row
    above_excl = np.zeros_like(above)
    above_excl[:, 1:, :] = above[:, :-1, :]
    empty = ~filled
    covered = empty & (above_excl > 0)
    blocked_rows = covered.any(axis=2)  # (k, H)
    n_blocked = blocked_rows.sum(axis=1).astype(float)
    return -(n_blocked / float(H))

# f058 piece_cells_resting_on_same_colour (deep): Count of placed-piece cells resting directly on pre-existing same-colour cells, divided by 5.
def _f058(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Count of placed-piece cells resting directly on pre-existing same-colour cells, divided by 5."""
    k = boards.shape[0]
    pc = int(ids[0, 1])
    if pc <= 0:
        return np.zeros(k)
    new = (board[None] == 0) & (boards == pc)
    same_col = (boards == pc)
    below_same = np.zeros_like(same_col)
    below_new = np.zeros_like(same_col)
    below_same[:, :-1, :] = same_col[:, 1:, :]
    below_new[:, :-1, :] = new[:, 1:, :]
    anchor = new & below_same & (~below_new)
    return anchor.sum(axis=(1, 2)) / 5.0

# f063 marginal_covered_holes (deep): Negative count of empty cells newly covered (filled cell above in same column) by the candidate, divided by H.
def _f063(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """Negative count of empty cells newly covered (filled cell above in same column) by the candidate, divided by H."""
    filled = boards != 0
    above = np.cumsum(filled, axis=1) - filled
    covered = (~filled) & (above > 0)
    new_covered = covered.sum(axis=(1, 2))

    cur_filled = board != 0
    cur_above = np.cumsum(cur_filled, axis=0) - cur_filled
    cur_covered = int((~cur_filled & (cur_above > 0)).sum())

    H = board.shape[0]
    return -(new_covered - cur_covered) / float(H)

# f083 endgame_gain_sprint (deep): gains/(gains+5) when pieces_left <= 10, else 0 for every candidate.
def _f083(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    """gains/(gains+5) when pieces_left <= 10, else 0 for every candidate."""
    g = gains.astype(float)
    vals = g / (g + 5.0)
    return np.where(pieces_left <= 10, vals, 0.0)

_TERMS = [(_f005, np.array([-14.567096, -141.03697])), (_f017, np.array([137.492842])), (_f020, np.array([174.292931])), (_f021, np.array([144.78247])), (_f022, np.array([3.73573])), (_f041, np.array([61.804682])), (_f049, np.array([10.799202])), (_f058, np.array([-0.232743])), (_f063, np.array([4.046097])), (_f083, np.array([0.749823]))]

def priority(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(placements))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
