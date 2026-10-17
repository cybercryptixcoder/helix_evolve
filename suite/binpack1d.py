"""Online 1D bin packing (the FunSearch problem).

Items arrive one by one and are placed immediately into an open bin they fit in, or into a new bin. The gap of
an instance is bins used over the L1 lower bound ceil(sum / C), in %. The floor of a family is the mean excess of
the (tighter, still valid) Martello-Toth L2 bound over L1, so progress is never asked to beat what is provably
impossible. Instances are generated from fixed seeds; nothing is cached.
"""
from __future__ import annotations

import numpy as np

from helix3.problem import Problem

N_ITEMS = 500
# split -> (seed, instances per family)
SPLITS = {"train": (11, 3), "valid": (12, 3), "test": (13, 3)}


def _weibull(rng, n):        # FunSearch-style: Weibull(shape 3, scale 45), clipped to [1, 100]
    return np.clip(np.rint(rng.weibull(3.0, n) * 45), 1, 100)


def _uniform(rng, n):        # OR-library style: 20..100 into bins of 150
    return rng.integers(20, 101, n)


def _small(rng, n):
    return rng.integers(1, 31, n)


def _large(rng, n):
    return rng.integers(30, 71, n)


def _bimodal(rng, n):        # held out: small (1..20) or large (45..70)
    big = rng.random(n) < 0.5
    return np.where(big, rng.integers(45, 71, n), rng.integers(1, 21, n))


def _scaled(rng, n):         # held out: Weibull shape 3, scale 450, into bins of 1000
    return np.clip(np.rint(rng.weibull(3.0, n) * 450), 1, 1000)


# family -> (generator, capacity)
FAMILIES = {
    "weibull": (_weibull, 100),
    "uniform": (_uniform, 150),
    "small": (_small, 100),
    "large": (_large, 100),
    "bimodal": (_bimodal, 100),
    "scaled": (_scaled, 1000),
}


def l1_bound(items, cap):
    return -(-int(sum(int(x) for x in items)) // int(cap))


def l2_bound(items, cap):
    """Martello-Toth L2 lower bound (max over thresholds 0 <= a <= C/2)."""
    w = np.sort(np.asarray(items, dtype=np.int64))
    cap = int(cap)
    best = l1_bound(w, cap)
    for a in np.unique(np.concatenate([[0], w[w <= cap // 2]])):
        big = w[w > cap - a]
        mid = w[(w > cap / 2) & (w <= cap - a)]
        small = w[(w >= a) & (w <= cap / 2)]
        extra = max(0, -(-(int(small.sum()) - (len(mid) * cap - int(mid.sum()))) // cap))
        best = max(best, len(big) + len(mid) + extra)
    return int(best)


def make_instance(family, seed, index, n=N_ITEMS):
    gen, cap = FAMILIES[family]
    rng = np.random.default_rng([seed, list(FAMILIES).index(family), index])
    items = gen(rng, n).astype(np.int64).tolist()
    return {"id": f"{family}-{index:03d}", "family": family, "capacity": int(cap), "items": items,
            "lower_bound": l1_bound(items, cap), "l2": l2_bound(items, cap)}


class BinPack1D(Problem):
    name = "binpack1d"
    title = "Online 1D bin packing"
    families = ["weibull", "uniform", "small", "large"]
    held_out_families = ["bimodal", "scaled"]
    signature = "feature(item, bins, capacity)"
    candidates_arg = 1
    description = """Items arrive one at a time, each with a size. Every bin has the same capacity. Each item must be placed immediately and permanently, before the next item is seen: into an open bin with enough room left, or into a new bin. Items never leave. The goal is to use as few bins as possible.

One **decision** = one arriving item; the **candidates** are the open bins it fits in (oldest first) plus a brand-new empty bin (always last).

Four training families of 500 items: `weibull` (sizes from a Weibull distribution, shape 3 and scale 45, clipped to 1-100; capacity 100), `uniform` (sizes 20-100, capacity 150), `small` (sizes 1-30, capacity 100), `large` (sizes 30-70, capacity 100). Other size distributions and capacities exist in testing. The **gap** of an instance is bins used ÷ the lower bound ceil(total size ÷ capacity) − 1, in %."""
    signature_doc = """- `item`: int: the arriving item's size.
- `bins`: shape (k,), int: the remaining room of every candidate bin, oldest first; **the last entry is always a brand-new empty bin** (equal to capacity).
- `capacity`: int: the bin capacity (100 or 150 in training, but other capacities exist: always normalise by it).
- Return one finite number per entry of `bins` (shape (k,)), or a few columns (shape (k, c)), roughly in [-1, 1]."""
    metric_notes = {
        "bins": "bins used",
        "lower_bound": "the L1 lower bound ceil(total size / capacity) the gap is measured against",
        "items_per_bin": "average items per bin",
        "mean_fill_pct": "average fill of a bin, % of capacity",
        "full_bins_pct": "% of bins filled to at least 98% of capacity",
        "nearly_empty_bins": "bins filled to less than 50% of capacity",
        "bins_with_one_item": "bins holding a single item",
    }
    example_features = [
        "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"Room left after placing, as a fraction of capacity.\"\"\"\n    return (bins - item) / capacity\n",
        "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"Is it the new bin?\"\"\"\n    v = np.zeros(len(bins))\n    v[-1] = 1.0\n    return v\n",
    ]

    def __init__(self):
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLITS:
                raise KeyError(split)
            seed, per = SPLITS[split]
            fams = self.families + (self.held_out_families if split == "test" else [])
            self._cache[split] = [make_instance(f, seed, i) for f in fams for i in range(per)]
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[1])

    def floor(self, family, split="train"):
        insts = [i for i in self.instances(split) if i["family"] == family]
        if not insts:
            return 0.0
        return float(np.mean([100 * (i["l2"] / i["lower_bound"] - 1) for i in insts]))

    def _pack(self, instance, priority):
        cap = int(instance["capacity"])
        items = instance["items"]
        remaining = np.empty(len(items), dtype=np.int64)       # one entry per open bin, oldest first
        counts = np.zeros(len(items), dtype=np.int64)
        capv = np.array([cap], dtype=np.int64)
        n_open = 0
        for size in items:
            fit = (remaining[:n_open] >= size).nonzero()[0]
            cand = np.concatenate([remaining[fit], capv])
            scores = np.asarray(priority(int(size), cand.copy(), cap), dtype=float)
            if scores.shape != (len(cand),):
                raise ValueError(f"priority returned shape {scores.shape}, expected ({len(cand)},)")
            if not np.all(np.isfinite(scores)):
                raise ValueError(f"priority returned NaN or infinity: {scores.tolist()[:10]}")
            c = int(np.argmax(np.round(scores, 9)))
            if c == len(fit):
                remaining[n_open] = cap - size
                counts[n_open] = 1
                n_open += 1
            else:
                remaining[fit[c]] -= size
                counts[fit[c]] += 1
        left = [int(r) for r in remaining[:n_open]]
        # plain-Python check of the finished packing
        if any(r < 0 for r in left) or n_open * cap - sum(left) != sum(int(x) for x in items):
            raise ValueError("invalid packing")
        return n_open, left, [int(c) for c in counts[:n_open]]

    def run(self, instance, priority):
        n, _, _ = self._pack(instance, priority)
        return {"gap": 100.0 * (n / instance["lower_bound"] - 1), "bins": n}

    def diagnose(self, instance, priority):
        n, left, counts = self._pack(instance, priority)
        cap = instance["capacity"]
        fill = 1 - np.asarray(left, dtype=float) / cap
        counts = np.asarray(counts)
        hist = np.histogram(fill, bins=[0, 0.5, 0.8, 0.9, 0.95, 0.98, 1.0001])[0]
        return {
            "gap": round(100.0 * (n / instance["lower_bound"] - 1), 3),
            "bins": n,
            "lower_bound": instance["lower_bound"],
            "items_per_bin": round(len(instance["items"]) / n, 3),
            "mean_fill_pct": round(100 * float(fill.mean()), 2),
            "full_bins_pct": round(100 * float((fill >= 0.98).mean()), 1),
            "nearly_empty_bins": int((fill < 0.5).sum()),
            "bins_with_one_item": int((counts == 1).sum()),
            "_text": "bins by fill: " + ", ".join(f"{lab} x{c}" for lab, c in
                                                   zip(["<50%", "50-80%", "80-90%", "90-95%", "95-98%", ">=98%"], hist)),
        }
