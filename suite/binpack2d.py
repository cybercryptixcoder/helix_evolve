"""Online 2D vector bin packing: Helix's original problem, on the repo's own evaluator (read-only).

Scores match `python -m evaluator` exactly: the same instances, simulator and tie-breaking. The gap is the
evaluator's excess over its simple lower bound, in %. On the train split the floor is the excess of the
optimal packings (helix/bounds.py), so progress % = 0 at Code Zero (First Fit) and 100 at the optimum.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
VALID_SEEDS, VALID_PER_FAMILY = (1001, 1002), 2


def _cls(v, cap):
    f = v / cap
    return "S" if f < 0.2 else ("M" if f < 0.4 else "L")


@lru_cache(maxsize=1)
def _optimal():
    try:
        return json.loads((ROOT / "helix" / "optimal_packings.json").read_text())["instances"]
    except (OSError, ValueError, KeyError):
        return {}


def packing_metrics(items, cap, groups, lower_bound):
    """Named metrics of a finished packing (groups = job indices per bin)."""
    items = np.asarray(items)
    cap = np.asarray(cap, dtype=float)
    n = len(groups)
    left = np.array([cap - items[g].sum(axis=0) for g in groups]) / cap
    stranded = int((((left[:, 0] < 0.05) & (left[:, 1] > 0.25)) | ((left[:, 1] < 0.05) & (left[:, 0] > 0.25))).sum())
    sizes = Counter(len(g) for g in groups)
    pats = Counter("+".join(sorted(_cls(items[j][0], cap[0]) + _cls(items[j][1], cap[1]) for j in g)) for g in groups)
    return {
        "gap": round(100 * (n / lower_bound - 1), 3),
        "bins": n,
        "jobs_per_bin": round(len(items) / n, 3),
        "two_job_bins_pct": round(100 * sizes.get(2, 0) / n, 1),
        "stranded_bins": stranded,
        "room_cpu_pct": round(100 * float(left[:, 0].mean()), 2),
        "room_mem_pct": round(100 * float(left[:, 1].mean()), 2),
        "_text": "most common bins: " + ", ".join(f"{p} x{c}" for p, c in pats.most_common(5)),
    }


class BinPack2D(Problem):
    name = "binpack2d"
    title = "Online 2D vector bin packing"
    families = ["uniform", "correlated", "anticorr", "small", "large", "bimodal"]
    held_out_families = ["lognormal", "wide"]
    signature = "feature(item, bins, capacity)"
    description = """Jobs arrive one at a time. Each job needs some CPU and some memory. Every bin (a machine) has the same capacity in both resources. Each job must be placed immediately and permanently, before the next job is seen: into an open bin that still has enough CPU **and** memory, or into a new bin. Jobs never leave. The goal is to use as few bins as possible.

One **decision** = one arriving job; the **candidates** are the open bins it fits in (oldest first) plus a brand-new empty bin (always last).

Six training families of 1,000 jobs: `uniform` (CPU and memory independent, 1-50% of a bin), `correlated`, `anticorr` (half CPU-heavy, half memory-heavy), `small` (1-20%), `large` (15-60%), `bimodal` (each resource small or large). The **gap** of an instance is bins used ÷ a simple lower bound − 1, in %."""
    signature_doc = """- `item`: shape (2,), int: the arriving job's [cpu, mem].
- `bins`: shape (k, 2), int: the remaining [cpu, mem] of every candidate bin, oldest first; **the last row is always a brand-new empty bin** (equal to capacity).
- `capacity`: shape (2,), int ([100, 100] in training, but other capacities exist: always normalise by it).
- Return one finite number per row of `bins` (shape (k,)), or a few columns (shape (k, c)), roughly in [-1, 1]."""
    metric_notes = {
        "bins": "bins used",
        "jobs_per_bin": "average jobs per bin (higher = denser)",
        "two_job_bins_pct": "% of bins holding exactly two jobs",
        "stranded_bins": "bins with < 5% left in one resource and > 25% in the other",
        "room_cpu_pct": "average CPU left per bin, % of capacity",
        "room_mem_pct": "average memory left per bin, % of capacity",
    }
    search_split = "search"     # the first two train instances of each family: searches run on 12, records on all 18
    # hidden textbook baseline (never shown to agents): the bin left fullest (Best Fit)
    baseline = [("import numpy as np\n\ndef feature(item, bins, capacity):\n    return -((bins - item) / capacity).sum(axis=1)\n", 1.0)]
    example_features = [
        "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"Best fit: minus the room left after placing.\"\"\"\n    r = (bins - item) / capacity\n    return -r.sum(axis=1)\n",
        "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"Is it the new bin?\"\"\"\n    v = np.zeros(len(bins))\n    v[-1] = 1.0\n    return v\n",
    ]

    def __init__(self):
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from evaluator import problem as ev
        self._ev = ev
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            ev = self._ev
            if split in ("train", "test"):
                self._cache[split] = ev.load_split(split)
            elif split == "search":
                tr = self.instances("train")
                self._cache[split] = [i for f in self.families for i in [x for x in tr if x["family"] == f][:2]]
            elif split == "valid":
                self._cache[split] = [ev.make_instance(f, s, i, 1000) for s in VALID_SEEDS
                                      for f in self.families for i in range(VALID_PER_FAMILY)]
            else:
                raise KeyError(split)
        return self._cache[split]

    def run(self, instance, priority):
        r = self._ev.run_instance(instance, priority)
        return {"gap": 100 * r["excess"], "bins": r["bins_used"]}

    def n_candidates(self, args):
        return len(args[1])

    def floor(self, family, split="train"):
        if split != "train":
            return 0.0
        try:
            from helix import bounds
            return float(bounds.family_floor("train").get(family, {}).get("lower", 0.0))
        except Exception:
            return 0.0

    def diagnose(self, instance, priority):
        cap = np.asarray(instance["capacity"], dtype=np.int64)
        items = np.asarray(instance["items"], dtype=np.int64)
        remaining = np.empty((len(items), 2), dtype=np.int64)
        groups, n_open = [], 0
        for step, item in enumerate(items):
            fit_idx = (remaining[:n_open] >= item).all(axis=1).nonzero()[0]
            cand = np.vstack([remaining[fit_idx], cap[None, :]])
            c = int(np.argmax(np.round(np.asarray(priority(item.copy(), cand.copy(), cap.copy()), dtype=float), 9)))
            if c == len(fit_idx):
                remaining[n_open] = cap - item
                groups.append([step])
                n_open += 1
            else:
                remaining[fit_idx[c]] -= item
                groups[fit_idx[c]].append(step)
        return packing_metrics(items, cap, groups, instance["lower_bound"])

    def reference_metrics(self, instance):
        opt = _optimal().get(instance["id"])
        if not opt:
            return {}
        m = packing_metrics(instance["items"], instance["capacity"], opt["bins"], instance["lower_bound"])
        m["_text"] = m["_text"].replace("most common bins", "reference's most common bins")
        return m
