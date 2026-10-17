"""Capacitated vehicle routing, built stop by stop.

Identical vehicles of capacity Q start and end at a depot; every customer has a demand and is visited exactly
once. The routes are built one stop at a time, one vehicle after another: at each decision the policy scores
the unvisited customers whose demand fits the current vehicle's remaining capacity (index order) plus, once
the current route has served at least one customer, the option to return to the depot and start a new
vehicle (always last). When no customer fits the vehicle returns automatically; after the last customer the
last vehicle returns. The gap is total length over the best solution known for the instance (cached in
suite/data/cvrp_refs.json, rebuilt with `python -m suite.cvrp --refs`: Clarke-Wright savings starts, then
ruin-and-recreate under simulated annealing, finished with 2-opt, relocate and swap moves), so the floor is 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "suite" / "data" / "cvrp_refs.json"
SPLIT_SEED = {"train": 1401, "valid": 2502, "test": 3603}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family: (seed code, number of customers, vehicle capacity); demands are integers 1-10
FAMILIES = {"uniform": (1, 50, 40), "clustered": (2, 60, 50), "eccentric": (3, 50, 40), "large": (4, 80, 45)}
TRAIN_FAMILIES = ["uniform", "clustered", "eccentric"]
HELD_OUT = ["large"]


# ---------------------------------------------------------------------------------------------- instances
def make_customers(family, rng):
    """(depot (2,), customer coords (n, 2), demands (n,) int, capacity)."""
    code, n, cap = FAMILIES[family]
    if family in ("uniform", "eccentric"):
        xy = rng.uniform(0.0, 1.0, size=(n, 2))
    elif family == "clustered":
        c = int(rng.integers(3, 7))
        centres = rng.uniform(0.1, 0.9, size=(c, 2))
        xy = centres[rng.integers(0, c, size=n)] + rng.normal(0.0, 0.05, size=(n, 2))
    elif family == "large":
        h = n // 2
        centres = rng.uniform(0.15, 0.85, size=(3, 2))
        a = centres[rng.integers(0, 3, size=h)] + rng.normal(0.0, 0.04, size=(h, 2))
        xy = np.vstack([a, rng.uniform(0.0, 1.0, size=(n - h, 2))])
    else:
        raise KeyError(family)
    if family == "eccentric":
        depot = rng.integers(0, 2, size=2).astype(float)          # one of the four corners
    elif family == "large":
        depot = rng.uniform(0.2, 0.8, size=2)
    else:
        depot = np.array([0.5, 0.5])
    xy = np.clip(xy, 0.0, 1.0)[rng.permutation(n)]                # random numbering: index order means nothing
    demands = rng.integers(1, 11, size=n).astype(np.int64)
    return np.round(depot, 4), np.round(xy, 4), demands, int(cap)


def _hash(depot, xy, demands, cap):
    blob = (np.ascontiguousarray(np.round(depot, 4)).tobytes() + np.ascontiguousarray(np.round(xy, 4)).tobytes()
            + np.ascontiguousarray(demands, dtype=np.int64).tobytes() + str(int(cap)).encode())
    return hashlib.sha1(blob).hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code = FAMILIES[fam][0]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            depot, xy, dem, cap = make_customers(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "depot": depot, "coords": xy, "demands": dem, "capacity": cap})
    return out


def dist_matrix(xy):
    d = xy[:, None, :] - xy[None, :, :]
    return np.sqrt((d ** 2).sum(-1))


def route_lengths(depot, xy, routes):
    """Length of each route (customer indices 0..n-1; each route starts and ends at the depot)."""
    out = []
    for r in routes:
        p = np.vstack([depot, xy[np.asarray(r, dtype=np.int64)], depot])
        out.append(float(np.sqrt(((p[1:] - p[:-1]) ** 2).sum(1)).sum()))
    return out


def validate(inst, routes):
    """Plain-Python check: every customer exactly once, no route over capacity."""
    n, cap, dem = len(inst["coords"]), int(inst["capacity"]), inst["demands"]
    seen = sorted(int(c) for r in routes for c in r)
    if seen != list(range(n)):
        raise ValueError("invalid solution: customers missing or visited twice")
    for r in routes:
        if not r or sum(int(dem[c]) for c in r) > cap:
            raise ValueError("invalid solution: empty route or route over capacity")


# ---------------------------------------------------------------------------------------------- diagnostics
def _crossings(segs):
    """Pairs of route legs that properly cross (legs sharing an endpoint, e.g. at the depot, do not count)."""
    a, b = segs[:, 0], segs[:, 1]

    def orient(p1, p2, p3):
        return np.sign((p2[..., 0] - p1[..., 0]) * (p3[..., 1] - p1[..., 1])
                       - (p2[..., 1] - p1[..., 1]) * (p3[..., 0] - p1[..., 0]))

    A, B = a[:, None, :], b[:, None, :]
    C, D = a[None, :, :], b[None, :, :]
    x = (orient(A, B, C) * orient(A, B, D) < 0) & (orient(C, D, A) * orient(C, D, B) < 0)
    i, j = np.triu_indices(len(segs), 1)
    return int(x[i, j].sum())


def solution_metrics(inst, routes, ref_len):
    depot, xy, dem, cap = inst["depot"], inst["coords"], inst["demands"], int(inst["capacity"])
    lens = route_lengths(depot, xy, routes)
    L = float(sum(lens))
    loads = np.array([int(dem[np.asarray(r)].sum()) for r in routes])
    segs, depot_legs = [], 0.0
    for r in routes:
        p = np.vstack([depot, xy[np.asarray(r, dtype=np.int64)], depot])
        segs.append(np.stack([p[:-1], p[1:]], axis=1))
        depot_legs += float(np.sqrt(((p[1] - p[0]) ** 2).sum()) + np.sqrt(((p[-1] - p[-2]) ** 2).sum()))
    segs = np.concatenate(segs)
    typical = float(np.median(dem))
    return {
        "gap": round(100 * (L / ref_len - 1), 3) + 0.0,
        "route_length": round(L, 4),
        "routes": len(routes),
        "min_routes": int(-(-int(dem.sum()) // cap)),
        "mean_load_pct": round(100 * float(loads.mean()) / cap, 2),
        "depot_returns_early": int((cap - loads >= typical).sum()),
        "longest_route": round(max(lens), 4),
        "depot_legs_pct": round(100 * depot_legs / L, 2),
        "crossings": _crossings(segs),
        "_text": "route loads (% of capacity): " + ", ".join(str(int(round(100 * x / cap))) for x in sorted(loads)),
    }


# ---------------------------------------------------------------------------------------------- the problem
def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


class CVRP(Problem):
    name = "cvrp"
    title = "Capacitated vehicle routing: build the routes stop by stop"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    signature = "feature(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands)"
    candidates_arg = 1
    description = """A fleet of identical delivery vehicles is based at a depot. Each vehicle can carry `capacity` units. Every customer has a demand (an integer from 1 to 10) and must be visited exactly once, by one vehicle, which delivers the whole demand. A vehicle leaves the depot, visits customers whose demands add up to at most the capacity, and drives back to the depot. There are as many vehicles as needed. Distances are straight-line (Euclidean). The goal is the shortest total distance driven by all vehicles together.

The routes are built one stop at a time, one vehicle after another. The first vehicle starts at the depot with its full capacity. At each step the policy picks where the current vehicle goes next: an unvisited customer whose demand fits in the capacity it has left, or, once it has visited at least one customer, back to the depot. Going back ends that vehicle's route, and the next vehicle starts from the depot with its full capacity. When no unvisited customer fits, the vehicle goes back to the depot automatically. When every customer has been served, the last vehicle goes back to the depot. Every leg, including the legs from and to the depot, counts toward the length.

One **decision** = choosing the current vehicle's next stop. The **candidates** are the unvisited customers whose demand fits the remaining capacity, in index order, followed by the option to go back to the depot (always the last candidate, and present only when the current route has visited at least one customer). Customers are numbered at random, so the index carries no information. A decision with a single candidate is taken automatically.

There are three training families in the unit square, all with demands 1-10: `uniform` (50 customers spread evenly at random, depot at the centre, capacity 40), `clustered` (60 customers in a few tight groups, depot at the centre, capacity 50) and `eccentric` (50 customers spread evenly, depot in a corner of the square, capacity 40). The test split adds a family that training never shows. The **gap** of an instance is total length / the best solution known for that instance - 1, in %. The best-known solutions come from a long offline search, so 0 is about the best possible."""
    signature_doc = """- `current`: shape (2,), float: [x, y] of where the current vehicle is now. It equals `depot` at the first stop of a route (when the depot option is absent).
- `candidates`: shape (k, 2), float: [x, y] of every candidate. The unvisited customers that fit, in index order, come first. **When the current route has already visited at least one customer, the last row is the go-back-to-the-depot option and equals `depot`**; at the first stop of a route there is no depot option and every row is a customer.
- `demands`: shape (k,), int: the demand of each candidate (1-10 for a customer, at most `remaining`); **0 for the depot option**, so `demands == 0` marks it.
- `remaining`: int: the capacity the current vehicle has left (at least 1).
- `capacity`: int: a vehicle's full capacity (40 or 50 in training, but other capacities exist: normalise by it).
- `depot`: shape (2,), float: [x, y] of the depot, where every route starts and ends.
- `unvisited`: shape (m, 2), float: [x, y] of every customer not yet visited, in index order, including those that do not fit in the current vehicle (the customer candidates are among them).
- `unvisited_demands`: shape (m,), int: the demands of `unvisited`.
- Coordinates lie in [0, 1].
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is the next stop."""
    metric_notes = {
        "route_length": "total length of all routes (what the gap measures)",
        "routes": "vehicles used",
        "min_routes": "ceil(total demand / capacity): the fewest vehicles any solution can use",
        "mean_load_pct": "average vehicle load, % of capacity",
        "depot_returns_early": "routes that came back with unused capacity of at least the median customer demand",
        "longest_route": "length of the longest single route",
        "depot_legs_pct": "legs from and to the depot (first and last leg of every route), % of total length",
        "crossings": "pairs of legs (within or between routes) that cross each other",
    }
    # hidden textbook baseline (never shown to agents): go to the nearest customer that fits; the depot only when forced
    baseline = [("import numpy as np\n\ndef feature(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):\n"
                 "    d = np.sqrt(((candidates - current) ** 2).sum(1))\n    return np.where(demands > 0, -d, -10.0)\n", 1.0)]
    example_features = [
        "import numpy as np\n\ndef feature(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):\n"
        "    \"\"\"Minus the distance from the current position.\"\"\"\n"
        "    return -np.sqrt(((candidates - current) ** 2).sum(axis=1))\n",
        "import numpy as np\n\ndef feature(current, candidates, demands, remaining, capacity, depot, unvisited, unvisited_demands):\n"
        "    \"\"\"Two columns: the candidate's demand as a fraction of capacity, and is it the depot option.\"\"\"\n"
        "    return np.stack([demands / capacity, (demands == 0).astype(float)], axis=1)\n",
    ]

    def __init__(self):
        self._cache = {}
        self._refs = None

    # -------------------------------------------------------------------------------------- data
    def refs(self):
        if self._refs is None:
            try:
                self._refs = json.loads(REFS.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                raise RuntimeError(f"missing {REFS.relative_to(ROOT)}: run `python -m suite.cvrp --refs`")
        return self._refs

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            refs = self.refs()
            out = raw_instances(split)
            for inst in out:
                r = refs.get(inst["id"])
                if r is None or r["hash"] != _hash(inst["depot"], inst["coords"], inst["demands"], inst["capacity"]):
                    raise RuntimeError(f"cvrp reference for {inst['id']} is missing or stale: "
                                       "run `python -m suite.cvrp --refs`")
                inst["ref"] = float(r["length"])
            self._cache[split] = out
        return self._cache[split]

    # -------------------------------------------------------------------------------------- simulate
    def build(self, instance, priority):
        xy, dem, depot = instance["coords"], instance["demands"], instance["depot"]
        cap = int(instance["capacity"])
        unvisited = np.ones(len(xy), dtype=bool)
        routes, route = [], []
        rem, cur = cap, depot
        zero = np.zeros(1, dtype=np.int64)
        left = len(xy)
        while left:
            fit = np.flatnonzero(unvisited & (dem <= rem))
            if len(fit) == 0:                                     # nothing fits: back to the depot automatically
                routes.append(route)
                route, rem, cur = [], cap, depot
                continue
            k = len(fit) + (1 if route else 0)
            if k == 1:
                c = 0
            else:
                cand, cd = xy[fit], dem[fit]
                if route:
                    cand, cd = np.vstack([cand, depot]), np.concatenate([cd, zero])
                uv = np.flatnonzero(unvisited)
                c = _choose(priority, (cur.copy(), cand, cd, int(rem), cap, depot.copy(), xy[uv], dem[uv]), k)
            if c == len(fit):                                     # the depot option: start a new vehicle
                routes.append(route)
                route, rem, cur = [], cap, depot
            else:
                j = int(fit[c])
                route.append(j)
                unvisited[j] = False
                rem -= int(dem[j])
                cur = xy[j]
                left -= 1
        routes.append(route)
        validate(instance, routes)
        return routes

    def run(self, instance, priority):
        routes = self.build(instance, priority)
        L = float(sum(route_lengths(instance["depot"], instance["coords"], routes)))
        return {"gap": 100.0 * (L / instance["ref"] - 1.0), "route_length": L, "routes": len(routes)}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        return solution_metrics(instance, self.build(instance, priority), instance["ref"])

    def reference_metrics(self, instance):
        r = self.refs().get(instance["id"])
        return solution_metrics(instance, r["routes"], instance["ref"]) if r else {}


# ---------------------------------------------------------------------------------------------- references
# Solver nodes: 0 = depot, c + 1 = customer c. D is a list of lists (fast scalar access in pure Python).
def _cost(routes, D):
    tot = 0.0
    for r in routes:
        prev = 0
        for c in r:
            tot += D[prev][c]
            prev = c
        tot += D[prev][0]
    return tot


def _savings(Dn, dem, Q, lam, noise, rng):
    """Clarke-Wright parallel savings with savings D0i + D0j - lam * Dij, optionally perturbed."""
    n = len(Dn) - 1
    i, j = np.triu_indices(n, 1)
    i, j = i + 1, j + 1
    s = Dn[0, i] + Dn[0, j] - lam * Dn[i, j]
    if noise:
        s = s * rng.uniform(1 - noise, 1 + noise, size=len(s))
    route_of = list(range(n + 1))
    routes = {c: [c] for c in range(1, n + 1)}
    load = {c: int(dem[c]) for c in range(1, n + 1)}
    for k in np.argsort(-s):
        if s[k] <= 0:
            break
        a, b = int(i[k]), int(j[k])
        ra, rb = route_of[a], route_of[b]
        if ra == rb or load[ra] + load[rb] > Q:
            continue
        A, B = routes[ra], routes[rb]
        if A[-1] != a:
            if A[0] != a:
                continue
            A.reverse()
        if B[0] != b:
            if B[-1] != b:
                continue
            B.reverse()
        A.extend(B)
        load[ra] += load.pop(rb)
        for c in B:
            route_of[c] = ra
        del routes[rb]
    return list(routes.values())


def _ruin(routes, loads, adj, dem, rng, cbar=10, lmax=10):
    """String and split-string removals around a random seed customer (SISR). Mutates routes and loads;
    returns the removed customers."""
    where = {}
    for ri, r in enumerate(routes):
        for c in r:
            where[c] = ri
    ls_max = min(lmax, sum(len(r) for r in routes) / len(routes))
    ks = int(rng.uniform(1, 4 * cbar / (1 + ls_max)))
    removed, ruined = [], set()
    for c in adj[rng.randrange(1, len(adj))]:
        if len(ruined) >= ks:
            break
        ri = where[c]
        if ri in ruined:
            continue
        r = routes[ri]
        lt = int(rng.uniform(1, min(len(r), ls_max) + 1))
        m = 0
        if lt < len(r) and rng.random() < 0.5:                 # split string: keep m customers in the middle
            m = 1
            while lt + m < len(r) and rng.random() < 0.5:
                m += 1
        w = lt + m
        pos = r.index(c)
        start = rng.randint(max(0, pos - w + 1), min(pos, len(r) - w))
        keep_at = rng.randint(0, lt) if m else 0
        window = r[start:start + w]
        out = window[:keep_at] + window[keep_at + m:]
        routes[ri] = r[:start] + window[keep_at:keep_at + m] + r[start + w:]
        loads[ri] -= sum(dem[x] for x in out)
        removed.extend(out)
        ruined.add(ri)
    return removed


def _recreate(routes, loads, removed, D, dem, Q, rng, blink=0.01):
    """Greedy cheapest insertion (each improving position skipped with probability `blink`)."""
    x = rng.random() * 11
    if x < 4:
        rng.shuffle(removed)
    elif x < 8:
        removed.sort(key=lambda c: -dem[c])
    elif x < 10:
        removed.sort(key=lambda c: -D[0][c])
    else:
        removed.sort(key=lambda c: D[0][c])
    for c in removed:
        Dc, dc = D[c], dem[c]
        best, br, bp = 2 * Dc[0], -1, 0
        for ri, r in enumerate(routes):
            if loads[ri] + dc > Q:
                continue
            prev = 0
            for p, nxt in enumerate(r):
                delta = Dc[prev] + Dc[nxt] - D[prev][nxt]
                if delta < best and rng.random() > blink:
                    best, br, bp = delta, ri, p
                prev = nxt
            delta = Dc[prev] + Dc[0] - D[prev][0]
            if delta < best and rng.random() > blink:
                best, br, bp = delta, ri, len(r)
        if br < 0:
            routes.append([c])
            loads.append(dc)
        else:
            routes[br].insert(bp, c)
            loads[br] += dc


def _polish(routes, D, dem, Q):
    """Intra-route 2-opt plus inter-route relocate and swap, first improvement, until no move improves."""
    routes = [r[:] for r in routes if r]
    loads = [sum(dem[c] for c in r) for r in routes]

    def ins_cost(r, p, c):                                      # cost of putting c before position p of r
        a = r[p - 1] if p > 0 else 0
        b = r[p] if p < len(r) else 0
        return D[a][c] + D[c][b] - D[a][b]

    def rem_gain(r, p):
        a = r[p - 1] if p > 0 else 0
        b = r[p + 1] if p + 1 < len(r) else 0
        return D[a][r[p]] + D[r[p]][b] - D[a][b]

    improved = True
    while improved:
        improved = False
        routes = [_two_opt_route(r, D) for r in routes]
        for i in range(len(routes)):                            # relocate one customer to another route
            for p in range(len(routes[i])):
                c, g = routes[i][p], rem_gain(routes[i], p)
                for j in range(len(routes)):
                    if j == i or loads[j] + dem[c] > Q:
                        continue
                    for q in range(len(routes[j]) + 1):
                        if ins_cost(routes[j], q, c) < g - 1e-10:
                            routes[j].insert(q, c)
                            del routes[i][p]
                            loads[j] += dem[c]
                            loads[i] -= dem[c]
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
        if improved:
            keep = [k for k, r in enumerate(routes) if r]
            routes, loads = [routes[k] for k in keep], [loads[k] for k in keep]
            continue
        for i in range(len(routes)):                            # swap two customers of different routes
            for j in range(i + 1, len(routes)):
                ri, rj = routes[i], routes[j]
                for p in range(len(ri)):
                    for q in range(len(rj)):
                        a, b = ri[p], rj[q]
                        if loads[i] - dem[a] + dem[b] > Q or loads[j] - dem[b] + dem[a] > Q:
                            continue
                        old = _cost([ri, rj], D)
                        ri[p], rj[q] = b, a
                        if _cost([ri, rj], D) < old - 1e-10:
                            loads[i] += dem[b] - dem[a]
                            loads[j] += dem[a] - dem[b]
                            improved = True
                            break
                        ri[p], rj[q] = a, b
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return routes


def _two_opt_route(r, D):
    r = [0] + list(r) + [0]
    improved = True
    while improved:
        improved = False
        for i in range(len(r) - 3):
            for j in range(i + 2, len(r) - 1):
                if D[r[i]][r[j]] + D[r[i + 1]][r[j + 1]] < D[r[i]][r[i + 1]] + D[r[j]][r[j + 1]] - 1e-12:
                    r[i + 1:j + 1] = r[i + 1:j + 1][::-1]
                    improved = True
    return r[1:-1]


def solve(depot, xy, demands, Q, iters=30000, restarts=3, seed=0, t0=0.3, tf=0.003):
    """Best of `restarts` runs: a (perturbed) savings start, ruin-and-recreate with simulated annealing."""
    P = np.vstack([depot, xy])
    Dn = dist_matrix(P)
    D = Dn.tolist()
    dem = [0] + [int(d) for d in demands]
    adj = [[]] + [[int(c) + 1 for c in np.argsort(Dn[i, 1:], kind="stable")] for i in range(1, len(P))]
    nrng = np.random.default_rng(seed)
    rng = random.Random(seed)
    best, best_cost = None, math.inf
    for rs in range(restarts):
        cur = _savings(Dn, dem, Q, 1.0 if rs == 0 else float(nrng.uniform(0.6, 1.4)), 0.0 if rs == 0 else 0.1, nrng)
        cur_cost = _cost(cur, D)
        cur_loads = [sum(dem[c] for c in r) for r in cur]
        run_best, run_cost = [r[:] for r in cur], cur_cost
        avg_edge = cur_cost / (len(xy) + len(cur))
        T0, Tf = t0 * avg_edge, tf * avg_edge
        for it in range(iters):
            T = T0 * (Tf / T0) ** (it / iters)
            new, loads = [r[:] for r in cur], cur_loads[:]
            removed = _ruin(new, loads, adj, dem, rng)
            keep = [k for k, r in enumerate(new) if r]
            new, loads = [new[k] for k in keep], [loads[k] for k in keep]
            _recreate(new, loads, removed, D, dem, Q, rng)
            c = _cost(new, D)
            if c < cur_cost - T * math.log(1.0 - rng.random()):
                cur, cur_cost, cur_loads = new, c, loads
                if c < run_cost - 1e-12:
                    run_best, run_cost = [r[:] for r in new], c
        run_best = _polish(run_best, D, dem, Q)
        run_cost = _cost(run_best, D)
        if run_cost < best_cost - 1e-12:
            best, best_cost = run_best, run_cost
    return [[c - 1 for c in r] for r in best], best_cost


def build_refs(iters=30000, restarts=3):
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in raw_instances(split):
            seed = int(hashlib.sha1(inst["id"].encode()).hexdigest()[:8], 16)
            routes, L = solve(inst["depot"], inst["coords"], inst["demands"], inst["capacity"], iters, restarts, seed)
            validate(inst, routes)
            L = float(sum(route_lengths(inst["depot"], inst["coords"], routes)))
            out[inst["id"]] = {"length": round(L, 6), "routes": routes,
                               "hash": _hash(inst["depot"], inst["coords"], inst["demands"], inst["capacity"])}
            print(f"  {inst['id']:16s} n={len(inst['coords']):3d} routes {len(routes):2d} best {L:.4f}  "
                  f"({time.time() - t0:.0f}s)", flush=True)
    REFS.parent.mkdir(parents=True, exist_ok=True)
    REFS.write_text(json.dumps({"method": f"Clarke-Wright savings starts, ruin-and-recreate (string removals, "
                                          f"greedy reinsertion with blinks) under simulated annealing, then 2-opt, "
                                          f"relocate and swap; {restarts} restarts x {iters} iterations", "instances": out}, indent=0))
    print(f"wrote {REFS} ({len(out)} instances, {time.time() - t0:.0f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs", action="store_true", help="rebuild suite/data/cvrp_refs.json")
    ap.add_argument("--iters", type=int, default=30000)
    ap.add_argument("--restarts", type=int, default=3)
    a = ap.parse_args(argv)
    if a.refs:
        build_refs(a.iters, a.restarts)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
