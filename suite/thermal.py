"""Thermal (open suite): place arriving jobs in a data hall whose racks heat up and slow down.

Jobs arrive (seeded) with a size (slots) and an ideal duration. Servers of 16 slots sit in racks; a rack's
temperature rises with its load, falls slowly towards the supply air, and exchanges heat with adjacent racks; a hot
rack slows every job in it (an invented nonlinear slowdown). Each decision places one job on a server with room
(candidates shuffled per decision with the instance's seed, so Code Zero is a random policy); a job that fits
nowhere waits in a queue and is placed (another decision) as soon as it fits. Cost = total completion time above
each job's ideal duration (heat slowdown + waiting), summed over jobs, in minutes.

Open ceiling (docs/OPEN_SUITE.md): no reference, no floor, no textbook rule. gap = 100 * cost / Code Zero's cost
on the same instance (computed once per process and cached by instance id), so Code Zero scores exactly 100.
"""
from __future__ import annotations

import numpy as np

from helix3.problem import Problem

SPLIT_SEED = {"train": 8101, "valid": 8202, "test": 8303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
TRAIN_FAMILIES = ["row", "pods", "bursts"]
HELD_OUT = ["mixed"]
CODES = {"row": 1, "pods": 2, "bursts": 3, "mixed": 4}
SLOTS = 16                    # slots per server
T_SUPPLY = 20.0               # supply air temperature, deg C
GAIN = 1.0                    # deg C per minute added by a fully loaded rack
WINDOW = 300                  # jobs arrive during minutes [0, WINDOW)
HOT, SCALE, THROTTLE = 30.0, 10.0, 42.0      # slowdown(T) = 1 + (max(T - HOT, 0) / SCALE)^2 + max(T - THROTTLE, 0) / 4
# arrival intensity per family (jobs per minute; for bursts, the mean batch size)
LOAD = {"row": 1.7, "pods": 1.6, "bursts": 20, "mixed": 2.5}
_CZ = {}                      # instance id -> Code Zero's cost (in-process cache)


def slowdown(temp):
    """The heat slowdown factor of a rack at temperature `temp` (1 = full speed)."""
    return 1.0 + (np.maximum(temp - HOT, 0.0) / SCALE) ** 2 + np.maximum(temp - THROTTLE, 0.0) / 4.0


# ---------------------------------------------------------------------------------------------- instances
def _row_adjacency(rows, per_row, across=False):
    R = rows * per_row
    A = np.zeros((R, R))
    for r in range(rows):
        for i in range(per_row - 1):
            a, b = r * per_row + i, r * per_row + i + 1
            A[a, b] = A[b, a] = 1.0
    if across:
        for r in range(rows - 1):
            for i in range(per_row):
                a, b = r * per_row + i, (r + 1) * per_row + i
                A[a, b] = A[b, a] = 1.0
    return A


def make_hall(family, rng):
    """(racks R, servers per rack S, cooling (R,), adjacency (R, R), coupling, arrival minutes (n,), sizes, durations)."""
    if family == "row":
        R, S = 8, 5
        cooling = np.linspace(0.055, 0.035, R)
        A, kappa = _row_adjacency(1, R), 0.01
        arr = np.sort(rng.integers(0, WINDOW, int(rng.poisson(LOAD["row"] * WINDOW))))
        n = len(arr)
        size = rng.integers(1, 9, n)
        dur = rng.integers(10, 81, n)
    elif family == "pods":
        R, S = 10, 4
        cooling = np.full(R, 0.05) * rng.uniform(0.9, 1.1, R)
        A, kappa = _row_adjacency(2, 5, across=True), 0.02
        t = np.arange(WINDOW)
        lam_t = LOAD["pods"] * (1 + 0.6 * np.sin(2 * np.pi * t / 150 + rng.uniform(0, 2 * np.pi)))
        arr = np.repeat(t, rng.poisson(lam_t))
        n = len(arr)
        big = rng.random(n) < 0.15
        size = np.where(big, rng.integers(8, 17, n), rng.integers(1, 5, n))
        dur = np.where(big, rng.integers(60, 151, n), rng.integers(5, 31, n))
    elif family == "bursts":
        R, S = 9, 4
        cooling = np.where(np.arange(R) % 2 == 0, 0.075, 0.035)
        A, kappa = _row_adjacency(1, R), 0.01
        parts, s = [rng.integers(0, WINDOW, int(rng.poisson(0.35 * WINDOW)))], int(rng.integers(0, 20))
        while s < WINDOW:
            parts.append(np.full(int(rng.poisson(LOAD["bursts"])), s))
            s += int(rng.integers(25, 46))
        arr = np.sort(np.concatenate(parts))
        n = len(arr)
        size = rng.integers(4, 17, n)
        dur = rng.integers(15, 61, n)
    elif family == "mixed":
        R, S = 12, 4
        cooling = np.repeat([0.06, 0.035, 0.06], 4) * rng.uniform(0.9, 1.1, R)
        A, kappa = _row_adjacency(3, 4, across=True), 0.015
        parts, s = [rng.integers(0, WINDOW, int(rng.poisson(LOAD["mixed"] * WINDOW)))], int(rng.integers(0, 30))
        while s < WINDOW:
            parts.append(np.full(int(rng.poisson(12)), s))
            s += int(rng.integers(40, 70))
        arr = np.sort(np.concatenate(parts))
        n = len(arr)
        size = np.minimum(rng.geometric(0.22, n), SLOTS)
        dur = np.clip(np.round(rng.lognormal(np.log(30), 0.8, n)), 5, 240)
    else:
        raise KeyError(family)
    return R, S, np.round(cooling, 4), A, kappa, arr.astype(np.int64), size.astype(np.int64), dur.astype(float)


def _instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for fam in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], CODES[fam], i])
            R, S, cooling, A, kappa, arr, size, dur = make_hall(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "seed": [SPLIT_SEED[split], CODES[fam], i, 99], "R": R, "S": S, "cooling": cooling,
                        "neighbors": A * kappa, "arrive": arr, "size": size, "duration": dur})
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
    """Run the hall under `priority` (None = Code Zero: always the first shuffled candidate). Returns stats."""
    R, S = inst["R"], inst["S"]
    cool, A = inst["cooling"], inst["neighbors"]                       # A[r, a] = coupling between adjacent racks
    deg = A.sum(1)
    arr, size, dur = inst["arrive"], inst["size"], inst["duration"]
    n = len(arr)
    rng = np.random.default_rng(inst["seed"])
    free = np.full(R * S, SLOTS, dtype=np.int64)
    rack_used = np.zeros(R)
    temps = np.full(R, T_SUPPLY)
    rem = np.zeros(n)
    rk = np.zeros(n, dtype=np.int64)
    srv = np.zeros(n, dtype=np.int64)
    start = np.zeros(n)
    finish = np.zeros(n)
    run_idx = np.zeros(0, dtype=np.int64)
    queue = []
    nxt = done = decisions = 0
    peak, spread_sum, spread_n = T_SUPPLY, 0.0, 0
    sizef, cap = size.astype(float), float(S * SLOTS)

    def place(j, t, waiting):
        """Place job j if some server has room (a decision); returns True if placed."""
        nonlocal run_idx, decisions
        cands = np.flatnonzero(free >= size[j])
        k = len(cands)
        if k == 0:
            return False
        cands = cands[rng.permutation(k)]
        if k == 1 or priority is None:
            c = int(cands[0])
        else:
            q = np.array(waiting, dtype=np.int64)
            args = (int(size[j]), free[cands].astype(float), cands // S, float(dur[j]), temps.copy(), cool, A,
                    free.reshape(R, S).astype(float), np.column_stack([rk[run_idx], sizef[run_idx], rem[run_idx]]),
                    np.column_stack([sizef[q], dur[q]]), float(t))
            c = int(cands[_choose(priority, args, k)])
        if k > 1:
            decisions += 1
        free[c] -= size[j]
        rk[j], srv[j] = c // S, c
        rack_used[c // S] += size[j]
        rem[j], start[j] = dur[j], t
        run_idx = np.append(run_idx, j)
        return True

    t, freed = 0, False
    while done < n:
        if queue and freed:                                            # waiting jobs first, in arrival order
            mx = int(free.max())
            i = 0
            while i < len(queue):
                j = queue[i]
                if size[j] <= mx and place(j, t, queue[:i] + queue[i + 1:]):
                    queue.pop(i)
                    mx = int(free.max())
                else:
                    i += 1
        while nxt < n and arr[nxt] == t:                               # then this minute's arrivals
            if not place(nxt, t, queue):
                queue.append(nxt)
            nxt += 1
        freed = False
        heat = rack_used.copy()                                        # the load of this minute
        if len(run_idx):                                               # one minute of work at current speeds
            prog = 1.0 / slowdown(temps)[rk[run_idx]]
            r = rem[run_idx] - prog
            fin = r <= 1e-9
            if fin.any():
                ids = run_idx[fin]
                finish[ids] = t + rem[ids] / prog[fin]
                np.add.at(free, srv[ids], size[ids])
                np.add.at(rack_used, rk[ids], -sizef[ids])
                run_idx, r = run_idx[~fin], r[~fin]
                done += len(ids)
                freed = True
            rem[run_idx] = r
            spread_sum += float(temps.max() - temps.min())
            spread_n += 1
        temps = temps + GAIN * heat / cap - cool * (temps - T_SUPPLY) + (A @ temps - deg * temps)
        peak = max(peak, float(temps.max()))
        t += 1
        if t > 100 * WINDOW:
            raise RuntimeError("thermal: the simulation did not finish")
    extra = np.maximum(finish - arr - dur, 0.0)
    wait = start - arr
    return {"cost": float(extra.sum()), "wait": float(wait.sum()), "queued": int((wait > 0).sum()),
            "stretch": float(np.mean((finish - arr) / dur)), "peak": peak,
            "spread": spread_sum / max(1, spread_n), "decisions": decisions, "n": n, "minutes": t}


def cz_cost(inst):
    c = _CZ.get(inst["id"])
    if c is None:
        c = _CZ[inst["id"]] = simulate(inst)["cost"]
        if not c > 0:
            raise RuntimeError(f"thermal: Code Zero has cost {c} on {inst['id']}")
    return c


# ---------------------------------------------------------------------------------------------- the problem
class Thermal(Problem):
    name = "thermal"
    title = "Thermal: placing jobs in a data hall that heats up"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time)"
    candidates_arg = 1
    description = f"""A data hall has R racks, each holding S servers; every server has {SLOTS} slots. Jobs arrive over time (at whole minutes, during the first {WINDOW} minutes). A job needs `size` slots (1-{SLOTS}) on one server for as long as it runs, and has an ideal `duration` in minutes: the time it takes at full speed. A server can run several jobs at once while their sizes fit in its {SLOTS} slots. A job is placed on one server and stays there until it finishes.

**Heat.** Each rack has a temperature (deg C), starting at the supply air temperature {T_SUPPLY:.0f}. Every minute, rack r's temperature changes by
`{GAIN:g} * used_slots_r / (S * {SLOTS})  -  cooling_r * (temp_r - {T_SUPPLY:.0f})  +  sum over racks a of neighbors[r, a] * (temp_a - temp_r)`,
where used_slots_r counts the slots of the jobs running in the rack, cooling_r is the rack's own cooling coefficient (it depends on where the rack stands) and neighbors[r, a] is the heat coupling between racks r and a (positive only for adjacent racks, else 0). **Slowdown.** A rack at temperature T runs every job in it slower by the factor
`slowdown(T) = 1 + (max(T - {HOT:.0f}, 0) / {SCALE:.0f})^2 + max(T - {THROTTLE:.0f}, 0) / 4`
(1 = full speed): in one minute a job completes 1 / slowdown minutes of its ideal work. The temperatures at the start of a minute set the speeds for that minute; jobs that finish free their slots, and the temperatures then update with the load of that minute.

One **decision** = placing one job. Each minute, first the jobs waiting in the queue are tried in arrival order, then the jobs arriving that minute. A job is placed on one of the servers with enough free slots for it: those servers are the **candidates**, in a random order (reshuffled at every decision), so the position carries no information. If no server has room, the job joins the end of the wait queue automatically and is offered again (another decision) as soon as some server has room for it; a later job that fits may be placed before an earlier waiting one that does not. A decision with a single candidate is taken automatically. Nothing is known about jobs that have not arrived yet.

**Cost** of an instance (lower is better) = the sum over all jobs of (finish time - arrival time - ideal duration), in minutes: the time lost to waiting in the queue plus the time lost to heat slowdown. Families differ in the arrival pattern (steady, varying, batches), the rack layout (number of racks and servers, which racks are adjacent, cooling coefficients) and the job mix (sizes and durations). Three training families: `row`, `pods`, `bursts`; the test split adds a family that training never shows.

There is no known best solution: the score of an instance is **gap = 100 x cost / cost of Code Zero** on that instance, where Code Zero is the policy that always takes the first candidate (a random choice, because the order is shuffled). Code Zero scores 100; lower is better and nothing tells where the best possible lies."""
    signature_doc = f"""- `size`: int: slots the job needs (1-{SLOTS}).
- `free`: shape (k,), float: free slots on each candidate server before placing the job (always >= size). These are the candidates, in a random order.
- `rack`: shape (k,), int: the rack index (0..R-1) of each candidate server.
- `duration`: float: the job's ideal duration in minutes (at full speed).
- `temps`: shape (R,), float: the current temperature of every rack, deg C.
- `cooling`: shape (R,), float: every rack's cooling coefficient (see the heat rule).
- `neighbors`: shape (R, R), float, symmetric: the heat coupling between two racks (see the heat rule): positive where the racks are adjacent, 0 elsewhere and on the diagonal.
- `server_free`: shape (R, S), float: free slots on every server of the hall, rack by rack (row r = rack r).
- `running`: shape (m, 3), float: every job running now: [rack index, size, ideal work still to do in minutes].
- `queue`: shape (q, 2), float: the other jobs waiting in the queue, in arrival order: [size, ideal duration] (q = 0 when nobody else waits).
- `time`: float: the current minute (jobs arrive during minutes 0-{WINDOW - 1}).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The job goes to the highest-scoring server."""
    metric_notes = {
        "cost": "total minutes lost over all jobs (waiting + heat slowdown; what the gap measures)",
        "queued_pct": "% of jobs that had to wait in the queue",
        "wait_share_pct": "minutes spent waiting in the queue, % of the cost (the rest is heat slowdown)",
        "mean_stretch": "mean over jobs of (finish - arrival) / ideal duration (1 = no loss)",
        "peak_temp": "the highest rack temperature reached, deg C",
        "temp_spread": "mean over minutes (while jobs run) of hottest minus coolest rack temperature, deg C",
    }
    example_features = [
        "import numpy as np\n\ndef feature(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time):\n"
        "    \"\"\"Minus the temperature of the candidate's rack.\"\"\"\n"
        "    return -temps[rack]\n",
        "import numpy as np\n\ndef feature(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time):\n"
        "    \"\"\"Two columns: free slots left after placing, and the rack's cooling coefficient.\"\"\"\n"
        "    return np.stack([free - size, cooling[rack]], axis=1)\n",
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
        return {"gap": 100.0 * (s["cost"] / base), "cost": s["cost"], "queued_pct": 100.0 * s["queued"] / s["n"],
                "peak_temp": s["peak"]}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        base = cz_cost(instance)
        s = simulate(instance, priority)
        return {
            "gap": round(100.0 * (s["cost"] / base), 3),
            "cost": round(s["cost"], 1),
            "queued_pct": round(100 * s["queued"] / s["n"], 2),
            "wait_share_pct": round(100 * s["wait"] / max(s["cost"], 1e-9), 2),
            "mean_stretch": round(s["stretch"], 3),
            "peak_temp": round(s["peak"], 2),
            "temp_spread": round(s["spread"], 2),
        }
