"""Greedy graph colouring: the policy picks which vertex to colour next.

At each decision the candidates are the uncoloured vertices (index order); the chosen vertex gets the
smallest colour not used by any of its coloured neighbours. The gap is colours used over the best colouring
known for the instance: the planted k for planted graphs, otherwise the best of many randomised greedy
orderings followed by a tabu search (TabuCol) that keeps trying one colour fewer. References are cached in
suite/data/coloring_refs.json and rebuilt with `python -m suite.coloring --refs`.
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
REFS = ROOT / "suite" / "data" / "coloring_refs.json"
SPLIT_SEED = {"train": 7101, "valid": 8202, "test": 9303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family: (seed code, vertices, parameter)
FAMILIES = {"sparse": (1, 120, 0.08), "dense": (2, 70, 0.5), "geometric": (3, 100, 0.2),
            "planted": (4, 100, (6, 0.35)), "medium": (5, 120, 0.25)}
TRAIN_FAMILIES = ["sparse", "dense", "geometric", "planted"]
HELD_OUT = ["medium"]


# ---------------------------------------------------------------------------------------------- instances
def make_graph(family, rng):
    """(adjacency (n, n) bool, planted number of colours or None)."""
    code, n, par = FAMILIES[family]
    planted = None
    if family in ("sparse", "dense", "medium"):
        A = rng.random((n, n)) < par
    elif family == "geometric":
        xy = rng.random((n, 2))
        A = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1) < par ** 2
    elif family == "planted":
        k, p = par
        cls = rng.permutation(np.arange(n) % k)
        A = (rng.random((n, n)) < p) & (cls[:, None] != cls[None, :])
        planted = k
    else:
        raise KeyError(family)
    A = np.triu(A, 1)
    A = A | A.T
    perm = rng.permutation(n)                                # random numbering: index order means nothing
    return A[np.ix_(perm, perm)], planted


def _hash(A):
    return hashlib.sha1(np.packbits(A).tobytes()).hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code = FAMILIES[fam][0]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            A, planted = make_graph(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "adj": A, "planted": planted})
    return out


# ---------------------------------------------------------------------------------------------- greedy
def greedy(A, order):
    """Colour vertices in `order`, each with the smallest colour free among its coloured neighbours."""
    n = len(A)
    col = np.full(n, -1, dtype=np.int64)
    used = np.zeros((n, n + 1), dtype=bool)
    for v in order:
        c = int(np.argmin(used[v]))
        col[v] = c
        used[A[v], c] = True
    return col


def coloring_metrics(A, col, ref, order=None):
    k = int(col.max()) + 1
    sizes = np.bincount(col, minlength=k)
    deg = A.sum(1)
    # Kempe-free check: vertices whose colour could be lowered (a free smaller colour exists now)
    used = np.zeros((len(A), k), dtype=bool)
    for c in range(k):
        used[:, c] = (A & (col == c)[None, :]).any(1)
    lowerable = int(sum(1 for v in range(len(A)) if col[v] > 0 and not used[v, :col[v]].all()))
    out = {
        "gap": round(100 * (k / ref - 1), 3),
        "colors": k,
        "largest_class_pct": round(100 * float(sizes.max()) / len(A), 2),
        "smallest_class": int(sizes.min()),
        "singleton_classes": int((sizes == 1).sum()),
        "lowerable_vertices": lowerable,
    }
    if order is not None:
        order = np.asarray(order)
        first_top = int(np.flatnonzero(col[order] == k - 1)[0])
        out["last_color_at_pct"] = round(100 * first_top / len(A), 1)
        out["deg_rank_corr"] = round(float(np.corrcoef(deg[order], -np.arange(len(A)))[0, 1]), 3) if deg.std() > 0 else 0.0
    return out


# ---------------------------------------------------------------------------------------------- the problem
def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


class GraphColoring(Problem):
    name = "coloring"
    title = "Graph colouring: choose the order to colour vertices"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    signature = "feature(neighbor_colors, adjacency, degree, color_sizes)"
    candidates_arg = 0
    description = """Colour every vertex of a graph so that no two adjacent vertices share a colour, using as few colours as possible.

The colouring is built one vertex at a time. At each step the policy picks which uncoloured vertex to colour next; that vertex then automatically gets the smallest colour (colours are numbered 0, 1, 2, ...) not already used by one of its coloured neighbours. A new colour is opened only when every existing colour is taken by some neighbour. So the policy decides only the **order**, and the order decides how many colours are needed.

One **decision** = choosing the next vertex. The **candidates** are all uncoloured vertices, in index order. Vertices are numbered at random, so the index carries no information. When one vertex is left it is taken automatically.

Four training families: `sparse` (random graphs, 120 vertices, each pair joined with probability 0.08), `dense` (random, 70 vertices, probability 0.5), `geometric` (100 random points in the unit square, joined when closer than 0.2) and `planted` (100 vertices secretly split into 6 groups; pairs in different groups are joined with probability 0.35, pairs in the same group never, so 6 colours suffice). The test split adds a family that training never shows. The **gap** of an instance is colours used / the fewest colours known for that graph - 1, in % (for `planted`, the known 6 or fewer). Colour counts are small integers, so one colour more or less moves an instance's gap by roughly 10-25%."""
    signature_doc = """- `neighbor_colors`: shape (k, c), int: for each candidate (uncoloured vertex, index order) and each colour used so far, how many of its neighbours already have that colour. c = number of colours used so far (c = 0 at the first decision: the array has shape (k, 0)). The colour a candidate would get is the first column that is 0 in its row, or c (a new colour) if none is.
- `adjacency`: shape (k, k), bool: which candidates are adjacent to each other (the graph restricted to the uncoloured vertices; symmetric, False on the diagonal).
- `degree`: shape (k,), int: each candidate's degree in the whole graph (coloured + uncoloured neighbours).
- `color_sizes`: shape (c,), int: how many vertices have each colour so far.
- The whole graph has n = k + color_sizes.sum() vertices.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c')). The highest-scoring candidate is coloured next."""
    metric_notes = {
        "colors": "colours used",
        "largest_class_pct": "% of vertices in the largest colour class",
        "smallest_class": "size of the smallest colour class",
        "singleton_classes": "colour classes with a single vertex",
        "lowerable_vertices": "vertices that could now take a smaller colour (their earlier choice became suboptimal)",
        "last_color_at_pct": "how far into the order (%) the highest colour was first opened",
        "deg_rank_corr": "correlation between a vertex's degree and how early it was coloured (+1 = high degree first)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(neighbor_colors, adjacency, degree, color_sizes):\n"
        "    \"\"\"Degree in the whole graph.\"\"\"\n"
        "    return degree.astype(float)\n",
        "import numpy as np\n\ndef feature(neighbor_colors, adjacency, degree, color_sizes):\n"
        "    \"\"\"Minus the number of uncoloured neighbours.\"\"\"\n"
        "    return -adjacency.sum(axis=1).astype(float)\n",
    ]

    def __init__(self):
        self._cache = {}
        self._refs = None

    def refs(self):
        if self._refs is None:
            try:
                self._refs = json.loads(REFS.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                raise RuntimeError(f"missing {REFS.relative_to(ROOT)}: run `python -m suite.coloring --refs`")
        return self._refs

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            refs = self.refs()
            out = raw_instances(split)
            for inst in out:
                r = refs.get(inst["id"])
                if r is None or r["hash"] != _hash(inst["adj"]):
                    raise RuntimeError(f"coloring reference for {inst['id']} is missing or stale: "
                                       "run `python -m suite.coloring --refs`")
                inst["ref"] = int(r["colors"])
                inst["degree"] = inst["adj"].sum(1).astype(np.int64)
            self._cache[split] = out
        return self._cache[split]

    def build(self, instance, priority):
        A, deg = instance["adj"], instance["degree"]
        n = len(A)
        nc = np.zeros((n, n + 1), dtype=np.int64)            # neighbour colour counts
        col = np.full(n, -1, dtype=np.int64)
        uncol = np.ones(n, dtype=bool)
        sizes = np.zeros(n + 1, dtype=np.int64)
        order = np.empty(n, dtype=np.int64)
        c_used = 0
        for step in range(n):
            cand = np.flatnonzero(uncol)
            k = len(cand)
            if k == 1:
                i = 0
            else:
                args = (nc[cand, :c_used], A[np.ix_(cand, cand)], deg[cand], sizes[:c_used].copy())
                i = _choose(priority, args, k)
            v = cand[i]
            c = int(np.argmin(nc[v, :c_used + 1] > 0))
            col[v] = c
            sizes[c] += 1
            c_used = max(c_used, c + 1)
            nc[A[v], c] += 1
            uncol[v] = False
            order[step] = v
        return col, order

    def run(self, instance, priority):
        col, _ = self.build(instance, priority)
        k = int(col.max()) + 1
        return {"gap": 100.0 * (k / instance["ref"] - 1.0), "colors": k}

    def n_candidates(self, args):
        return len(args[0])

    def diagnose(self, instance, priority):
        col, order = self.build(instance, priority)
        return coloring_metrics(instance["adj"], col, instance["ref"], order)

    def reference_metrics(self, instance):
        r = self.refs().get(instance["id"])
        if not r:
            return {}
        return coloring_metrics(instance["adj"], np.asarray(r["coloring"]), instance["ref"])


# ---------------------------------------------------------------------------------------------- references
def tabucol(A, k, init, rng, iters):
    """Tabu search for a proper k-colouring, starting from `init` (colours >= k are re-drawn)."""
    n = len(A)
    Ai = A.astype(np.int32)
    col = init.copy()
    bad = col >= k
    col[bad] = rng.integers(0, k, int(bad.sum()))
    G = Ai @ np.eye(k, dtype=np.int32)[col]                 # G[v, c]: neighbours of v with colour c
    ar = np.arange(n)
    conf = G[ar, col]
    f = int(conf.sum()) // 2
    best_f = f
    tabu = np.zeros((n, k), dtype=np.int64)
    BIG = 1 << 30
    for it in range(iters):
        if f == 0:
            return col
        delta = G - conf[:, None]
        delta[ar, col] = BIG
        delta[conf == 0] = BIG
        ok = (tabu <= it) | (f + delta < best_f)
        d = np.where(ok, delta, BIG)
        m = d.min()
        if m >= BIG:
            continue
        cand = np.flatnonzero(d.ravel() == m)
        v, c = divmod(int(cand[rng.integers(len(cand))]), k)
        old = col[v]
        nb = A[v]
        G[nb, old] -= 1
        G[nb, c] += 1
        col[v] = c
        conf = G[ar, col]
        f += int(m)
        best_f = min(best_f, f)
        tabu[v, old] = it + 1 + int(0.6 * np.count_nonzero(conf)) + int(rng.integers(0, 10))
    return col if f == 0 else None


def solve(A, planted, seed, orders=300, iters=20000):
    rng = np.random.default_rng(seed)
    n = len(A)
    best = None
    for _ in range(orders):
        col = greedy(A, rng.permutation(n))
        if best is None or col.max() < best.max():
            best = col
    while best.max() + 1 > 2:
        k = int(best.max())                                  # try one colour fewer
        if planted is not None and k < planted:
            break
        col = tabucol(A, k, best, rng, iters)
        if col is None:
            break
        best = col
    return best


def clique_bound(A, seed, tries=300):
    """Size of the largest clique found by randomised greedy search: a lower bound on the colours needed."""
    rng = np.random.default_rng(seed)
    best = 0
    for _ in range(tries):
        size, cand = 0, np.ones(len(A), dtype=bool)
        while cand.any():
            idx = np.flatnonzero(cand)
            v = idx[rng.integers(len(idx))] if rng.random() < 0.3 else idx[np.argmax(A[np.ix_(idx, idx)].sum(1))]
            size += 1
            cand &= A[v]
        best = max(best, size)
    return best


def _proper(A, col):
    return not (A & (col[:, None] == col[None, :])).any()


def build_refs(orders=300, iters=20000):
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in raw_instances(split):
            seed = int(hashlib.sha1(inst["id"].encode()).hexdigest()[:8], 16)
            col = solve(inst["adj"], inst["planted"], seed, orders, iters)
            assert _proper(inst["adj"], col)
            k = int(col.max()) + 1
            lb = clique_bound(inst["adj"], seed)
            out[inst["id"]] = {"colors": k, "clique_lower_bound": lb, "coloring": [int(x) for x in col],
                               "hash": _hash(inst["adj"]), "planted": inst["planted"]}
            print(f"  {inst['id']:16s} n={len(col):3d} best {k}, clique {lb}"
                  + (f" (planted {inst['planted']})" if inst["planted"] else "") + f"  ({time.time() - t0:.0f}s)", flush=True)
    REFS.parent.mkdir(parents=True, exist_ok=True)
    REFS.write_text(json.dumps({"method": f"best of {orders} random greedy orders, then TabuCol ({iters} iterations per "
                                          "colour count) trying one colour fewer until it fails; planted k caps it",
                                "instances": out}, indent=0))
    print(f"wrote {REFS} ({len(out)} instances, {time.time() - t0:.0f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs", action="store_true", help="rebuild suite/data/coloring_refs.json")
    ap.add_argument("--orders", type=int, default=300)
    ap.add_argument("--iters", type=int, default=20000)
    a = ap.parse_args(argv)
    if a.refs:
        build_refs(a.orders, a.iters)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
