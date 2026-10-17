"""0/1 knapsack, built one item at a time.

At each decision the candidates are the remaining items that still fit (index order); the chosen one is added;
the build stops when nothing fits. Instances follow Pisinger's classic generators. The reference is the exact
optimum by dynamic programming, cached in suite/data/knapsack_refs.json (rebuild: python -m suite.knapsack --refs);
an instance missing from the cache is solved on the spot (the DP takes a few milliseconds).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
REFS_FILE = ROOT / "suite" / "data" / "knapsack_refs.json"
R = 1000                                   # coefficient range
# split -> (seed, instances per family)
SPLITS = {"train": (21, 3), "valid": (22, 3), "test": (23, 3)}


def _uncorrelated(rng, n):
    w = rng.integers(1, R + 1, n)
    return rng.integers(1, R + 1, n), w


def _weakly(rng, n):
    w = rng.integers(1, R + 1, n)
    return np.maximum(1, w + rng.integers(-R // 10, R // 10 + 1, n)), w


def _strongly(rng, n):
    w = rng.integers(1, R + 1, n)
    return w + R // 10, w


def _inverse(rng, n):
    v = rng.integers(1, R + 1, n)
    return v, v + R // 10


def _almost_strong(rng, n):    # held out
    w = rng.integers(1, R + 1, n)
    return w + R // 10 + rng.integers(-R // 500, R // 500 + 1, n), w


FAMILIES = {
    "uncorrelated": _uncorrelated,
    "weakly_correlated": _weakly,
    "strongly_correlated": _strongly,
    "inverse_strongly_correlated": _inverse,
    "almost_strongly_correlated": _almost_strong,
}


def fingerprint(values, weights, capacity):
    return hashlib.sha1(json.dumps([list(map(int, values)), list(map(int, weights)), int(capacity)]).encode()).hexdigest()[:16]


def make_instance(family, seed, index):
    rng = np.random.default_rng([seed, list(FAMILIES).index(family), index])
    n = int(rng.integers(100, 201))
    v, w = FAMILIES[family](rng, n)
    v, w = np.asarray(v, dtype=np.int64), np.asarray(w, dtype=np.int64)
    cap = int(w.sum()) // 2
    return {"id": f"{family}-{index:03d}", "family": family, "values": v.tolist(), "weights": w.tolist(),
            "capacity": cap, "fingerprint": fingerprint(v, w, cap)}


def solve_dp(values, weights, capacity):
    """Exact 0/1 knapsack by DP over capacities. Returns (optimum, sorted chosen indices)."""
    v = np.asarray(values, dtype=np.int64)
    w = np.asarray(weights, dtype=np.int64)
    cap = int(capacity)
    best = np.zeros(cap + 1, dtype=np.int64)
    keep = np.zeros((len(v), cap + 1), dtype=bool)
    for i in range(len(v)):
        wi = int(w[i])
        if wi > cap:
            continue
        cand = best[:cap + 1 - wi] + v[i]
        take = cand > best[wi:]
        keep[i, wi:] = take
        best[wi:] = np.where(take, cand, best[wi:])
    c, chosen = cap, []
    for i in range(len(v) - 1, -1, -1):
        if keep[i, c]:
            chosen.append(i)
            c -= int(w[i])
    chosen.sort()
    opt = int(best[cap])
    assert int(v[chosen].sum()) == opt and int(w[chosen].sum()) <= cap
    return opt, chosen


def _load_refs():
    try:
        return json.loads(REFS_FILE.read_text())["instances"]
    except (OSError, ValueError, KeyError):
        return {}


def solution_metrics(instance, chosen, opt):
    v = np.asarray(instance["values"], dtype=float)
    w = np.asarray(instance["weights"], dtype=float)
    cap = instance["capacity"]
    chosen = np.asarray(sorted(chosen), dtype=int)
    value, weight = float(v[chosen].sum()), float(w[chosen].sum())
    ref = set(instance["ref_items"])
    unused = cap - weight
    left = np.setdiff1d(np.arange(len(v)), chosen)
    return {
        "gap": round(100.0 * (1 - value / opt), 4),
        "value": int(value),
        "items_taken": int(len(chosen)),
        "fill_pct": round(100 * weight / cap, 3),
        "value_per_weight": round(value / max(weight, 1.0), 4),
        "mean_item_weight_pct": round(100 * float(w[chosen].mean()) / cap, 3) if len(chosen) else 0.0,
        "shared_with_reference_pct": round(100 * len(ref.intersection(chosen.tolist())) / max(1, len(ref)), 1),
        "_text": (f"unused capacity {unused:.0f}; smallest weight left out {w[left].min():.0f}" if len(left)
                  else f"unused capacity {unused:.0f}; every item taken"),
    }


class Knapsack(Problem):
    name = "knapsack"
    title = "0/1 knapsack, built item by item"
    families = ["uncorrelated", "weakly_correlated", "strongly_correlated", "inverse_strongly_correlated"]
    held_out_families = ["almost_strongly_correlated"]
    signature = "feature(values, weights, remaining, capacity, taken)"
    candidates_arg = 0
    description = """There are n items, each with a positive integer value and weight, and one knapsack with a weight capacity. A solution is a set of items whose total weight is at most the capacity; the goal is the largest total value. Each item is taken at most once.

The solution is built one item at a time. One **decision** = choosing the next item to add; the **candidates** are all items not yet taken whose weight still fits in the remaining capacity, in their original index order. The chosen item is added for good (nothing is ever removed) and the build stops when no remaining item fits.

Four training families (Pisinger's classic generators), 100-200 items each, weights in 1-1000, capacity = half the total weight: `uncorrelated` (value uniform in 1-1000, independent of weight), `weakly_correlated` (value within ±100 of the weight, at least 1), `strongly_correlated` (value = weight + 100), `inverse_strongly_correlated` (weight = value + 100). The **gap** of an instance is 1 − value ÷ the optimal value (exact, by dynamic programming), in %."""
    signature_doc = """- `values`: shape (k,), int: the value of every candidate item (the items not yet taken that still fit), in index order.
- `weights`: shape (k,), int: their weights (each ≤ `remaining`).
- `remaining`: int: the capacity still free.
- `capacity`: int: the knapsack's total capacity (it differs between instances: normalise by it).
- `taken`: int: how many items have been added so far.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)), roughly in [-1, 1]."""
    metric_notes = {
        "value": "total value of the items taken",
        "items_taken": "number of items in the solution",
        "fill_pct": "total weight taken, % of capacity",
        "value_per_weight": "total value ÷ total weight of the items taken",
        "mean_item_weight_pct": "average weight of a taken item, % of capacity",
        "shared_with_reference_pct": "% of the optimal solution's items that this solution also took",
    }
    # hidden textbook baseline (never shown to agents): the best value per unit of weight
    baseline = [("import numpy as np\n\ndef feature(values, weights, remaining, capacity, taken):\n    return values / np.maximum(weights, 1e-9)\n", 1.0)]
    example_features = [
        "import numpy as np\n\ndef feature(values, weights, remaining, capacity, taken):\n    \"\"\"Value as a fraction of the largest candidate value.\"\"\"\n    return values / max(1.0, float(values.max()))\n",
        "import numpy as np\n\ndef feature(values, weights, remaining, capacity, taken):\n    \"\"\"Minus the weight as a fraction of the remaining capacity.\"\"\"\n    return -weights / max(1.0, float(remaining))\n",
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
            for inst in insts:
                ref = refs.get(f"{split}/{inst['id']}")
                if not ref or ref.get("fingerprint") != inst["fingerprint"]:
                    opt, items = solve_dp(inst["values"], inst["weights"], inst["capacity"])
                    ref = {"opt": opt, "items": items}
                inst["opt"], inst["ref_items"] = int(ref["opt"]), list(ref["items"])
            self._cache[split] = insts
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    def _build(self, instance, priority):
        v = np.asarray(instance["values"], dtype=np.int64)
        w = np.asarray(instance["weights"], dtype=np.int64)
        cap = int(instance["capacity"])
        avail = np.ones(len(v), dtype=bool)
        remaining, chosen = cap, []
        while True:
            cand = np.flatnonzero(avail & (w <= remaining))
            if len(cand) == 0:
                break
            scores = np.asarray(priority(v[cand].copy(), w[cand].copy(), remaining, cap, len(chosen)), dtype=float)
            if scores.shape != (len(cand),):
                raise ValueError(f"priority returned shape {scores.shape}, expected ({len(cand)},)")
            if not np.all(np.isfinite(scores)):
                raise ValueError(f"priority returned NaN or infinity: {scores.tolist()[:10]}")
            j = int(cand[int(np.argmax(np.round(scores, 9)))])
            avail[j] = False
            remaining -= int(w[j])
            chosen.append(j)
        # plain-Python check
        values, weights = instance["values"], instance["weights"]
        if len(set(chosen)) != len(chosen) or sum(weights[j] for j in chosen) > cap:
            raise ValueError("invalid solution")
        return chosen, sum(values[j] for j in chosen)

    def run(self, instance, priority):
        chosen, value = self._build(instance, priority)
        return {"gap": max(0.0, 100.0 * (1 - value / instance["opt"])), "value": int(value)}

    def diagnose(self, instance, priority):
        chosen, _ = self._build(instance, priority)
        return solution_metrics(instance, chosen, instance["opt"])

    def reference_metrics(self, instance):
        m = solution_metrics(instance, instance["ref_items"], instance["opt"])
        m["_text"] = "reference: " + m["_text"]
        return m


def build_refs():
    p = Knapsack()
    out = {}
    for split in SPLITS:
        for inst in p.instances(split):
            opt, items = solve_dp(inst["values"], inst["weights"], inst["capacity"])
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "opt": opt, "items": items}
    REFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFS_FILE.write_text(json.dumps({"note": "exact optima of the knapsack instances (python -m suite.knapsack --refs)",
                                     "instances": out}, separators=(",", ":")) + "\n")
    print(f"wrote {len(out)} optima to {REFS_FILE}")


if __name__ == "__main__":
    if "--refs" in sys.argv[1:]:
        build_refs()
    else:
        print(__doc__)
