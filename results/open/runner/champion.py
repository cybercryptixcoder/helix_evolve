# Helix v3 policy: runner, gap 44.769%, progress 55.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 forward_clearance (wide): Forward open-space: reward moving right when the columns just ahead at head/foot height are clear, penalise ne
def _f003(actions, forecast, state, local, hazards, goal_x, tick):
    """Forward open-space: reward moving right when the columns just ahead at head/foot height are clear, penalise near blockers and drops."""
    fx = forecast[:, 0]
    fy = forecast[:, 1]
    fy_safe = np.clip(fy, 0.0, 11.0)

    base_col = float(np.floor(state[0])) - 4.0

    r0 = np.clip(np.floor(fy_safe), 0, 11).astype(int)
    r1 = np.clip(np.floor(fy_safe) + 1, 0, 11).astype(int)

    fc = np.floor(fx)
    offsets = np.array([-2, -1, 0, 1, 2, 3, 4, 5], dtype=float)
    world_cols = fc[:, None] + offsets[None, :]  # (k, 8)
    j_idx = np.clip((world_cols - base_col).astype(int), 0, 23)

    tile_a = local[r0[:, None], j_idx]
    tile_b = local[r1[:, None], j_idx]
    blocked = ((tile_a == 1) | (tile_a == 2) | (tile_b == 1) | (tile_b == 2)).astype(float)

    ahead_mask = offsets[None, :] > 0
    dist = np.where(ahead_mask, offsets[None, :], 1.0)
    ahead_pen = np.sum(np.where(ahead_mask, blocked / dist, 0.0), axis=1)

    forward = np.clip(fx - state[0], -1.0, 1.0)
    open_ahead = 1.0 - np.clip(ahead_pen, 0.0, 1.0)
    drop = np.clip(state[1] - fy, 0.0, 3.0) / 3.0

    val = 0.6 * forward + 0.4 * open_ahead - 0.5 * ahead_pen - 0.4 * drop
    return np.clip(val, -1.0, 1.0)

# f006 hazard_clearance (deep): Negative smooth proximity penalty to nearest spike inset square or saw disc edge (box centre), -1 if the actio
def _f006(actions, forecast, state, local, hazards, goal_x, tick):
    """Negative smooth proximity penalty to nearest spike inset square or saw disc edge (box centre), -1 if the action dies."""
    k = forecast.shape[0]
    px = forecast[:, 0]
    py = forecast[:, 1] + 0.45

    # (a) spikes: inset squares [c+0.2, c+0.8] x [r+0.2, r+0.8]
    base_col = np.floor(state[0]) - 4
    spike_r, spike_j = np.nonzero(local == 2)
    if spike_r.size > 0:
        c = base_col + spike_j.astype(np.float64)
        r = spike_r.astype(np.float64)
        x0 = c + 0.2
        x1 = c + 0.8
        y0 = r + 0.2
        y1 = r + 0.8
        # broadcast: (k, n)
        dx = np.maximum(np.maximum(x0[None, :] - px[:, None], px[:, None] - x1[None, :]), 0.0)
        dy = np.maximum(np.maximum(y0[None, :] - py[:, None], py[:, None] - y1[None, :]), 0.0)
        d_spike = np.sqrt(dx * dx + dy * dy).min(axis=1)
    else:
        d_spike = np.full(k, np.inf)

    # (b) saws
    if hazards.shape[0] > 0:
        hx = hazards[:, 0]
        hy = hazards[:, 1]
        hr = hazards[:, 4]
        dist = np.sqrt((px[:, None] - hx[None, :]) ** 2 + (py[:, None] - hy[None, :]) ** 2) - hr[None, :] - 0.4
        d_saw = np.maximum(dist, 0.0).min(axis=1)
    else:
        d_saw = np.full(k, np.inf)

    # (c)
    d = np.minimum(np.minimum(d_spike, d_saw), 1.0)
    value = -np.exp(-d / 0.3)
    value = np.where(forecast[:, 5] == 0, -1.0, value)
    return value

# f014 dash_safe_landing (deep): Dash-only score: end-of-dash ground support minus 0.6 * mean corridor blockage, -1 if the dash dies.
def _f014(actions, forecast, state, local, hazards, goal_x, tick):
    """Dash-only score: end-of-dash ground support minus 0.6 * mean corridor blockage, -1 if the dash dies."""
    k = actions.shape[0]
    out = np.zeros(k, dtype=float)

    is_dash = (actions == 6) | (actions == 7)
    if not np.any(is_dash):
        return out

    d = np.where(actions == 7, 1.0, -1.0)  # +1 right, -1 left
    fx = forecast[:, 0]
    fy = forecast[:, 1]
    alive = forecast[:, 5]

    base_col = np.floor(state[0]) - 4.0

    # End-of-dash column: remaining 5 ticks cover 4.0 tiles.
    ec = np.floor(fx + 4.0 * d)
    ec_j = np.clip(ec - base_col, 0, 23).astype(int)

    fy_floor = np.floor(fy)
    row_body = np.clip(fy_floor, 0, 11).astype(int)
    row_head = np.clip(fy_floor + 1, 0, 11).astype(int)
    row_below = np.clip(fy_floor - 1, 0, 11).astype(int)

    # Support: solid (1 or 3) tile under the body at the end column, or past the goal.
    under = local[row_below, ec_j]
    solid_under = (under == 1) | (under == 3)
    support = np.where(ec >= goal_x, 1.0, np.where(solid_under, 1.0, 0.0))

    # Corridor blockage over j = 1..5 at body rows.
    blocked_sum = np.zeros(k, dtype=float)
    for j in range(1, 6):
        cj = np.clip(np.floor(fx) + d * j - base_col, 0, 23).astype(int)
        t_body = local[row_body, cj]
        t_head = local[row_head, cj]
        hit = ((t_body == 1) | (t_body == 2) | (t_head == 1) | (t_head == 2))
        blocked_sum += hit.astype(float)
    blocked = blocked_sum / 5.0

    value = support - 0.6 * blocked
    value = np.where(alive == 0, -1.0, value)
    out = np.where(is_dash, value, 0.0)
    return out

# f039 saw_folded_arrival_margin (deep): Min over next 4 ticks and all saws of body-centre-to-disc-centre distance minus 0.90 (folded saw phase), clipp
def _f039(actions, forecast, state, local, hazards, goal_x, tick):
    """Min over next 4 ticks and all saws of body-centre-to-disc-centre distance minus 0.90 (folded saw phase), clipped to [-1, 0.5]; -1 for dying actions."""
    k = forecast.shape[0]
    alive = forecast[:, 5] > 0.5
    out = np.full(k, -1.0, dtype=float)
    if hazards.shape[0] == 0:
        out[alive] = 0.0
        return out

    fx = forecast[:, 0]
    fy = forecast[:, 1]
    vx = forecast[:, 2]
    vy = forecast[:, 3]

    dt = np.arange(1, 5, dtype=float)  # (4,)
    # vertical body-centre offset: y + clip(vy*dt - 0.015*dt*(dt+1)/2, -0.6dt, 0.42dt) + 0.45
    dy_off = vy[:, None] * dt[None, :] - 0.015 * dt[None, :] * (dt[None, :] + 1.0) / 2.0
    dy_off = np.clip(dy_off, -0.6 * dt[None, :], 0.42 * dt[None, :])
    bx = fx[:, None] + vx[:, None] * dt[None, :]          # (k,4)
    by = fy[:, None] + dy_off + 0.45                       # (k,4)

    sx0 = hazards[:, 0]
    sy0 = hazards[:, 1]
    svx = hazards[:, 2]
    svy = hazards[:, 3]
    e1x = hazards[:, 5]
    e1y = hazards[:, 6]
    e2x = hazards[:, 7]
    e2y = hazards[:, 8]

    dx = e2x - e1x
    dy = e2y - e1y
    L = np.maximum(1e-6, np.hypot(dx, dy))
    hx = dx / L
    hy = dy / L
    u0 = np.clip((sx0 - e1x) * hx + (sy0 - e1y) * hy, 0.0, L)
    v = np.hypot(svx, svy)
    sigma = np.where((svx * hx + svy * hy) >= 0.0, 1.0, -1.0)

    # (m,4) folded positions
    w = np.mod(u0[:, None] + sigma[:, None] * v[:, None] * dt[None, :], 2.0 * L[:, None])
    u = L[:, None] - np.abs(w - L[:, None])
    sx = e1x[:, None] + hx[:, None] * u
    sy = e1y[:, None] + hy[:, None] * u

    # distances (k, m, 4)
    ddx = bx[:, None, :] - sx[None, :, :]
    ddy = by[:, None, :] - sy[None, :, :]
    dist = np.hypot(ddx, ddy) - 0.90
    m = dist.min(axis=(1, 2))  # (k,)

    val = np.clip(m / 2.0, -1.0, 0.5)
    out[alive] = val[alive]
    return out

# f058 dash_gap_urgency (deep): Dash-only: 1 - (distance in columns to the first floorless column ahead in the dash direction)/10, 0 for non-d
def _f058(actions, forecast, state, local, hazards, goal_x, tick):
    """Dash-only: 1 - (distance in columns to the first floorless column ahead in the dash direction)/10, 0 for non-dashes."""
    actions = np.asarray(actions)
    k = actions.shape[0]
    out = np.zeros(k, dtype=float)

    is_dash = (actions == 6) | (actions == 7)
    if not np.any(is_dash):
        return out

    x0 = float(state[0])
    y0 = float(state[1])
    r = int(np.clip(np.floor(y0) - 1, 0, 11))
    base_col = int(np.floor(x0)) - 4

    # n = 1..10
    ns = np.arange(1, 11, dtype=float)  # (10,)
    dirs = np.where(actions == 7, 1.0, -1.0)  # (k,)

    # columns for each candidate and n: (k, 10)
    cols = np.floor(x0) + dirs[:, None] * ns[None, :]
    js = np.clip(cols - base_col, 0, 23).astype(int)  # (k, 10)

    row = local[r, :]  # (24,)
    tile = row[js]  # (k, 10)
    is_gap = (tile != 1) & (tile != 3)  # (k, 10)

    # smallest n that is a gap, else 11
    d = np.full(k, 11.0)
    has_gap = np.any(is_gap, axis=1)
    first_idx = np.argmax(is_gap, axis=1)  # 0..9
    d[has_gap] = ns[first_idx[has_gap]]

    val = np.clip(1.0 - d / 10.0, -1.0, 1.0)
    out[is_dash] = val[is_dash]
    return out

# f054 spike_time_to_contact (wide): Foot-level spike threat weighted by time-to-contact: negative predicted spike-box overlap over the next 6 tick
def _f054(actions, forecast, state, local, hazards, goal_x, tick):
    """Foot-level spike threat weighted by time-to-contact: negative predicted spike-box overlap over the next 6 ticks of each candidate's trajectory (worst tick), -1 if the action dies now; zero when no foot-level spike ahead."""
    k = forecast.shape[0]
    fx = forecast[:, 0]
    fy = forecast[:, 1]
    vx = forecast[:, 2]
    vy = forecast[:, 3]
    alive = forecast[:, 5]

    base_col = np.floor(state[0]) - 4.0

    # gather spike inset squares in the view
    spike_r, spike_j = np.nonzero(local == 2)
    if spike_r.size == 0:
        return np.where(alive == 0, -1.0, 0.0)

    c = base_col + spike_j.astype(np.float64)
    r = spike_r.astype(np.float64)
    x0 = c + 0.2
    x1 = c + 0.8
    y0 = r + 0.2
    y1 = r + 0.8

    # only spikes that could matter: within a few tiles ahead of the runner
    ahead_mask = (x1 >= state[0] - 0.8) & (x0 <= state[0] + 6.0)
    if not np.any(ahead_mask):
        return np.where(alive == 0, -1.0, 0.0)
    x0 = x0[ahead_mask]
    x1 = x1[ahead_mask]
    y0 = y0[ahead_mask]
    y1 = y1[ahead_mask]

    dt = np.arange(0, 6, dtype=float)  # include current tick (t=0 uses forecast)

    # rough ballistic vertical propagation (no ground check; bounded)
    dy_off = vy[:, None] * dt[None, :] - 0.015 * dt[None, :] * (dt[None, :] + 1.0)
    dy_off = np.clip(dy_off, -0.6 * dt[None, :], 0.42 * dt[None, :])
    # horizontal propagation with mild decay assumption
    bx = fx[:, None] + vx[:, None] * dt[None, :]
    by = fy[:, None] + dy_off

    # box half extents
    hw = 0.3
    hh = 0.9

    # overlap depth per tick per spike: (k, T, n)
    ox = np.minimum(bx[:, :, None] + hw, x1[None, None, :]) - np.maximum(bx[:, :, None] - hw, x0[None, None, :])
    oy = np.minimum(by[:, :, None] + hh, y1[None, None, :]) - np.maximum(by[:, :, None], y0[None, None, :])
    overlap = np.minimum(ox, oy)  # positive = penetrating in both axes

    worst = overlap.max(axis=(1, 2))  # (k,)
    val = -np.clip(worst, 0.0, 1.0)
    val = np.where(alive == 0, -1.0, val)
    return val

# f066 post_death_hazard_brake (deep): Post-death hazard brake: g*(clip(d/2,0,1)-1) with g=min(deaths,2)/2, d=min body-centre distance to spike inset
def _f066(actions, forecast, state, local, hazards, goal_x, tick):
    """Post-death hazard brake: g*(clip(d/2,0,1)-1) with g=min(deaths,2)/2, d=min body-centre distance to spike inset boxes and saw discs; -g if the action dies."""
    k = actions.shape[0]
    g = min(float(state[6]), 2.0) / 2.0
    if g == 0.0:
        return np.zeros(k)

    fx = forecast[:, 0]
    fy = forecast[:, 1] + 0.45
    alive = forecast[:, 5]

    # Spike inset boxes: tile (r, c) inset by 0.2 -> box [c+0.2, c+0.8] x [r+0.2, r+0.8]
    # Body half-extents: 0.3 wide, 0.45 tall (centre at fy).
    spike_rows, spike_cols = np.nonzero(local == 2)
    d = np.full(k, 2.0)
    if spike_rows.size > 0:
        base_col = int(np.floor(state[0])) - 4
        sc = (spike_cols + base_col).astype(float) + 0.5
        sr = spike_rows.astype(float) + 0.5
        # distance from body centre to inset box (half-extents 0.3, 0.45)
        dx = np.maximum(np.abs(fx[:, None] - sc[None, :]) - 0.6, 0.0)
        dy = np.maximum(np.abs(fy[:, None] - sr[None, :]) - 0.75, 0.0)
        db = np.hypot(dx, dy)
        d = np.minimum(d, db.min(axis=1))

    # Saws at current position
    if hazards.shape[0] > 0:
        sx = hazards[:, 0]
        sy = hazards[:, 1]
        dxs = np.maximum(np.abs(fx[:, None] - sx[None, :]) - 0.3, 0.0)
        dys = np.maximum(np.abs(fy[:, None] - sy[None, :]) - 0.45, 0.0)
        ds = np.hypot(dxs, dys) - 0.45
        d = np.minimum(d, ds.min(axis=1))

    score = g * (np.clip(d / 2.0, 0.0, 1.0) - 1.0)
    score = np.where(alive == 0, -g, score)
    return score

# f069 spike_clearance_margin_sum (wide): Spike threat as a per-tick clearance-margin sum (not overlap): over the next 6 ticks, for each tick the negati
def _f069(actions, forecast, state, local, hazards, goal_x, tick):
    """Spike threat as a per-tick clearance-margin sum (not overlap): over the next 6 ticks, for each tick the negative closest box-edge distance to any spike, weighted by 1/(1+tick), zero if no spike ahead; -1 for dying actions."""
    k = forecast.shape[0]
    fx = forecast[:, 0]
    fy = forecast[:, 1]
    vx = forecast[:, 2]
    vy = forecast[:, 3]
    alive = forecast[:, 5]

    base_col = np.floor(state[0]) - 4.0

    spike_r, spike_j = np.nonzero(local == 2)
    if spike_r.size == 0:
        return np.where(alive == 0, -1.0, 0.0)

    c = base_col + spike_j.astype(np.float64)
    r = spike_r.astype(np.float64)
    x0 = c + 0.2
    x1 = c + 0.8
    y0 = r + 0.2
    y1 = r + 0.8

    ahead_mask = (x1 >= state[0] - 1.0) & (x0 <= state[0] + 7.0)
    if not np.any(ahead_mask):
        return np.where(alive == 0, -1.0, 0.0)
    x0 = x0[ahead_mask]
    x1 = x1[ahead_mask]
    y0 = y0[ahead_mask]
    y1 = y1[ahead_mask]

    dt = np.arange(0, 6, dtype=float)
    dy_off = vy[:, None] * dt[None, :] - 0.015 * dt[None, :] * (dt[None, :] + 1.0)
    dy_off = np.clip(dy_off, -0.6 * dt[None, :], 0.42 * dt[None, :])
    bx = fx[:, None] + vx[:, None] * dt[None, :]   # (k, T)
    by = fy[:, None] + dy_off                       # (k, T)

    hw = 0.3
    hh = 0.9

    # squared distance from body box to each spike inset box, per tick per spike
    dx = np.maximum(np.maximum(x0[None, None, :] - (bx[:, :, None] + hw),
                               (bx[:, :, None] - hw) - x1[None, None, :]), 0.0)
    dy = np.maximum(np.maximum(y0[None, None, :] - (by[:, :, None] + hh),
                               by[:, :, None] - y1[None, None, :]), 0.0)
    dist = np.sqrt(dx * dx + dy * dy)  # (k, T, n), 0 when overlapping

    nearest = dist.min(axis=2)  # (k, T)
    # margin in [-1, 0]: 0 when touching/penetrating, ->0 as far away
    margin = -np.clip(nearest / 1.5, 0.0, 1.0)
    w = 1.0 / (1.0 + dt)  # (T,)
    val = np.sum(margin * w[None, :], axis=1) / np.sum(w)
    val = np.clip(val, -1.0, 0.0)
    val = np.where(alive == 0, -1.0, val)
    return val

_TERMS = [(_f003, np.array([8.643774])), (_f006, np.array([65.731514])), (_f014, np.array([-4.607054])), (_f039, np.array([3.692825])), (_f058, np.array([-7.825664])), (_f054, np.array([6.524687])), (_f066, np.array([-0.427712])), (_f069, np.array([0.25976]))]

def priority(actions, forecast, state, local, hazards, goal_x, tick):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(actions, forecast, state, local, hazards, goal_x, tick), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(actions))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
