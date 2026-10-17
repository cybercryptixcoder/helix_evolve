"""Travelling salesman, built city by city.

The tour starts at city 0; at each decision the policy scores the unvisited cities (index order) and the
best one is visited next; after the last city the tour closes back to city 0. The gap is tour length over
the best tour known for the instance (cached in suite/data/tsp_refs.json, rebuilt with
`python -m suite.tsp --refs`, an iterated 2-opt + or-opt search), so the floor is 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "suite" / "data" / "tsp_refs.json"
SPLIT_SEED = {"train": 1101, "valid": 2202, "test": 3303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family: (seed code, number of cities)
FAMILIES = {"uniform": (1, 60), "clustered": (2, 80), "grid": (3, 100), "mixed": (4, 100)}
TRAIN_FAMILIES = ["uniform", "clustered", "grid"]
HELD_OUT = ["mixed"]


# ---------------------------------------------------------------------------------------------- instances
def make_cities(family, rng):
    code, n = FAMILIES[family]
    if family == "uniform":
        xy = rng.uniform(0.0, 1.0, size=(n, 2))
    elif family == "clustered":
        c = int(rng.integers(4, 7))
        centres = rng.uniform(0.1, 0.9, size=(c, 2))
        xy = centres[rng.integers(0, c, size=n)] + rng.normal(0.0, 0.05, size=(n, 2))
    elif family == "grid":
        side = int(round(np.sqrt(n)))
        g = np.stack(np.meshgrid(np.arange(side), np.arange(side)), axis=-1).reshape(-1, 2)[:n]
        xy = (g + 0.5) / side + rng.normal(0.0, 0.12 / side, size=(n, 2))
    elif family == "mixed":
        h = n // 2
        centres = rng.uniform(0.15, 0.85, size=(3, 2))
        a = centres[rng.integers(0, 3, size=h)] + rng.normal(0.0, 0.04, size=(h, 2))
        xy = np.vstack([a, rng.uniform(0.0, 1.0, size=(n - h, 2))])
    else:
        raise KeyError(family)
    xy = np.clip(xy, 0.0, 1.0)[rng.permutation(n)]       # random numbering: index order means nothing
    return np.round(xy, 4)


def _hash(xy):
    return hashlib.sha1(np.ascontiguousarray(np.round(xy, 4)).tobytes()).hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code, n = FAMILIES[fam]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            xy = make_cities(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "coords": xy})
    return out


def dist_matrix(xy):
    d = xy[:, None, :] - xy[None, :, :]
    return np.sqrt((d ** 2).sum(-1))


def tour_length(xy, order):
    p = xy[np.asarray(order)]
    return float(np.sqrt(((p - np.roll(p, -1, axis=0)) ** 2).sum(1)).sum())


# ---------------------------------------------------------------------------------------------- diagnostics
def _crossings(p):
    """Number of pairs of non-adjacent tour edges that cross."""
    a, b = p, np.roll(p, -1, axis=0)
    n = len(p)

    def orient(p1, p2, p3):
        return np.sign((p2[..., 0] - p1[..., 0]) * (p3[..., 1] - p1[..., 1])
                       - (p2[..., 1] - p1[..., 1]) * (p3[..., 0] - p1[..., 0]))

    A, B = a[:, None, :], b[:, None, :]
    C, D = a[None, :, :], b[None, :, :]
    x = (orient(A, B, C) * orient(A, B, D) < 0) & (orient(C, D, A) * orient(C, D, B) < 0)
    i, j = np.triu_indices(n, 2)
    keep = ~((i == 0) & (j == n - 1))
    return int(x[i[keep], j[keep]].sum())


def tour_metrics(xy, order, ref_len):
    p = xy[np.asarray(order)]
    e = np.sqrt(((p - np.roll(p, -1, axis=0)) ** 2).sum(1))
    L = float(e.sum())
    D = dist_matrix(xy)
    np.fill_diagonal(D, np.inf)
    nn = float(D.min(1).mean())
    return {
        "gap": round(100 * (L / ref_len - 1), 3),
        "length": round(L, 4),
        "crossings": _crossings(p),
        "long_edges": int((e > 3 * nn).sum()),
        "longest_edge_pct": round(100 * float(e.max()) / L, 2),
        "closing_edge_pct": round(100 * float(e[-1]) / L, 2),
    }


# ---------------------------------------------------------------------------------------------- the problem
def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


class TSPConstruct(Problem):
    name = "tsp"
    title = "Travelling salesman: build the tour city by city"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    signature = "feature(current, candidates, tour, start)"
    candidates_arg = 1
    description = """A traveller must visit every city exactly once and come back to where they started. Distances are straight-line (Euclidean). The goal is the shortest closed tour.

The tour is built one city at a time. It starts at city 0. At each step the policy picks which unvisited city to go to next. After the last city the tour returns to city 0 automatically, and that closing leg counts toward the length.

One **decision** = choosing the next city. The **candidates** are all the unvisited cities, in index order. Cities are numbered at random, so the index carries no information. When only one city is left it is taken automatically.

There are three training families of cities in the unit square: `uniform` (60 cities spread evenly at random), `clustered` (80 cities in a few tight groups) and `grid` (100 cities on a jittered 10x10 grid). The test split adds a family that training never shows. The **gap** of an instance is tour length / the best tour known for that instance - 1, in %. The best-known tours come from a long offline search, so 0 is about the best possible."""
    signature_doc = """- `current`: shape (2,), float: [x, y] of the city the traveller is at now.
- `candidates`: shape (k, 2), float: [x, y] of every unvisited city, in index order. These are the candidates.
- `tour`: shape (m, 2), float: [x, y] of the cities visited so far, in visiting order. `tour[0]` is the start city and `tour[-1]` is the current city; m = 1 at the first decision. The instance has m + k cities.
- `start`: shape (2,), float: [x, y] of the start city, where the tour must end.
- Coordinates lie in [0, 1].
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is visited next."""
    metric_notes = {
        "length": "tour length",
        "crossings": "pairs of tour edges that cross each other",
        "long_edges": "edges longer than 3x the instance's mean nearest-neighbour distance",
        "longest_edge_pct": "the longest edge, % of tour length",
        "closing_edge_pct": "the closing leg from the last city back to the start, % of tour length",
    }
    # hidden textbook baseline (never shown to agents): go to the nearest city
    baseline = [("import numpy as np\n\ndef feature(current, candidates, tour, start):\n    return -np.sqrt(((candidates - current) ** 2).sum(1))\n", 1.0)]
    example_features = [
        "import numpy as np\n\ndef feature(current, candidates, tour, start):\n"
        "    \"\"\"Minus the distance from the current city.\"\"\"\n"
        "    return -np.sqrt(((candidates - current) ** 2).sum(axis=1))\n",
        "import numpy as np\n\ndef feature(current, candidates, tour, start):\n"
        "    \"\"\"Distance from the start city.\"\"\"\n"
        "    return np.sqrt(((candidates - start) ** 2).sum(axis=1))\n",
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
                raise RuntimeError(f"missing {REFS.relative_to(ROOT)}: run `python -m suite.tsp --refs`")
        return self._refs

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            refs = self.refs()
            out = raw_instances(split)
            for inst in out:
                r = refs.get(inst["id"])
                if r is None or r["hash"] != _hash(inst["coords"]):
                    raise RuntimeError(f"tsp reference for {inst['id']} is missing or stale: "
                                       "run `python -m suite.tsp --refs`")
                inst["ref"] = float(r["length"])
            self._cache[split] = out
        return self._cache[split]

    # -------------------------------------------------------------------------------------- simulate
    def build(self, instance, priority):
        xy = instance["coords"]
        n = len(xy)
        unvisited = np.ones(n, dtype=bool)
        unvisited[0] = False
        order = np.zeros(n, dtype=np.int64)
        start = xy[0]
        for m in range(1, n):
            cand = np.flatnonzero(unvisited)
            k = len(cand)
            c = 0 if k == 1 else _choose(priority, (xy[order[m - 1]].copy(), xy[cand], xy[order[:m]], start.copy()), k)
            order[m] = cand[c]
            unvisited[cand[c]] = False
        return order

    def run(self, instance, priority):
        order = self.build(instance, priority)
        L = tour_length(instance["coords"], order)
        return {"gap": 100.0 * (L / instance["ref"] - 1.0), "length": L}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        return tour_metrics(instance["coords"], self.build(instance, priority), instance["ref"])

    def reference_metrics(self, instance):
        r = self.refs().get(instance["id"])
        return tour_metrics(instance["coords"], r["tour"], instance["ref"]) if r else {}


# ---------------------------------------------------------------------------------------------- references
_VALID = {}


def _two_opt(t, D):
    n = len(t)
    valid = _VALID.get(n)
    if valid is None:
        valid = np.triu(np.ones((n, n), dtype=bool), 2)
        valid[0, n - 1] = False
        _VALID[n] = valid
    while True:
        tn = np.roll(t, -1)
        e = D[t, tn]
        delta = D[np.ix_(t, t)] + D[np.ix_(tn, tn)] - e[:, None] - e[None, :]
        delta = np.where(valid, delta, 0.0)
        k = int(np.argmin(delta))
        if delta.flat[k] > -1e-10:
            return t
        i, j = divmod(k, n)
        t[i + 1:j + 1] = t[i + 1:j + 1][::-1].copy()


def _or_opt(t, D):
    """Best segment move (length 1-3, either orientation). Returns the new tour or None."""
    n = len(t)
    idx = np.arange(n)
    a, b = t, np.roll(t, -1)
    dab = D[a, b]
    best, move = -1e-10, None
    for L in (1, 2, 3):
        s0, s1 = t, t[(idx + L - 1) % n]
        p, q = t[(idx - 1) % n], t[(idx + L) % n]
        gain = D[p, s0] + D[s1, q] - D[p, q]
        fwd = D[np.ix_(s0, a)] + D[np.ix_(s1, b)]
        rev = D[np.ix_(s1, a)] + D[np.ix_(s0, b)]
        delta = np.minimum(fwd, rev) - dab[None, :] - gain[:, None]
        for d in range(-1, L):
            delta[idx, (idx + d) % n] = np.inf
        k = int(np.argmin(delta))
        if delta.flat[k] < best:
            best = delta.flat[k]
            i, j = divmod(k, n)
            move = (L, i, j, bool(rev[i, j] < fwd[i, j]))
    if move is None:
        return None
    L, i, j, flip = move
    a_city = t[j]
    t2 = np.roll(t, -i)
    seg, rest = t2[:L], t2[L:]
    pos = int(np.flatnonzero(rest == a_city)[0])
    return np.concatenate([rest[:pos + 1], seg[::-1] if flip else seg, rest[pos + 1:]])


def _local_search(t, D):
    while True:
        t = _two_opt(t, D)
        t2 = _or_opt(t, D)
        if t2 is None:
            return t
        t = t2


def _double_bridge(t, rng):
    n = len(t)
    a, b, c = np.sort(rng.choice(np.arange(1, n), 3, replace=False))
    return np.concatenate([t[:a], t[b:c], t[a:b], t[c:]])


def _length(t, D):
    return float(D[t, np.roll(t, -1)].sum())


def solve(xy, kicks=400, restarts=3, seed=0):
    """Iterated local search (2-opt + or-opt, double-bridge kicks) from a few random starts."""
    D = dist_matrix(xy)
    rng = np.random.default_rng(seed)
    best_t, best_l = None, np.inf
    for _ in range(restarts):
        t = _local_search(rng.permutation(len(xy)), D)
        L = _length(t, D)
        for _ in range(kicks):
            c = _local_search(_double_bridge(t, rng), D)
            cl = _length(c, D)
            if cl < L - 1e-12:
                t, L = c, cl
        if L < best_l - 1e-12:
            best_t, best_l = t, L
    k = int(np.flatnonzero(best_t == 0)[0])                # start the stored tour at city 0
    return np.roll(best_t, -k), best_l


def build_refs(kicks=1000, restarts=1):
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in raw_instances(split):
            seed = int(hashlib.sha1(inst["id"].encode()).hexdigest()[:8], 16)
            tour, L = solve(inst["coords"], kicks, restarts, seed=seed)
            out[inst["id"]] = {"length": round(L, 6), "tour": [int(x) for x in tour], "hash": _hash(inst["coords"])}
            print(f"  {inst['id']:16s} n={len(tour):3d} best {L:.4f}  ({time.time() - t0:.0f}s)", flush=True)
    REFS.parent.mkdir(parents=True, exist_ok=True)
    REFS.write_text(json.dumps({"method": f"iterated 2-opt + or-opt, {restarts} random starts x {kicks} "
                                          "double-bridge kicks", "instances": out}, indent=0))
    print(f"wrote {REFS} ({len(out)} instances, {time.time() - t0:.0f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs", action="store_true", help="rebuild suite/data/tsp_refs.json")
    ap.add_argument("--kicks", type=int, default=1000)
    ap.add_argument("--restarts", type=int, default=1)
    a = ap.parse_args(argv)
    if a.refs:
        build_refs(a.kicks, a.restarts)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
