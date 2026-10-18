"""Runner (open suite): an invented side-scrolling platform game, run as a speedrun over seeded levels.

A runner (a 0.6 x 0.9 box) crosses a procedurally generated level of solid ground, pits, spikes, boost pads,
checkpoints and moving saws, under simple tick physics (gravity, a fixed-height jump, a dash with a cooldown).
Every tick the policy chooses the action (wait, left, right, jump, jump-left, jump-right, dash-left, dash-right;
only the legal ones). Dying (a pit, a spike, a saw) respawns the runner at its last checkpoint and costs extra
ticks. A level's cost is the ticks it took to reach the goal; a level not finished within the cap costs the cap,
plus a penalty, plus a charge per tile of distance never reached.

Open ceiling (docs/OPEN_SUITE.md): an instance is two levels of one style; cost = the sum of their costs;
gap = 100 * cost / Code Zero's cost (Code Zero = 100 exactly). Code Zero's costs are cached in
suite/data/runner_cz.json (rebuild: `python -m suite.runner --cz`); a missing or stale entry is computed on the spot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
CZ_FILE = ROOT / "suite" / "data" / "runner_cz.json"
SPLIT_SEED = {"train": 9121, "valid": 9232, "test": 9343}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
LEVELS = 2
STYLES = {"meadow": 1, "caves": 2, "towers": 3, "foundry": 4}
TRAIN_FAMILIES = ["meadow", "caves", "towers"]
HELD_OUT = ["foundry"]

# physics (tiles and ticks)
G = 0.03            # gravity per tick
VFALL = 0.6         # terminal fall speed
JUMP_V = 0.42       # upward speed of a jump
VMAX = 0.25         # top running speed
ACC_G, ACC_A = 0.05, 0.03      # acceleration per tick on the ground / in the air
FRIC_G, FRIC_A = 0.6, 0.95     # vx multiplier per tick with no horizontal input, ground / air
DRAG_G, DRAG_A = 0.03, 0.015   # speed lost per tick above VMAX while pressing that way, ground / air
DASH_V, DASH_TICKS, DASH_COOL = 0.8, 6, 45
BOOST_V = 0.6
HW, PH = 0.3, 0.9   # half width, height of the runner
SAW_R = 0.45
DEATH_TICKS = 40
CAP = 1500
STALL = 300         # ticks without a new furthest x (by 0.5 tile) end the run, unfinished
UNFINISHED = 100
PER_TILE = 5.0
HL = 12             # level height (rows)
VIEW_BACK, VIEW_AHEAD = 4, 20
EMPTY, SOLID, SPIKE, BOOST, FLAG, GOAL = 0, 1, 2, 3, 4, 5
ACTIONS = ["wait", "left", "right", "jump", "jump-left", "jump-right", "dash-left", "dash-right"]
DIR = (0, -1, 1, 0, -1, 1, -1, 1)


# ---------------------------------------------------------------------------------------------- levels
class Builder:
    def __init__(self, rng):
        self.rng, self.cols, self.saws, self.flags = rng, [], [], []
        self.h, self.since_flag = 2, 0

    def col(self, h, ceil=None, spike=False, boost=False, plat=None):
        c = np.zeros(HL, dtype=np.int8)
        c[:h] = SOLID
        if boost and h > 0:
            c[h - 1] = BOOST
        if spike and h > 0:
            c[h] = SPIKE
        if plat is not None:
            c[plat - 1] = SOLID
        if ceil is not None:
            c[ceil:] = SOLID
        self.cols.append(c)
        self.since_flag += 1

    def flat(self, n, **kw):
        for _ in range(n):
            self.col(self.h, **kw)

    def flag(self):
        self.flat(1)
        self.cols[-1][self.h] = FLAG
        self.flags.append((len(self.cols) - 0.5, float(self.h)))
        self.flat(2)
        self.since_flag = 0

    def saw(self, ax, ay, bx, by, speed):
        plen = math.hypot(bx - ax, by - ay)
        self.saws.append((ax, ay, bx, by, speed, float(self.rng.uniform(0, 2 * plen)), plen))

    def newh(self, lo=1, hi=6, d=(-1, 0, 1)):
        self.h = int(np.clip(self.h + int(self.rng.choice(d)), lo, hi))


def _chunk(b, style, kind):
    r = b.rng
    x0 = len(b.cols)
    ceil = None
    if style == "caves":
        ceil = b.h + int(r.choice([3, 4, 5]))
        ceil = min(ceil, HL - 1)
    kw = {"ceil": ceil}
    cs = style == "caves" and ceil - b.h == 5 and r.random() < 0.6   # hanging spikes under a high ceiling
    if kind == "flat":
        b.flat(int(r.integers(3, 6)), **kw)
    elif kind == "step":
        b.flat(2, **kw)
        lo, hi = (1, 6) if style != "towers" else (1, 7)
        d = (-2, -1, 1, 2) if style != "caves" else (-1, 1)
        b.newh(lo, hi, d)
        if style == "caves":
            kw["ceil"] = min(HL - 1, max(kw["ceil"], b.h + 3))
        b.flat(int(r.integers(3, 5)), **kw)
    elif kind == "gap":
        b.flat(2, **kw)
        w = int(r.integers(2, 5)) if style != "caves" else int(r.integers(2, 4))
        for _ in range(w):
            b.col(0, ceil=kw["ceil"])
        if style != "caves":
            b.newh(1, 6)
        b.flat(int(r.integers(3, 5)), **kw)
    elif kind == "spikes":
        b.flat(2, **kw)
        for _ in range(int(r.integers(1, 4))):
            b.col(b.h, spike=True, ceil=kw["ceil"])
        b.flat(int(r.integers(3, 5)), **kw)
    elif kind == "boostgap":
        b.flat(1)
        b.flat(2, boost=True)
        for _ in range(int(r.integers(8, 11))):
            b.col(0)
        b.flat(4)
    elif kind == "platforms":
        b.flat(2)
        n = int(r.integers(1, 3))
        for _ in range(n):
            for _ in range(int(r.integers(2, 4))):
                b.col(0)
            p = int(np.clip(b.h + int(r.choice([-1, 0, 1])), 1, 7))
            for _ in range(int(r.integers(2, 4))):
                b.col(0, plat=p)
            b.h = p
        for _ in range(int(r.integers(2, 4))):
            b.col(0)
        b.newh(1, 6)
        b.flat(3)
    elif kind == "saw_v":
        b.flat(3, **kw)
        c = len(b.cols) + 1
        top = b.h + 3.6 if ceil is None else min(b.h + 3.6, ceil - 0.5)
        b.flat(4, **kw)
        b.saw(c + 0.5, b.h + 0.5, c + 0.5, top, float(r.uniform(0.04, 0.08)))
        b.flat(2, **kw)
    elif kind == "saw_h":
        b.flat(2, **kw)
        c = len(b.cols)
        b.flat(7, **kw)
        b.saw(c + 0.5, b.h + 0.5, c + 6.5, b.h + 0.5, float(r.uniform(0.04, 0.08)))
        b.flat(2, **kw)
    if cs:                                   # hang spikes from the ceiling over part of the chunk
        for c in range(x0 + 1, len(b.cols) - 1):
            col = b.cols[c]
            if col[HL - 1] == SOLID and r.random() < 0.5:
                k = HL - 1                   # the lowest tile of the ceiling
                while k > 0 and col[k - 1] == SOLID:
                    k -= 1
                if col[k - 1] == EMPTY:
                    col[k - 1] = SPIKE


KINDS = {
    "meadow": (["flat", "step", "gap", "spikes", "boostgap", "saw_h", "saw_v"], [.12, .2, .25, .2, .11, .06, .06]),
    "caves": (["flat", "step", "gap", "spikes", "saw_h"], [.2, .2, .25, .2, .15]),
    "towers": (["flat", "step", "gap", "platforms", "saw_v", "spikes"], [.1, .25, .15, .25, .15, .1]),
    "foundry": (["flat", "gap", "spikes", "boostgap", "saw_h", "saw_v", "platforms"], [.06, .12, .14, .16, .2, .2, .12]),
}


def make_level(style, rng, length=90):
    b = Builder(rng)
    b.flat(2)
    b.flag()                                  # the start (first checkpoint) at x = 2.5
    b.flat(2)
    kinds, pr = KINDS[style]
    while len(b.cols) < length:
        if b.since_flag >= 24:
            if style == "caves":
                b.flat(1, ceil=min(HL - 1, b.h + 4))
            b.flag()
            continue
        _chunk(b, style, kinds[int(rng.choice(len(kinds), p=pr))])
    b.flat(2)
    goal = len(b.cols)
    b.flat(1)
    b.cols[-1][b.h] = GOAL
    b.flat(VIEW_AHEAD + 4)
    tiles = np.stack(b.cols, axis=1)          # (HL, L), row 0 = bottom
    saws = np.array(b.saws, dtype=float).reshape(-1, 7)
    return {"tiles": tiles, "saws": saws, "flags": b.flags, "goal_x": goal + 0.5}


# ---------------------------------------------------------------------------------------------- physics
class Level:
    """Fast lookups for one level."""

    def __init__(self, lv):
        t = lv["tiles"]
        self.L = t.shape[1]
        self.solid = [[bool(v in (SOLID, BOOST)) for v in row] for row in t]     # [row][col]
        self.spike = [[bool(v == SPIKE) for v in row] for row in t]
        self.boost = [[bool(v == BOOST) for v in row] for row in t]
        pad = np.full((HL, VIEW_BACK), SOLID, dtype=np.int8)
        self.padded = np.concatenate([pad, t], axis=1)
        self.saw_list = [tuple(map(float, row)) for row in lv["saws"]]
        self.flags = lv["flags"]
        self.goal_x = lv["goal_x"]

    def is_solid(self, c, r):
        if c < 0:
            return True
        if r < 0 or r >= HL or c >= self.L:
            return False
        return self.solid[r][c]


def saw_pos(s, t):
    ax, ay, bx, by, speed, phase, plen = s
    u = (phase + speed * t) % (2 * plen)
    if u <= plen:
        f, sg = u / plen, 1.0
    else:
        f, sg = 2.0 - u / plen, -1.0
    return ax + (bx - ax) * f, ay + (by - ay) * f, sg * speed * (bx - ax) / plen, sg * speed * (by - ay) / plen


def step(lv, st, a, near_saws):
    """One tick. st = (x, y, vx, vy, grounded, cooldown, dash_left, dash_dir). Returns (new state, alive)."""
    x, y, vx, vy, gr, cool, dl, dd = st
    dashing = True
    if dl > 0:                                                       # dashing: straight line, no gravity
        vx, vy, dl = DASH_V * dd, 0.0, dl - 1
    elif a >= 6:                                                     # start a dash
        dd = DIR[a]
        vx, vy, dl, cool = DASH_V * dd, 0.0, DASH_TICKS - 1, DASH_COOL
    else:
        dashing = False
        d = DIR[a]
        if d:
            if vx * d < VMAX:
                vx += d * (ACC_G if gr else ACC_A)
                if vx * d > VMAX:
                    vx = d * VMAX
            else:
                vx -= d * (DRAG_G if gr else DRAG_A)
                if vx * d < VMAX:
                    vx = d * VMAX
        else:
            vx *= FRIC_G if gr else FRIC_A
            if -0.005 < vx < 0.005:
                vx = 0.0
        if gr and 3 <= a <= 5:
            vy = JUMP_V
        vy -= G
        if vy < -VFALL:
            vy = -VFALL
    if cool > 0:
        cool -= 1
    # horizontal move
    nx = x + vx
    r0, r1 = math.floor(y + 1e-9), math.floor(y + PH - 1e-9)
    if vx > 0:
        c = math.floor(nx + HW - 1e-9)
        if c > math.floor(x + HW - 1e-9):
            for r in range(r0, r1 + 1):
                if lv.is_solid(c, r):
                    nx, vx = c - HW, 0.0
                    break
    elif vx < 0:
        c = math.floor(nx - HW + 1e-9)
        if c < math.floor(x - HW + 1e-9):
            for r in range(r0, r1 + 1):
                if lv.is_solid(c, r):
                    nx, vx = c + 1 + HW, 0.0
                    break
    if dashing and dl == 0 and vx != 0.0:                            # the dash's last tick: back to top speed
        vx = dd * VMAX
    # vertical move
    ny = y + vy
    c0, c1 = math.floor(nx - HW + 1e-9), math.floor(nx + HW - 1e-9)
    gr = False
    if vy < 0:
        r = math.floor(ny)
        if r < math.floor(y + 1e-9):
            for c in range(c0, c1 + 1):
                if lv.is_solid(c, r):
                    ny, vy, gr = r + 1.0, 0.0, True
                    break
    elif vy > 0:
        r = math.floor(ny + PH - 1e-9)
        if r > math.floor(y + PH - 1e-9):
            for c in range(c0, c1 + 1):
                if lv.is_solid(c, r):
                    ny, vy = r - PH, 0.0
                    break
    elif ny == math.floor(ny):                                       # dashing level: standing on something?
        r = int(ny) - 1
        for c in range(c0, c1 + 1):
            if lv.is_solid(c, r):
                gr = True
                break
    if gr:                                                           # a boost pad under the centre
        cc, rr = math.floor(nx), int(ny) - 1
        if 0 <= rr < HL and 0 <= cc < lv.L and lv.boost[rr][cc] and vx < BOOST_V:
            vx = BOOST_V
    st2 = (nx, ny, vx, vy, gr, cool, dl, dd)
    # death
    if ny + PH < 0:
        return st2, False
    for r in range(max(0, math.floor(ny + 0.2)), min(HL - 1, math.floor(ny + PH - 0.2)) + 1):
        row = lv.spike[r]
        for c in range(max(0, math.floor(nx - HW - 0.8)), min(lv.L - 1, math.floor(nx + HW - 0.2)) + 1):
            if row[c] and nx + HW > c + 0.2 and nx - HW < c + 0.8 and ny + PH > r + 0.2 and ny < r + 0.8:
                return st2, False
    for sx, sy in near_saws:
        ddx = abs(sx - nx) - HW
        ddy = abs(sy - (ny + PH / 2)) - PH / 2
        ddx = ddx if ddx > 0 else 0.0
        ddy = ddy if ddy > 0 else 0.0
        if ddx * ddx + ddy * ddy < SAW_R * SAW_R:
            return st2, False
    return st2, True


def legal(st):
    if st[6] > 0:
        return [0]
    out = [0, 1, 2]
    if st[4]:
        out += [3, 4, 5]
    if st[5] == 0:
        out += [6, 7]
    return out


def run_level(level, seed, priority, stats=None):
    """Run one level under `priority` (None = Code Zero). Returns its cost."""
    lv = level["_lv"]
    flags = lv.flags
    goal_x = lv.goal_x
    keys = np.random.default_rng(seed).random((CAP, 8)).tolist()
    cx, cy = flags[0]
    spawn = (cx, cy, 0.0, 0.0, True, 0, 0, 1)
    st, nflag = spawn, 1
    clock = it = deaths = dashes = decisions = 0
    furthest, mark, mark_t = cx, cx, 0
    finished = False
    saws = lv.saw_list
    while clock < CAP and it < CAP:
        acts = legal(st)
        x = st[0]
        t1 = clock + 1
        near = []
        for s in saws:
            if min(s[0], s[2]) - 2 < x < max(s[0], s[2]) + 2:
                px, py, _, _ = saw_pos(s, t1)
                near.append((px, py))
        if len(acts) == 1:
            res = step(lv, st, acts[0], near)
            a = acts[0]
        else:
            row = keys[it]
            order = sorted(acts, key=row.__getitem__)
            decisions += 1
            if priority is None:
                a = order[0]
                res = step(lv, st, a, near)
            else:
                outs = [step(lv, st, b, near) for b in order]
                fc = np.array([(s2[0], s2[1], s2[2], s2[3], float(s2[4]), float(ok)) for s2, ok in outs])
                c0 = math.floor(x)
                local = lv.padded[:, c0: c0 + VIEW_BACK + VIEW_AHEAD]
                hz = []
                for s in saws:
                    if min(s[0], s[2]) - SAW_R < x + VIEW_AHEAD and max(s[0], s[2]) + SAW_R > x - VIEW_BACK:
                        px, py, vx, vy = saw_pos(s, clock)
                        hz.append((px, py, vx, vy, SAW_R, s[0], s[1], s[2], s[3]))
                hz = np.array(hz, dtype=float).reshape(-1, 9)
                state = np.array([st[0], st[1], st[2], st[3], float(st[4]), float(st[5]), float(deaths),
                                  flags[nflag - 1][0], furthest])
                k = len(order)
                s_ = np.asarray(priority(np.array(order), fc, state, local, hz, goal_x, clock), dtype=float)
                if s_.shape != (k,):
                    raise ValueError(f"priority returned shape {s_.shape} for {k} candidates; expected ({k},)")
                i = int(np.argmax(np.round(s_, 9)))
                a = order[i]
                res = outs[i]
        it += 1
        clock += 1
        if a >= 6 and st[6] == 0:
            dashes += 1
        st, alive = res
        if not alive:
            deaths += 1
            clock += DEATH_TICKS
            cx, cy = flags[nflag - 1]
            st = (cx, cy, 0.0, 0.0, True, 0, 0, 1)
        else:
            x = st[0]
            if x > furthest:
                furthest = x
            while nflag < len(flags) and x >= flags[nflag][0]:
                nflag += 1
            if x >= goal_x:
                finished = True
                break
        if furthest >= mark + 0.5:
            mark, mark_t = furthest, clock
        elif clock - mark_t > STALL:
            break
    start = flags[0][0]
    remaining = max(0.0, goal_x - max(furthest, start))
    cost = float(clock) if finished else CAP + UNFINISHED + PER_TILE * remaining
    if stats is not None:
        stats["finished"] += int(finished)
        stats["deaths"] += deaths
        stats["dashes"] += dashes
        stats["decisions"] += decisions
        stats["progress"] += 100.0 * (min(furthest, goal_x) - start) / (goal_x - start)
        if finished:
            stats["fin_ticks"] += clock
    return cost


# ---------------------------------------------------------------------------------------------- instances
def raw_instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for style in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        for i in range(PER_FAMILY):
            levels = []
            h = hashlib.sha1(json.dumps([G, VFALL, JUMP_V, VMAX, ACC_G, ACC_A, FRIC_G, FRIC_A, DRAG_G, DRAG_A,
                                         DASH_V, DASH_TICKS, DASH_COOL, BOOST_V, HW, PH, SAW_R, DEATH_TICKS, CAP,
                                         STALL, UNFINISHED, PER_TILE]).encode())
            for j in range(LEVELS):
                seed = [SPLIT_SEED[split], STYLES[style], i, j]
                lv = make_level(style, np.random.default_rng(seed))
                lv["seed"] = seed + [7]
                lv["_lv"] = Level(lv)
                h.update(lv["tiles"].tobytes() + lv["saws"].tobytes() + json.dumps(lv["seed"]).encode())
                levels.append(lv)
            out.append({"id": f"{style}-{SPLIT_BASE[split] + i:03d}", "family": style, "split": split,
                        "levels": levels, "fingerprint": h.hexdigest()[:12]})
    return out


def _new_stats():
    return {"finished": 0, "deaths": 0, "dashes": 0, "decisions": 0, "progress": 0.0, "fin_ticks": 0}


# ---------------------------------------------------------------------------------------------- the problem
class Runner(Problem):
    name = "runner"
    title = "Runner: speedrun an invented side-scrolling platform game over seeded levels"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(actions, forecast, state, local, hazards, goal_x, tick)"
    candidates_arg = 0
    description = f"""Speedrun an invented side-scrolling platform game. The policy controls the runner, one tick at a time.

**The level.** A grid of square tiles {HL} rows tall; the goal is 90 to 105 tiles to the right of the start. x grows to the right, y grows upwards, and tile (row r, column c) covers c <= x < c + 1, r <= y < r + 1. Tiles are: empty (0), solid ground or wall ({SOLID}), spike ({SPIKE}: deadly, not solid), boost pad ({BOOST}: solid ground), checkpoint flag ({FLAG}: not solid, a marker) and the goal flag ({GOAL}: not solid, a marker). Columns left of the level are solid; above the top row is open; below row 0 there is nothing (falling there is a fall into a pit). Some levels have ceilings, and spikes can hang from them. **Saws** move back and forth at constant speed along a straight segment between two end points, turning around at each end; each is a disc of radius {SAW_R}.

**The runner** is a box {2 * HW} wide and {PH} tall; its position (x, y) is the middle of its bottom edge, so it covers x - {HW} .. x + {HW} and y .. y + {PH}. It starts at the first checkpoint, standing still.

**Actions** (one per tick): 0 wait, 1 left, 2 right, 3 jump, 4 jump-left, 5 jump-right, 6 dash-left, 7 dash-right. Jumps are legal only while standing on the ground; dashes only when the dash cooldown is 0. During a dash no action can be chosen (the dash continues automatically).

**Physics, every tick, in this order.**
1. *Dash.* Starting a dash sets the horizontal speed to {DASH_V} in its direction and the vertical speed to 0, for {DASH_TICKS} ticks (this one included) with no gravity; the cooldown becomes {DASH_COOL} ticks. At the end of the dash's last tick the horizontal speed becomes {VMAX} in its direction (0 if it ended against a wall).
2. *Horizontal speed* (when not dashing). Pressing left or right (including jump-left / jump-right): if the speed in that direction is below {VMAX}, add {ACC_G} on the ground or {ACC_A} in the air, but never beyond {VMAX}; if it is already at or above {VMAX} (after a boost), it drops by {DRAG_G} on the ground or {DRAG_A} in the air, but not below {VMAX}. Not pressing left or right multiplies the speed by {FRIC_G} on the ground or {FRIC_A} in the air (below 0.005 it becomes 0).
3. *Vertical speed* (when not dashing). A jump (from the ground) sets it to {JUMP_V}. Then gravity subtracts {G}; falling speed never exceeds {VFALL}.
4. The cooldown, if above 0, drops by 1.
5. *Move* horizontally by the speed, stopping flush against a solid tile (horizontal speed becomes 0); then vertically, stopping on top of a solid tile (the runner is then on the ground, vertical speed 0) or under one (vertical speed 0). "On the ground" holds only after a tick that ended by landing or standing on a solid tile.
6. *Boost.* If the runner is on the ground and the tile under its centre is a boost pad, its horizontal speed becomes at least {BOOST_V} (to the right).
7. *Death.* The runner dies if it falls entirely below row 0, if its box overlaps the inner part of a spike tile (the square inset by 0.2 on every side), or if its box overlaps a saw's disc (the saw at its position after the tick). Death costs {DEATH_TICKS} extra ticks; the runner then stands still at its last checkpoint, cooldown 0.

**Checkpoints and the goal.** When the runner's x passes a checkpoint flag's column centre, that flag becomes its respawn point. The level is finished at the first tick that the runner's x reaches the goal flag's column centre.

**One decision** = choosing the action for the next tick. The **candidates** are the legal actions, in a random order (reshuffled every tick); with one legal action (during a dash) it is taken automatically. For each candidate the engine also reports its exact one-tick forecast.

**Cost.** A level costs the number of ticks until it is finished (death ticks included). A run is stopped unfinished at {CAP} ticks, or after {STALL} ticks in which the runner's furthest x never improved by 0.5; an unfinished level costs {CAP} + {UNFINISHED} + {PER_TILE:g} x (tiles between the furthest x the runner reached and the goal). An instance is {LEVELS} seeded levels of one style; its **cost** is the sum of their costs, and the **gap** is 100 x cost / the cost of Code Zero (the policy that always takes the first candidate, i.e. a random legal action) on the same instance: Code Zero is 100, lower is better, there is no known best.

Three training styles: `meadow` (open ground: steps, pits, ground spikes, boost pads, a few saws), `caves` (under ceilings, some with hanging spikes; pits, ground spikes, sliding saws) and `towers` (large height changes, floating platforms over long pits, rising and falling saws). The test split adds a level style that training never shows."""
    signature_doc = f"""- `actions`: shape (k,), int: the legal actions (the candidates), in random order. 0 wait, 1 left, 2 right, 3 jump, 4 jump-left, 5 jump-right, 6 dash-left, 7 dash-right.
- `forecast`: shape (k, 6), float: for each candidate, the state after this tick if it is chosen: [x, y, vx, vy, on_ground (0/1), alive (1, or 0 if this action dies this tick)]. For a dying action, x and y are where it died (before the respawn).
- `state`: shape (9,), float: the runner now: [x, y, vx, vy, on_ground (0/1), dash_cooldown (ticks until a dash is legal), deaths (so far in this level), checkpoint_x (x of the respawn point), furthest_x (the furthest x reached so far)].
- `local`: shape ({HL}, {VIEW_BACK + VIEW_AHEAD}), int8: the tiles around the runner: `local[r, j]` is the tile at row r (0 = bottom) and column floor(x) - {VIEW_BACK} + j (so column floor(x) is j = {VIEW_BACK}). Codes: 0 empty, {SOLID} solid, {SPIKE} spike, {BOOST} boost pad (solid), {FLAG} checkpoint flag, {GOAL} goal flag; columns left of the level read as solid.
- `hazards`: shape (m, 9), float: the saws whose path reaches into the view (columns floor(x) - {VIEW_BACK} .. floor(x) + {VIEW_AHEAD - 1}), now: [x, y, vx, vy (per tick), radius, end1_x, end1_y, end2_x, end2_y]. m may be 0.
- `goal_x`: float: the x at which the level is finished.
- `tick`: int: ticks used so far in this level (death ticks included); the run stops at {CAP}.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is played."""
    metric_notes = {
        "cost": "sum over the instance's levels of ticks to the goal (unfinished: cap + penalty + distance charge)",
        "finished": f"levels finished (of {LEVELS})",
        "ticks_per_finish": "mean ticks of the finished levels (0 if none)",
        "deaths_per_level": "deaths per level (each adds the death ticks and a walk back from the checkpoint)",
        "progress_pct": "mean % of the level's distance covered (furthest x), finished levels count 100",
        "dashes_per_level": "dashes started per level",
    }
    example_features = [
        "import numpy as np\n\ndef feature(actions, forecast, state, local, hazards, goal_x, tick):\n"
        "    \"\"\"The x after the tick.\"\"\"\n"
        "    return forecast[:, 0]\n",
        "import numpy as np\n\ndef feature(actions, forecast, state, local, hazards, goal_x, tick):\n"
        "    \"\"\"Two columns: alive after the tick, and is it a jump.\"\"\"\n"
        "    return np.stack([forecast[:, 5], ((actions >= 3) & (actions <= 5)).astype(float)], axis=1)\n",
        "import numpy as np\n\ndef feature(actions, forecast, state, local, hazards, goal_x, tick):\n"
        "    \"\"\"Solid tiles in the view, the same for every candidate.\"\"\"\n"
        "    return np.full(len(actions), float((local == 1).sum()))\n",
    ]

    def __init__(self):
        self._cache = {}
        self._cz = None

    def instances(self, split):
        if split not in self._cache:
            self._cache[split] = raw_instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    @staticmethod
    def _cost(inst, priority, stats=None):
        return sum(run_level(lv, lv["seed"], priority, stats) for lv in inst["levels"])

    def cz_cost(self, inst):
        if self._cz is None:
            try:
                self._cz = json.loads(CZ_FILE.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                self._cz = {}
        key = f"{inst['split']}/{inst['id']}"
        r = self._cz.get(key)
        if r is None or r.get("fingerprint") != inst["fingerprint"]:
            r = {"fingerprint": inst["fingerprint"], "cost": self._cost(inst, None)}
            self._cz[key] = r
        return r["cost"]

    def run(self, instance, priority):
        c = self._cost(instance, priority)
        return {"gap": 100.0 * (c / self.cz_cost(instance)), "cost": c}

    def diagnose(self, instance, priority):
        st = _new_stats()
        c = self._cost(instance, priority, st)
        n = len(instance["levels"])
        return {
            "gap": round(100.0 * (c / self.cz_cost(instance)), 3),
            "cost": round(c, 1),
            "finished": st["finished"],
            "ticks_per_finish": round(st["fin_ticks"] / st["finished"], 1) if st["finished"] else 0.0,
            "deaths_per_level": round(st["deaths"] / n, 2),
            "progress_pct": round(st["progress"] / n, 1),
            "dashes_per_level": round(st["dashes"] / n, 2),
        }


# ---------------------------------------------------------------------------------------------- cache
def build_cz():
    p = Runner()
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in p.instances(split):
            st = _new_stats()
            c = Runner._cost(inst, None, st)
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "cost": c}
            print(f"  {split:5s} {inst['id']:12s} Code Zero cost {c:7.1f}  ({st['decisions']} decisions, "
                  f"progress {st['progress'] / LEVELS:.0f}%)")
    CZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CZ_FILE.write_text(json.dumps({"method": "Code Zero (first candidate of the shuffled list): summed level costs",
                                   "instances": out}, indent=0))
    print(f"wrote {CZ_FILE} ({len(out)} instances, {time.time() - t0:.1f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cz", action="store_true", help="rebuild suite/data/runner_cz.json")
    a = ap.parse_args(argv)
    if a.cz:
        build_cz()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
