"""Weighted set cover, built one set at a time.

At each decision the candidates are the sets that cover at least one still-uncovered element (index order); the
chosen set is added; the build stops when every element is covered. No redundancy removal afterwards: the policy
alone decides. The reference is the optimum from an integer program (scipy.optimize.milp / HiGHS), cached in
suite/data/setcover_refs.json (rebuild: python -m suite.setcover --refs). The instances are sized so HiGHS proves
optimality on every one; if an instance ever isn't proven optimal, the cache keeps the best cover found and its
dual bound, and floor() reports the (negative) bound gap for that family.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
REFS_FILE = ROOT / "suite" / "data" / "setcover_refs.json"
TIME_LIMIT = 300.0
# split -> (seed, instances per family)
SPLITS = {"train": (31, 3), "valid": (32, 3), "test": (33, 3)}

# family -> (largest set as a fraction of the elements, cost model, rare elements?)
FAMILIES = {
    "unicost": (0.04, "unit", False),
    "random_cost": (0.08, "random", False),
    "size_cost": (0.04, "size", False),
    "rare_elements": (0.08, "random", True),
    "big_sets": (0.15, "random", False),          # held out
}


def make_instance(family, seed, index):
    frac, cost_model, rare = FAMILIES[family]
    rng = np.random.default_rng([seed, list(FAMILIES).index(family), index])
    m = int(rng.integers(100, 201))                    # elements
    n = int(rng.integers(200, 401))                    # sets
    hi = max(4, int(round(frac * m)))
    is_rare = np.zeros(m, dtype=bool)
    if rare:
        is_rare[rng.choice(m, m // 5, replace=False)] = True
    common = np.flatnonzero(~is_rare)
    A = np.zeros((n, m), dtype=bool)
    sizes = rng.integers(2, hi + 1, n)
    for j in range(n):
        A[j, rng.choice(common, min(int(sizes[j]), len(common)), replace=False)] = True
    for e in range(m):                                 # every element in >= 2 sets (rare ones: 1 or 2)
        need = (int(rng.integers(1, 3)) if is_rare[e] else 2) - int(A[:, e].sum())
        if need > 0:
            A[rng.choice(np.flatnonzero(~A[:, e]), need, replace=False), e] = True
    sz = A.sum(axis=1)
    if cost_model == "unit":
        costs = np.ones(n, dtype=np.int64)
    elif cost_model == "random":
        costs = rng.integers(1, 101, n)
    else:                                              # roughly proportional to size, ±40%
        costs = np.maximum(1, np.rint(10 * sz * rng.uniform(0.6, 1.4, n)))
    sets = [np.flatnonzero(A[j]).tolist() for j in range(n)]
    costs = np.asarray(costs, dtype=np.int64).tolist()
    fp = hashlib.sha1(json.dumps([m, sets, costs]).encode()).hexdigest()[:16]
    return {"id": f"{family}-{index:03d}", "family": family, "n_elements": m, "sets": sets, "costs": costs,
            "fingerprint": fp, "_A": A}


def solve_ilp(inst, time_limit=TIME_LIMIT):
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csr_matrix
    A, c = inst["_A"], np.asarray(inst["costs"], dtype=float)
    t = time.time()
    r = milp(c, constraints=LinearConstraint(csr_matrix(A.T.astype(float)), lb=1, ub=np.inf),
             integrality=np.ones(len(c)), bounds=Bounds(0, 1), options={"time_limit": time_limit, "disp": False})
    if r.x is None:
        raise RuntimeError(f"{inst['id']}: no cover found ({r.message})")
    chosen = np.flatnonzero(r.x > 0.5).tolist()
    assert A[chosen].any(axis=0).all()
    cost = int(sum(inst["costs"][j] for j in chosen))
    bound = float(getattr(r, "mip_dual_bound", cost) or cost)
    return {"fingerprint": inst["fingerprint"], "cost": cost, "sets": chosen, "optimal": bool(r.status == 0),
            "bound": round(bound, 6) if r.status != 0 else cost, "seconds": round(time.time() - t, 2)}


def _load_refs():
    try:
        return json.loads(REFS_FILE.read_text())["instances"]
    except (OSError, ValueError, KeyError):
        return {}


def cover_metrics(inst, chosen, ref_cost):
    """Order-free metrics of a cover (chosen = set indices)."""
    A = inst["_A"]
    costs = np.asarray(inst["costs"], dtype=float)
    chosen = np.asarray(chosen, dtype=int)
    cost = float(costs[chosen].sum())
    hits = A[chosen].sum(axis=0)                       # how many chosen sets cover each element
    redundant = int(sum(1 for j in chosen if (hits[A[j]] >= 2).all()))
    ref = set(inst["ref_sets"])
    return {
        "gap": round(100.0 * (cost / ref_cost - 1), 4),
        "cost": int(cost),
        "sets_used": int(len(chosen)),
        "mean_set_cost": round(cost / max(1, len(chosen)), 3),
        "mean_set_size": round(float(A[chosen].sum(axis=1).mean()), 3),
        "covered_twice_pct": round(100 * float((hits >= 2).mean()), 1),
        "redundant_sets": redundant,
        "shared_with_reference_pct": round(100 * len(ref.intersection(chosen.tolist())) / max(1, len(ref)), 1),
    }


class SetCover(Problem):
    name = "setcover"
    title = "Weighted set cover, built set by set"
    families = ["unicost", "random_cost", "size_cost", "rare_elements"]
    held_out_families = ["big_sets"]
    signature = "feature(costs, new_cover, sizes, covers, total)"
    candidates_arg = 0
    description = """There is a universe of elements and a collection of sets, each a subset of the elements with a positive integer cost. A **cover** is a choice of sets whose union is the whole universe; the goal is the cheapest cover.

The cover is built one set at a time. One **decision** = choosing the next set to add; the **candidates** are all sets that contain at least one element not yet covered, in their original index order (so every set touching an uncovered element is a candidate). The chosen set is added for good, and the build stops when every element is covered. Nothing is removed afterwards, so a set made unnecessary by later choices still counts.

Four training families, 100-200 elements and 200-400 sets each, every element in at least two sets: `unicost` (every set costs 1; sets of 2 up to ~4% of the elements), `random_cost` (costs 1-100 independent of the set; sets up to ~8%), `size_cost` (cost about 10 × the set's size, ±40%; sets up to ~4%), `rare_elements` (random costs; a fifth of the elements lie in only one or two sets). Other families exist in testing. The **gap** of an instance is cost ÷ the optimal cost (from an integer program) − 1, in %."""
    signature_doc = """- `costs`: shape (k,), int: the cost of every candidate set, in index order.
- `new_cover`: shape (k,), int: how many still-uncovered elements each candidate contains (≥ 1).
- `sizes`: shape (k,), int: each candidate's full size (covered elements included).
- `covers`: shape (k, u), bool: `covers[i, e]` is True when candidate i contains uncovered element e; the u columns are all the still-uncovered elements, in index order (u = `covers.shape[1]`).
- `total`: int: the number of elements in the universe (it differs between instances: normalise by it).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)), roughly in [-1, 1]."""
    metric_notes = {
        "cost": "total cost of the cover",
        "sets_used": "number of sets in the cover",
        "mean_set_cost": "average cost of a chosen set",
        "mean_set_size": "average size of a chosen set",
        "covered_twice_pct": "% of elements covered by two or more chosen sets",
        "redundant_sets": "chosen sets whose every element is also covered by another chosen set",
        "shared_with_reference_pct": "% of the optimal cover's sets that this cover also chose",
        "one_new_picks": "picks that covered exactly one new element",
        "one_new_cost_pct": "% of the total cost spent on picks that covered exactly one new element",
        "late_cost_pct": "% of the total cost spent on the picks made after 90% of the elements were covered",
    }
    example_features = [
        "import numpy as np\n\ndef feature(costs, new_cover, sizes, covers, total):\n    \"\"\"Minus the cost, relative to the most expensive candidate.\"\"\"\n    return -costs / max(1.0, float(costs.max()))\n",
        "import numpy as np\n\ndef feature(costs, new_cover, sizes, covers, total):\n    \"\"\"Share of the universe the candidate contains (two columns: full size, new elements).\"\"\"\n    return np.stack([sizes / total, new_cover / total], axis=1)\n",
    ]

    def __init__(self):
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLITS:
                raise KeyError(split)
            seed, per = SPLITS[split]
            fams = self.families + (self.held_out_families if split == "test" else [])
            insts = [make_instance(f, seed, i) for f in fams for i in range(per)]
            refs = _load_refs()
            missing = []
            for inst in insts:
                ref = refs.get(f"{split}/{inst['id']}")
                if not ref or ref.get("fingerprint") != inst["fingerprint"]:
                    missing.append(inst["id"])
                    ref = solve_ilp(inst, time_limit=30.0)
                inst["ref_cost"], inst["ref_sets"] = int(ref["cost"]), list(ref["sets"])
                inst["ref_bound"], inst["ref_optimal"] = float(ref["bound"]), bool(ref["optimal"])
            if missing:
                print(f"setcover: {len(missing)} {split} references not cached, solved now; "
                      f"run python -m suite.setcover --refs", file=sys.stderr)
            self._cache[split] = insts
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    def floor(self, family, split="train"):
        insts = [i for i in self.instances(split) if i["family"] == family]
        if not insts:
            return 0.0
        return float(np.mean([min(0.0, 100 * (i["ref_bound"] / i["ref_cost"] - 1)) for i in insts]))

    def _build(self, inst, priority):
        A = inst["_A"]
        AT = inst.get("_AT")
        if AT is None:
            AT = inst["_AT"] = np.ascontiguousarray(A.T).astype(np.int64)   # (elements, sets)
        costs = np.asarray(inst["costs"], dtype=np.int64)
        sizes = A.sum(axis=1).astype(np.int64)
        m = int(inst["n_elements"])
        unc = np.ones(m, dtype=bool)
        new = sizes.copy()
        order, gains = [], []
        n_unc = m
        while n_unc:
            cand = np.flatnonzero(new > 0)
            cov = A[cand][:, unc]
            scores = np.asarray(priority(costs[cand].copy(), new[cand].copy(), sizes[cand].copy(), cov, m), dtype=float)
            if scores.shape != (len(cand),):
                raise ValueError(f"priority returned shape {scores.shape}, expected ({len(cand)},)")
            if not np.all(np.isfinite(scores)):
                raise ValueError(f"priority returned NaN or infinity: {scores.tolist()[:10]}")
            j = int(cand[int(np.argmax(np.round(scores, 9)))])
            newly = A[j] & unc
            g = int(new[j])
            order.append(j)
            gains.append((g, m - n_unc))
            unc &= ~newly
            n_unc -= g
            new -= AT[newly].sum(axis=0)
        # plain-Python check: every element covered
        covered = set()
        for j in order:
            covered.update(inst["sets"][j])
        if len(covered) != m or len(set(order)) != len(order):
            raise ValueError("invalid cover")
        return order, gains, sum(inst["costs"][j] for j in order)

    def run(self, instance, priority):
        _, _, cost = self._build(instance, priority)
        return {"gap": 100.0 * (cost / instance["ref_cost"] - 1), "cost": int(cost)}

    def diagnose(self, instance, priority):
        order, gains, cost = self._build(instance, priority)
        m = cover_metrics(instance, order, instance["ref_cost"])
        costs = instance["costs"]
        n_el = instance["n_elements"]
        one = [j for j, (g, _) in zip(order, gains) if g == 1]
        late = [j for j, (_, done) in zip(order, gains) if done >= 0.9 * n_el]
        m["one_new_picks"] = len(one)
        m["one_new_cost_pct"] = round(100 * sum(costs[j] for j in one) / cost, 1)
        m["late_cost_pct"] = round(100 * sum(costs[j] for j in late) / cost, 1)
        return m

    def reference_metrics(self, instance):
        return cover_metrics(instance, instance["ref_sets"], instance["ref_cost"])


def build_refs(splits=None, time_limit=TIME_LIMIT):
    p = SetCover()
    p.instances = lambda split: [make_instance(f, SPLITS[split][0], i)        # skip the on-the-spot solving
                                 for f in p.families + (p.held_out_families if split == "test" else [])
                                 for i in range(SPLITS[split][1])]
    old = _load_refs()
    out = {}
    for split in splits or SPLITS:
        for inst in p.instances(split):
            key = f"{split}/{inst['id']}"
            if old.get(key, {}).get("fingerprint") == inst["fingerprint"] and old[key].get("optimal"):
                out[key] = old[key]
                continue
            out[key] = solve_ilp(inst, time_limit)
            r = out[key]
            print(f"{key}: cost {r['cost']} {'optimal' if r['optimal'] else 'bound ' + str(r['bound'])} "
                  f"({r['seconds']}s)", flush=True)
    keep = {k: v for k, v in old.items() if k not in out and splits}
    REFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFS_FILE.write_text(json.dumps({"note": "integer-program optima of the setcover instances "
                                             "(python -m suite.setcover --refs)", "instances": {**keep, **out}},
                                    separators=(",", ":")) + "\n")
    n_opt = sum(v["optimal"] for v in out.values())
    print(f"wrote {len(out)} references ({n_opt} proven optimal) to {REFS_FILE}")


if __name__ == "__main__":
    if "--refs" in sys.argv[1:]:
        build_refs()
    else:
        print(__doc__)
