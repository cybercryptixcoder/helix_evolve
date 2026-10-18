"""Forage (open suite): a drone collects items that keep appearing and lose value, on a limited battery.

Items appear over time (seeded) on the unit square, each with a value that falls linearly at its own rate until
it reaches 0 and the item disappears. A drone flies at speed 1; its battery drains with the distance flown and
recharges only at the charger. At each decision the policy picks the drone's next target among the items that
are visible now, plus the charger (candidates shuffled per decision with the instance's seed, so the first
candidate carries no heuristic and Code Zero is a random policy). Cost = value lost (every spawned item's full
value minus the values actually collected) + a fixed penalty each time the battery runs out.

Open ceiling (docs/OPEN_SUITE.md): no reference, no floor, no textbook rule. gap = 100 * cost / Code Zero's cost
on the same instance (computed once per process and cached by instance id), so Code Zero scores exactly 100.
"""
from __future__ import annotations

import numpy as np

from helix3.problem import Problem

SPLIT_SEED = {"train": 7101, "valid": 7202, "test": 7303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
TRAIN_FAMILIES = ["scatter", "hotspots", "waves"]
HELD_OUT = ["drift"]
CODES = {"scatter": 1, "hotspots": 2, "waves": 3, "drift": 4}
HORIZON = 100.0
RESCUE_TIME = 2.0
PENALTY = 40.0
# items appearing per time unit (waves: background rate, plus a wave of `wave_size` items on average)
RATE = {"scatter": 4.5, "hotspots": 5.0, "waves": 1.0, "wave_size": 24, "drift": 5.0}
_CZ = {}                       # instance id -> Code Zero's cost (in-process cache)


# ---------------------------------------------------------------------------------------------- instances
def make_items(family, rng):
    """(spawn times (n,) sorted, xy (n, 2), initial values (n,), decay rates (n,), charger (2,), drain, charge)."""
    T = HORIZON
    if family == "scatter":
        n = int(rng.poisson(RATE["scatter"] * T))
        t0 = rng.uniform(0, T, n)
        xy = rng.uniform(0, 1, (n, 2))
        v = rng.uniform(2, 10, n)
        life = rng.uniform(1.5, 5.0, n)
        charger, drain, charge = np.array([0.5, 0.5]), 0.12, 0.8
    elif family == "hotspots":
        n = int(rng.poisson(RATE["hotspots"] * T))
        t0 = rng.uniform(0, T, n)
        h = int(rng.integers(3, 5))
        centres = rng.uniform(0.1, 0.9, (h, 2))
        vscale = rng.choice([3.0, 6.0, 12.0], size=h)
        lscale = rng.uniform(1.5, 6.0, h)
        which = rng.integers(0, h, n)
        bg = rng.random(n) < 0.25
        xy = np.where(bg[:, None], rng.uniform(0, 1, (n, 2)), centres[which] + rng.normal(0, 0.06, (n, 2)))
        v = np.where(bg, rng.uniform(1, 6, n), vscale[which] * rng.uniform(0.6, 1.4, n))
        life = np.where(bg, rng.uniform(1.5, 5.0, n), lscale[which] * rng.uniform(0.7, 1.3, n))
        charger = rng.choice([0.05, 0.95], size=2)
        drain, charge = 0.10, 0.6
    elif family == "waves":
        starts, s = [], float(rng.uniform(0, 4))
        while s < T:
            starts.append(s)
            s += float(rng.uniform(6, 10))
        parts = [rng.uniform(0, T, int(rng.poisson(RATE["waves"] * T)))]
        for s in starts:
            parts.append(s + rng.uniform(0, 1.5, int(rng.poisson(RATE["wave_size"]))))
        t0 = np.concatenate(parts)
        t0 = t0[t0 < T]
        n = len(t0)
        xy = rng.uniform(0, 1, (n, 2))
        rare = rng.random(n) < 0.25
        v = np.where(rare, rng.uniform(12, 25, n), rng.uniform(1, 5, n))
        life = np.where(rare, rng.uniform(0.8, 2.0, n), rng.uniform(4, 10, n))
        charger, drain, charge = np.array([0.5, 0.5]), 0.16, 0.5
    elif family == "drift":
        n = int(rng.poisson(RATE["drift"] * T))
        t0 = rng.uniform(0, T, n)
        period = float(rng.uniform(20, 40))
        phase = float(rng.uniform(0, 2 * np.pi))
        ang = 2 * np.pi * t0 / period + phase
        centre = np.stack([0.5 + 0.3 * np.cos(ang), 0.5 + 0.3 * np.sin(ang)], axis=1)
        bg = rng.random(n) < 0.35
        xy = np.where(bg[:, None], rng.uniform(0, 1, (n, 2)), centre + rng.normal(0, 0.08, (n, 2)))
        v = rng.uniform(2, 12, n)
        life = np.clip(rng.lognormal(1.0, 0.5, n), 0.8, 10.0)
        charger, drain, charge = np.array([0.5, 0.02]), 0.14, 0.6
    else:
        raise KeyError(family)
    order = np.argsort(t0, kind="stable")
    t0, xy, v, life = t0[order], np.clip(xy[order], 0, 1), v[order], life[order]
    return (np.round(t0, 4), np.round(xy, 4), np.round(v, 3), np.round(v / life, 4),
            np.asarray(charger, float), float(drain), float(charge))


def _instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for fam in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], CODES[fam], i])
            t0, xy, v, rate, charger, drain, charge = make_items(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "seed": [SPLIT_SEED[split], CODES[fam], i, 99], "horizon": HORIZON,
                        "t0": t0, "xy": xy, "value": v, "rate": rate, "expire": t0 + v / rate,
                        "hist": np.column_stack([xy, t0, v, rate]), "charger": charger,
                        "drain": drain, "charge_rate": charge})
    return out


# ---------------------------------------------------------------------------------------------- simulate
def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


def simulate(inst, priority=None):
    """Fly the drone under `priority` (None = Code Zero: always the first shuffled candidate). Returns stats."""
    T, ch, drain, cr = inst["horizon"], inst["charger"], inst["drain"], inst["charge_rate"]
    t0, xy, V, r, expire, hist = inst["t0"], inst["xy"], inst["value"], inst["rate"], inst["expire"], inst["hist"]
    n = len(t0)
    rng = np.random.default_rng(inst["seed"])
    alive = np.ones(n, dtype=bool)
    t, pos, at_ch, bat = 0.0, ch, True, 1.0
    got = decay = charger_time = 0.0
    runouts = pickups = empty = decisions = 0
    while t < T:
        ns = int(np.searchsorted(t0, t, side="right"))
        vis = np.flatnonzero(alive[:ns] & (expire[:ns] > t))
        m = len(vis)
        target = -1                                                  # -1 = the charger
        if m:
            perm = rng.permutation(m + 1)                            # neutral order; index m is the charger
            if priority is None:
                o = int(perm[0])
            else:
                vals = np.append(V[vis] - r[vis] * (t - t0[vis]), 0.0)[perm]
                rates = np.append(r[vis], 0.0)[perm]
                cxy = np.vstack([xy[vis], ch])[perm]
                args = (np.array(pos, dtype=float), cxy, vals, rates, float(bat), drain, cr, ch.copy(),
                        float(t), float(T - t), hist[:ns])
                o = int(perm[_choose(priority, args, m + 1)])
            decisions += 1
            if o < m:
                target = int(vis[o])
        if target < 0 and at_ch:                                     # wait at the charger for the next item
            nt = float(t0[ns]) if ns < n else T
            charger_time += min(nt, T) - t
            t = nt
            continue
        dest = ch if target < 0 else xy[target]
        d = float(np.sqrt((dest[0] - pos[0]) ** 2 + (dest[1] - pos[1]) ** 2))
        if d * drain > bat + 1e-12:                                  # the battery runs out on the way
            t += bat / drain + RESCUE_TIME
            runouts += 1
            ct = 1.0 / cr
            charger_time += max(0.0, min(T, t + ct) - min(T, t))
            t += ct
            pos, at_ch, bat = ch, True, 1.0
            continue
        t += d
        bat -= d * drain
        pos, at_ch = dest, target < 0
        if target < 0:                                               # charge to full
            ct = (1.0 - bat) / cr
            charger_time += max(0.0, min(T, t + ct) - min(T, t))
            t += ct
            bat = 1.0
        elif t <= T:
            if alive[target] and expire[target] > t:
                val = float(V[target] - r[target] * (t - t0[target]))
                got += val
                decay += float(V[target]) - val
                pickups += 1
                alive[target] = False
            else:
                empty += 1
    total = float(V.sum())
    return {"cost": total - got + PENALTY * runouts, "total": total, "got": got, "decay": decay,
            "runouts": runouts, "pickups": pickups, "empty": empty, "charger_time": charger_time,
            "decisions": decisions, "n": n}


def cz_cost(inst):
    c = _CZ.get(inst["id"])
    if c is None:
        c = _CZ[inst["id"]] = simulate(inst)["cost"]
        if not c > 0:
            raise RuntimeError(f"forage: Code Zero has cost {c} on {inst['id']}")
    return c


# ---------------------------------------------------------------------------------------------- the problem
class Forage(Problem):
    name = "forage"
    title = "Forage: a drone collecting decaying items on a battery"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history)"
    candidates_arg = 1
    description = f"""A drone works on a square area (coordinates in [0, 1]) for {HORIZON:.0f} time units. Items appear over time at random places. Each item has a value when it appears, and its value falls linearly at the item's own rate (value units per time unit); when the value reaches 0 the item disappears. The drone flies in straight lines at speed 1 (one distance unit per time unit) and collects an item by flying to it: it gains the item's value at the moment it arrives, and the item is gone. Only the target is collected (flying over other items does not collect them).

The battery holds 1.0 (full). Flying drains `drain` per unit of distance; nothing else drains it. The battery recharges only at the charger: when the drone arrives at the charger it charges to full at `charge_rate` per time unit (taking (1 - battery) / charge_rate time units, during which time passes as usual). The drone starts at the charger with a full battery. If the battery would run out during a flight, the drone stops where it ran out, is carried back to the charger (taking {RESCUE_TIME:.0f} time units), charged to full there (taking 1 / charge_rate), and a penalty of {PENALTY:.0f} is added to the cost; the item it was flying to is not collected.

One **decision** = choosing the drone's next target whenever it has arrived somewhere (or finished charging, or finished waiting). The **candidates** are every item visible now (appeared and not yet collected or disappeared), plus the charger. Choosing the charger flies there and charges to full; if the drone is already at the charger (it is then always full), choosing the charger means waiting there until the next item appears. Candidates come in a random order (reshuffled at every decision), so the position carries no information. When no item is visible the drone goes to the charger, or waits there for the next item, automatically. Nothing is known about items that have not appeared yet. A flight that arrives after the end collects nothing.

**Cost** of an instance (lower is better) = the value lost = the sum of every item's value at the moment it appeared, minus the values actually collected (so value that decayed before pickup, and items that disappeared or were left at the end, all count), plus {PENALTY:.0f} for every time the battery ran out. Families differ in where and when items appear, how values and decay rates are distributed, and the battery (drain, charge rate, charger position). Three training families: `scatter`, `hotspots`, `waves`; the test split adds a family that training never shows.

There is no known best solution: the score of an instance is **gap = 100 x cost / cost of Code Zero** on that instance, where Code Zero is the policy that always takes the first candidate (a random choice, because the order is shuffled). Code Zero scores 100; lower is better and nothing tells where the best possible lies (0 would mean losing no value at all)."""
    signature_doc = """- `pos`: shape (2,), float: [x, y] of the drone now.
- `targets`: shape (k, 2), float: [x, y] of every candidate, in the (random) candidate order. The charger is one of the rows (at a random position); it is the row whose `values` is 0.
- `values`: shape (k,), float: the current value of each candidate item (always > 0 for an item); **0 for the charger**, so `values == 0` marks it.
- `rates`: shape (k,), float: how fast each item's value falls (value units per time unit; the item disappears after values / rates more time units); 0 for the charger.
- `battery`: float in [0, 1]: the battery left (1 = full).
- `drain`: float: battery used per unit of distance flown (a flight of length d needs d * drain).
- `charge_rate`: float: battery regained per time unit while charging at the charger.
- `charger`: shape (2,), float: [x, y] of the charger.
- `time`: float: the current time (from 0).
- `time_left`: float: time until the end.
- `history`: shape (s, 5), float: every item that has appeared so far (including those already collected or gone), in order of appearance: [x, y, time it appeared, value when it appeared, decay rate]. Nothing about items yet to appear.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is the next target."""
    metric_notes = {
        "cost": "value lost plus battery penalties (what the gap measures)",
        "pickups": "items collected",
        "decay_pct": "value that collected items had lost before pickup, % of all value that appeared",
        "missed_pct": "full value of items never collected (disappeared or left at the end), % of all value that appeared",
        "runouts": "times the battery ran out (each adds the penalty)",
        "charger_time_pct": "% of the time spent charging or waiting at the charger",
    }
    example_features = [
        "import numpy as np\n\ndef feature(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):\n"
        "    \"\"\"Minus the distance to the candidate.\"\"\"\n"
        "    return -np.sqrt(((targets - pos) ** 2).sum(axis=1))\n",
        "import numpy as np\n\ndef feature(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):\n"
        "    \"\"\"Two columns: the candidate's value, and is it the charger.\"\"\"\n"
        "    return np.stack([values, (values == 0).astype(float)], axis=1)\n",
    ]

    def __init__(self):
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            self._cache[split] = _instances(split)
        return self._cache[split]

    def run(self, instance, priority):
        base = cz_cost(instance)
        s = simulate(instance, priority)
        return {"gap": 100.0 * (s["cost"] / base), "cost": s["cost"], "runouts": s["runouts"], "pickups": s["pickups"]}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        base = cz_cost(instance)
        s = simulate(instance, priority)
        tot = s["total"]
        return {
            "gap": round(100.0 * (s["cost"] / base), 3),
            "cost": round(s["cost"], 2),
            "pickups": s["pickups"],
            "decay_pct": round(100 * s["decay"] / tot, 2),
            "missed_pct": round(100 * (tot - s["got"] - s["decay"]) / tot, 2),
            "runouts": s["runouts"],
            "charger_time_pct": round(100 * s["charger_time"] / instance["horizon"], 2),
        }
