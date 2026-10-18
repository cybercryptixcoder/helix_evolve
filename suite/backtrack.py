"""Backtrack (open suite): a fixed depth-first solver asks which unassigned variable to branch on next.

The puzzle is invented ("tide pools"): every pool gets a depth 0-3 under channel rules (pairs of pools),
basin totals (irregular groups of 4-6 pools) and a census (how many pools have each depth). Each puzzle is
generated around a hidden planted solution, so it always has one. The solver checks constraints one step ahead
(forward checking) and tries depths in increasing order; the policy only picks the branching order.

Open ceiling (docs/OPEN_SUITE.md): cost = search nodes until the first solution, summed over a ladder of three
puzzles of increasing size (each capped); gap = 100 * cost / Code Zero's cost on the same instance. Code Zero's
costs are cached in suite/data/backtrack_cz.json (rebuild: `python -m suite.backtrack --cz`); an instance missing
from the cache is computed on the spot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
CZ_FILE = ROOT / "suite" / "data" / "backtrack_cz.json"
SPLIT_SEED = {"train": 4111, "valid": 5222, "test": 6333}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
FAMILIES = {"scatter": 1, "strip": 2, "clusters": 3, "hubs": 4}
TRAIN_FAMILIES = ["scatter", "strip", "clusters"]
HELD_OUT = ["hubs"]
SIZES = (30, 55, 85)          # the ladder of puzzle sizes in one instance (each jittered by up to +-2 pools)
CAP_PER_POOL = 15             # a puzzle's node cap = 15 x its number of pools
L = 4                         # depths 0..3
APART, CLOSE = 1, 2           # channel kinds

# ---------------------------------------------------------------------------------------------- tables
MINV = [0] * 16
MAXV = [0] * 16
for _m in range(1, 16):
    _vs = [v for v in range(L) if _m >> v & 1]
    MINV[_m], MAXV[_m] = min(_vs), max(_vs)
DOMBITS = np.array([[(m >> v) & 1 for v in range(L)] for m in range(16)], dtype=bool)
# RANGE[a][b]: bitmask of the depths in [a, b] (0 <= a, b <= 3; empty when a > b)
RANGE = [[sum(1 << v for v in range(a, b + 1)) for b in range(L)] for a in range(L)]
ALLOW = {APART: [sum(1 << b for b in range(L) if b != a) for a in range(L)],
         CLOSE: [sum(1 << b for b in range(L) if abs(a - b) <= 1) for a in range(L)]}


# ---------------------------------------------------------------------------------------------- instances
def _points(family, n, rng):
    if family in ("scatter", "hubs"):
        return rng.random((n, 2))
    if family == "strip":
        return np.c_[rng.random(n) * 6.0, rng.random(n)]
    if family == "clusters":
        centres = rng.random((max(2, n // 10), 2)) * 3.0
        return centres[rng.integers(len(centres), size=n)] + rng.normal(0, 0.25, (n, 2))
    raise KeyError(family)


def make_puzzle(family, n, rng):
    xy = _points(family, n, rng)
    d = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    A = np.zeros((n, n), dtype=bool)
    A[np.repeat(np.arange(n), 2), np.argsort(d, 1)[:, :2].ravel()] = True     # each pool to its 2 nearest
    if family == "hubs":                                                    # a few pools with long channels
        for h in rng.choice(n, max(2, n // 12), replace=False):
            A[h, rng.choice(n, int(rng.integers(6, 11)), replace=False)] = True
        np.fill_diagonal(A, False)
    A = A | A.T
    x = rng.integers(0, L, n)                                               # the planted solution
    kind = np.zeros((n, n), dtype=np.int8)
    for i, j in zip(*np.nonzero(np.triu(A, 1))):
        diff = abs(int(x[i]) - int(x[j]))
        k = CLOSE if diff == 0 else APART if diff >= 2 else (CLOSE if rng.random() < 0.5 else APART)
        kind[i, j] = kind[j, i] = k
    basins = []
    for _ in range(int(round(0.6 * n))):
        c = int(rng.integers(n))
        s = int(rng.integers(4, 7))
        mem = sorted({c, *(int(v) for v in np.argsort(d[c])[: s - 1])})
        basins.append((mem, int(x[mem].sum())))
    perm = rng.permutation(n)                                               # random numbering
    inv = np.argsort(perm)
    kind = kind[np.ix_(perm, perm)]
    basins = [(sorted(int(inv[v]) for v in m), t) for m, t in basins]
    x = x[perm]
    return {"n": n, "kind": kind, "basins": basins, "census": [int(c) for c in np.bincount(x, minlength=L)],
            "planted": x}


def _prepare(p):
    """Solver tables for one puzzle (python lists for speed, numpy arrays for the features)."""
    n, kind = p["n"], p["kind"]
    p["adj"] = [[(int(u), int(kind[v, u])) for u in np.flatnonzero(kind[v])] for v in range(n)]
    B = len(p["basins"])
    mem = np.zeros((n, B), dtype=bool)
    for b, (m, _) in enumerate(p["basins"]):
        mem[m, b] = True
    p["member"] = mem
    p["members"] = [m for m, _ in p["basins"]]
    p["totals"] = [t for _, t in p["basins"]]
    p["vb"] = [[int(b) for b in np.flatnonzero(mem[v])] for v in range(n)]
    p["n_links"] = (kind > 0).sum(1)
    p["cap"] = CAP_PER_POOL * n
    return p


def _fingerprint(inst):
    h = hashlib.sha1()
    for p in inst["puzzles"]:
        h.update(p["kind"].tobytes())
        h.update(json.dumps([p["basins"], p["census"], p["seed"]]).encode())
    return h.hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code = FAMILIES[fam]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            puzzles = []
            for j, size in enumerate(SIZES):
                n = size + int(rng.integers(-2, 3))
                p = make_puzzle(fam, n, rng)
                p["seed"] = [SPLIT_SEED[split], code, i, j]
                puzzles.append(_prepare(p))
            inst = {"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "puzzles": puzzles}
            inst["fingerprint"] = _fingerprint(inst)
            out.append(inst)
    return out


# ---------------------------------------------------------------------------------------------- solver
def solve(p, priority, stats=None):
    """Depth-first search with forward checking; the policy picks the branching variable. Returns nodes used."""
    n, adj, vb, members = p["n"], p["adj"], p["vb"], p["members"]
    link_kind, member, n_links = p["kind"], p["member"], p["n_links"]
    cap = p["cap"]
    rng = np.random.default_rng(p["seed"])
    rem = list(p["totals"])
    need = list(p["census"])
    val = [-1] * n
    alink = [0] * n                      # channels to pools that have a depth
    wipe = [0] * n
    open_b = [len(m) for m in members]
    nodes = [0]
    fails = [0]

    def assign(v, a, dom):
        val[v] = a
        dom[v] = 1 << a
        for b in vb[v]:
            rem[b] -= a
            open_b[b] -= 1
        need[a] -= 1
        for u, _ in adj[v]:
            alink[u] += 1
        for u, k in adj[v]:
            if val[u] < 0:
                du = dom[u] & ALLOW[k][a]
                if not du:
                    wipe[u] += 1
                    return False
                dom[u] = du
        for b in vb[v]:
            r = rem[b]
            un = [u for u in members[b] if val[u] < 0]
            if not un:
                if r != 0:
                    wipe[v] += 1
                    return False
                continue
            lo = hi = 0
            for u in un:
                lo += MINV[dom[u]]
                hi += MAXV[dom[u]]
            for u in un:
                du = dom[u]
                a0 = r - hi + MAXV[du]           # smallest depth u may take
                a1 = r - lo + MINV[du]           # largest depth u may take
                m = du & RANGE[a0 if a0 > 0 else 0][a1 if a1 < 3 else 3] if a0 <= 3 and a1 >= 0 else 0
                if not m:
                    wipe[u] += 1
                    return False
                dom[u] = m
        if need[a] == 0:
            drop = ~(1 << a)
            for u in range(n):
                if val[u] < 0:
                    du = dom[u] & drop
                    if not du:
                        wipe[u] += 1
                        return False
                    dom[u] = du
        return True

    def unassign(v, a):
        val[v] = -1
        for b in vb[v]:
            rem[b] += a
            open_b[b] += 1
        need[a] += 1
        for u, _ in adj[v]:
            alink[u] -= 1

    def choose(dom, depth):
        un = np.flatnonzero(np.asarray(val) < 0)
        k = len(un)
        if k == 1:
            return int(un[0])
        cand = un[rng.permutation(k)]
        d = np.asarray(dom)[cand]
        args = (DOMBITS[d], link_kind[np.ix_(cand, cand)], np.asarray(alink)[cand], member[cand],
                np.array(open_b), np.array(rem), np.asarray(wipe)[cand], np.array(need), depth)
        s = np.asarray(priority(*args), dtype=float)
        if s.shape != (k,):
            raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
        return int(cand[int(np.argmax(np.round(s, 9)))])

    def dfs(dom, depth):
        if depth == n:
            return True
        v = choose(dom, depth)
        d = dom[v]
        for a in range(L):
            if not d >> a & 1:
                continue
            if nodes[0] >= cap:
                return False
            nodes[0] += 1
            nd = list(dom)
            ok = assign(v, a, nd)
            if ok and dfs(nd, depth + 1):
                return True
            if not ok:
                fails[0] += 1
            unassign(v, a)
        return False

    solved = dfs([15] * n, 0)
    if stats is not None:
        stats.update(solved=solved, fails=fails[0], val=list(val) if solved else None)
    return nodes[0] if solved else cap


def check_solution(p, val):
    x = np.asarray(val)
    kind = p["kind"]
    i, j = np.nonzero(np.triu(kind > 0, 1))
    diff = np.abs(x[i] - x[j])
    if ((kind[i, j] == APART) & (diff == 0)).any() or ((kind[i, j] == CLOSE) & (diff > 1)).any():
        return False
    if any(int(x[m].sum()) != t for m, t in p["basins"]):
        return False
    return [int(c) for c in np.bincount(x, minlength=L)] == p["census"]


def _zero(*args):
    return np.zeros(len(args[0]))


# ---------------------------------------------------------------------------------------------- the problem
class Backtrack(Problem):
    name = "backtrack"
    title = "Backtrack: choose the branching order of a fixed depth-first solver"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth)"
    candidates_arg = 0
    description = f"""An invented logic puzzle, "tide pools", solved by a fixed backtracking search. The policy only decides the order in which the search branches; the cost is how much searching it takes.

**The puzzle.** There are n pools; each must get a depth 0, 1, 2 or 3. Three kinds of rules:
- *Channels*: some pairs of pools are joined by a channel. An `apart` channel requires the two depths to differ; a `close` channel requires them to differ by at most 1.
- *Basins*: irregular groups of 4 to 6 pools, each with a total; the depths in a basin must add up to exactly its total. A pool can be in several basins or none.
- *Census*: for each depth, exactly how many pools must have it.
Every puzzle was generated around a hidden solution, so at least one solution exists (there may be more; any one counts).

**The solver (fixed).** Depth-first search. Each unassigned pool keeps a *domain*: the depths still possible for it (initially all four). At every node of the search, if all pools have a depth the puzzle is solved. Otherwise the policy chooses one unassigned pool (if only one is left it is taken automatically), and the solver tries that pool's domain values in increasing order. Each try is one **node**: the pool gets the depth, then the solver checks one step ahead: (1) every channel partner without a depth loses the depths its channel forbids; (2) in each basin of the pool, every member without a depth keeps only depths that leave the basin's remaining total reachable, given the smallest and largest depths still possible for the other members (one pass, using the domains as they were before this pass); a basin whose members all have depths must match its total exactly; (3) if a depth's census count is now reached, that depth is removed from every unassigned pool. If any domain becomes empty (a *wipeout*) or a full basin misses its total, the try fails and the next depth is tried; otherwise the search goes one level deeper with the reduced domains. When every depth of the chosen pool has failed, the search backs up to the previous choice. Domains are restored when the search backs up.

**One decision** = choosing the next pool to branch on. The **candidates** are all unassigned pools, in a random order (pools are also numbered at random, so neither order carries information). There is one decision at the start of the search and one after every node that passes its check (while two or more pools are unassigned).

**Instances and cost.** An instance is a ladder of three puzzles from one family, with about {SIZES[0]}, {SIZES[1]} and {SIZES[2]} pools. A puzzle's cost is the number of nodes until its first solution, capped at {CAP_PER_POOL} x its number of pools (an unsolved puzzle costs the cap). The instance's cost is the sum over its three puzzles, so the largest puzzle weighs most and how the search effort grows with size matters. The **gap** of an instance is 100 x its cost / the cost of Code Zero (the policy that always takes the first candidate, i.e. a random pool) on the same instance: Code Zero scores 100, lower is better, and 0 is impossible (a puzzle needs at least one node per pool). There is no known best.

Three training families, differing in how pools are placed and channels drawn (each pool is joined to its two nearest pools): `scatter` (pools spread uniformly over a square), `strip` (a long thin strip), `clusters` (tight clumps of pools). Basins are a pool and its nearest neighbours. The test split adds a family that training never shows."""
    signature_doc = """All per-candidate arrays have the candidates on the first axis (k = number of unassigned pools, in the decision's random order).
- `domain`: shape (k, 4), bool: which depths (columns 0..3) are still possible for each candidate. Its row sum is the domain size (at least 1).
- `links`: shape (k, k), int8: the channels between candidates: 0 = no channel, 1 = `apart`, 2 = `close` (symmetric, 0 on the diagonal).
- `assigned_links`: shape (k,), int: how many of each candidate's channels lead to pools that already have a depth.
- `basins`: shape (k, B), bool: which basins each candidate belongs to (B = number of basins in the puzzle, fixed per puzzle; a row can be all False).
- `basin_open`: shape (B,), int: how many members of each basin have no depth yet (candidates are exactly the pools without a depth).
- `basin_rest`: shape (B,), int: each basin's total minus the depths already set in it (what its open members must still add up to).
- `wipeouts`: shape (k,), int: how many times during this search so far a check emptied this candidate's domain, or completed one of its basins with the wrong total (counts never reset on backtracking).
- `census_left`: shape (4,), int: how many more pools must get each depth.
- `depth`: int: how many pools have a depth at this node (the puzzle has n = k + depth pools).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is branched on next."""
    metric_notes = {
        "cost": "search nodes summed over the instance's three puzzles (each capped): the instance's cost",
        "nodes_small": "search nodes on the instance's smallest puzzle (capped)",
        "nodes_large": "search nodes on the instance's largest puzzle (capped)",
        "growth": "growth exponent of the effort with size: log(nodes_large / nodes_small) / log(pools_large / pools_small); 1 = linear",
        "capped": "puzzles of the instance not solved within their node cap (0-3)",
        "fail_pct": "% of nodes whose one-step check failed (a wipeout or a missed basin total)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):\n"
        "    \"\"\"Minus the domain size.\"\"\"\n"
        "    return -domain.sum(axis=1).astype(float)\n",
        "import numpy as np\n\ndef feature(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):\n"
        "    \"\"\"Channels to other unassigned pools.\"\"\"\n"
        "    return (links > 0).sum(axis=1).astype(float)\n",
        "import numpy as np\n\ndef feature(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):\n"
        "    \"\"\"Number of basins the pool is in.\"\"\"\n"
        "    return basins.sum(axis=1).astype(float)\n",
    ]

    def __init__(self):
        self._cache = {}
        self._cz = None

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            self._cache[split] = raw_instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    # -------------------------------------------------------------- Code Zero's cost (cached)
    def cz_cost(self, inst):
        if self._cz is None:
            try:
                self._cz = json.loads(CZ_FILE.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                self._cz = {}
        key = f"{inst['split']}/{inst['id']}"
        r = self._cz.get(key)
        if r is None or r.get("fingerprint") != inst["fingerprint"]:
            r = {"fingerprint": inst["fingerprint"], "cost": sum(solve(p, _zero) for p in inst["puzzles"])}
            self._cz[key] = r
        return r["cost"]

    # -------------------------------------------------------------- scoring
    def run(self, instance, priority):
        cost = sum(solve(p, priority) for p in instance["puzzles"])
        return {"gap": 100.0 * (cost / self.cz_cost(instance)), "cost": cost}

    def diagnose(self, instance, priority):
        nodes, st = [], []
        for p in instance["puzzles"]:
            s = {}
            nodes.append(solve(p, priority, s))
            st.append(s)
        cost = sum(nodes)
        ns, nl = instance["puzzles"][0]["n"], instance["puzzles"][-1]["n"]
        return {
            "gap": round(100.0 * (cost / self.cz_cost(instance)), 3),
            "cost": cost,
            "nodes_small": nodes[0],
            "nodes_large": nodes[-1],
            "growth": round(math.log(nodes[-1] / nodes[0]) / math.log(nl / ns), 3),
            "capped": sum(not s["solved"] for s in st),
            "fail_pct": round(100.0 * sum(s["fails"] for s in st) / max(1, cost), 2),
        }


# ---------------------------------------------------------------------------------------------- cache
def build_cz():
    p = Backtrack()
    p._cz = {}
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in p.instances(split):
            costs = []
            for pz in inst["puzzles"]:
                s = {}
                costs.append(solve(pz, _zero, s))
                if s["solved"]:
                    assert check_solution(pz, s["val"]), inst["id"]
                assert check_solution(pz, pz["planted"]), inst["id"]
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "cost": int(sum(costs)),
                                            "puzzles": costs, "sizes": [pz["n"] for pz in inst["puzzles"]]}
            print(f"  {split:5s} {inst['id']:14s} sizes {[pz['n'] for pz in inst['puzzles']]} Code Zero nodes {costs}")
    CZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CZ_FILE.write_text(json.dumps({"method": "Code Zero (first candidate of the shuffled list) search nodes per instance",
                                   "instances": out}, indent=0))
    print(f"wrote {CZ_FILE} ({len(out)} instances, {time.time() - t0:.1f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cz", action="store_true", help="rebuild suite/data/backtrack_cz.json")
    a = ap.parse_args(argv)
    if a.cz:
        build_cz()
    else:
        ap.print_help()


if __name__ == "__main__":
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 2000))
    main()
