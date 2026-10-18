"""Progression (open suite): build a large subset of {1..n} that avoids an invented linear equation, greedily.

Each family has one equation a*x + b*y = c*z with a + b = c (so it is invariant under shifting and scaling: no
interval and no residue class avoids it, and the largest avoiding sets have no known formula). A set is valid when it
contains no solution with x, y, z pairwise distinct (for these equations two equal variables force the third, so
"distinct" only excludes x = y = z). The set is built one number at a time: the candidates are the numbers whose
addition keeps the set valid; the build ends when none remain. Score = the final set's size (bigger is better).

Open ceiling, maximisation (docs/OPEN_SUITE.md, round 2): gap = 100 x Code Zero's size / size, so Code Zero (the
first candidate of a shuffled list, i.e. a random maximal set) scores exactly 100 and a set twice as large scores 50.
Code Zero's sizes are computed once per process (fast) and cached by instance id.

The available mask is kept up to date with vectorised updates: after adding e, every number v completing a solution
with e and one earlier element w (six role assignments of e, w, v to x, y, z) becomes unavailable.
"""
from __future__ import annotations

import numpy as np

from helix3.problem import Problem

SPLIT_SEED = {"train": 3301, "valid": 3402, "test": 3503}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family -> ((a, b, c), (n_min, n_max)) for a*x + b*y = c*z
FAMILIES = {
    "trio": ((1, 2, 3), (400, 600)),
    "pentad": ((2, 3, 5), (350, 550)),
    "skew": ((1, 4, 5), (400, 600)),
    "hept": ((3, 4, 7), (350, 550)),
}
TRAIN_FAMILIES = ["trio", "pentad", "skew"]
HELD_OUT = ["hept"]
CODES = {"trio": 1, "pentad": 2, "skew": 3, "hept": 4}
_CZ = {}                      # (split, instance id) -> Code Zero's set size


def _instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for fam in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        coef, (lo, hi) = FAMILIES[fam]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], CODES[fam], i])
            n = int(rng.integers(lo, hi + 1))
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "n": n,
                        "coef": np.array(coef, dtype=np.int64), "seed": [SPLIT_SEED[split], CODES[fam], i, 5]})
    return out


def _block(avail, e, W, coef, n):
    """Mark unavailable every v that completes a*x + b*y = c*z with the new element e and an earlier element w."""
    if len(W) == 0:
        return
    a, b, c = (int(t) for t in coef)
    for num, den in ((a * e + b * W, c),           # e = x, w = y -> z
                     (a * W + b * e, c),           # e = y, w = x -> z
                     (c * W - a * e, b),           # e = x, w = z -> y
                     (c * e - a * W, b),           # e = z, w = x -> y
                     (c * W - b * e, a),           # e = y, w = z -> x
                     (c * e - b * W, a)):          # e = z, w = y -> x
        ok = (num % den == 0) & (num >= den) & (num <= den * n)
        if ok.any():
            avail[num[ok] // den - 1] = False


def build(inst, priority=None, stats=None):
    """The greedy build under `priority` (None = Code Zero). Returns the final set size."""
    n, coef = inst["n"], inst["coef"]
    rng = np.random.default_rng(inst["seed"])
    avail = np.ones(n, dtype=bool)
    chosen = np.zeros(n, dtype=bool)
    order = []
    left10 = None
    while True:
        cand = np.flatnonzero(avail) + 1
        k = len(cand)
        if k == 0:
            break
        cand = cand[rng.permutation(k)]
        if priority is None or k == 1:
            e = int(cand[0])
        else:
            s = np.asarray(priority(cand, chosen, avail, n, coef), dtype=float)
            if s.shape != (k,):
                raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
            e = int(cand[int(np.argmax(np.round(s, 9)))])
        W = np.asarray(order, dtype=np.int64)
        chosen[e - 1] = True
        avail[e - 1] = False
        _block(avail, e, W, coef, n)
        order.append(e)
        if len(order) == 10:
            left10 = int(avail.sum())
    if stats is not None:
        stats.update(order=order, chosen=chosen, left10=left10 if left10 is not None else 0)
    return len(order)


def is_valid(S, coef):
    """Brute-force check: no x, y, z in S, pairwise distinct, with a*x + b*y = c*z."""
    S = np.asarray(sorted(S), dtype=np.int64)
    a, b, c = (int(t) for t in coef)
    member = set(S.tolist())
    for x in S:
        num = a * int(x) + b * S                    # c*z = a*x + b*y for every y
        for y, v in zip(S, num):
            if y != x and v % c == 0 and (v // c) in member and v // c != x and v // c != y:
                return False
    return True


def cz_size(inst):
    key = (inst["split"], inst["id"])
    v = _CZ.get(key)
    if v is None:
        v = _CZ[key] = build(inst)
    return v


def _max_run(chosen):
    best = run = 0
    for c in chosen:
        run = run + 1 if c else 0
        best = max(best, run)
    return best


# ---------------------------------------------------------------------------------------------- the problem
class Progression(Problem):
    name = "progression"
    title = "Progression: a large set of numbers avoiding an invented equation"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(cand, chosen, avail, n, coef)"
    candidates_arg = 0
    description = f"""A mathematical construction with no known best answer. Build a set S of whole numbers from 1 to n that contains no solution of the equation

    a*x + b*y = c*z      with x, y, z in S, pairwise distinct

for fixed positive coefficients a, b, c with a + b = c (so x = y = z is always a solution of the equation; that is why the three must be distinct). The order of x and y matters (b*x + a*y = c*z is a different condition), and x, y, z can be in any order of size.

**One decision** = adding one number to S. The **candidates** are the numbers not in S whose addition keeps S free of solutions; they come in a random order (reshuffled at every decision), so the list order carries no information. Numbers are never removed. The build ends when no candidate is left (S cannot be extended), so every finished set is maximal; their sizes differ a lot.

**Score** of an instance: the size of the final set (bigger is better). The **gap** is 100 x (size of Code Zero's set) / (size of this set), where Code Zero is the policy that always takes the first candidate (a random number): Code Zero scores 100; a set twice as large scores 50; nothing tells where the largest possible lies.

**Families** differ in the equation and the range of n: `trio` (x + 2y = 3z, n from {FAMILIES['trio'][1][0]} to {FAMILIES['trio'][1][1]}), `pentad` (2x + 3y = 5z, n from {FAMILIES['pentad'][1][0]} to {FAMILIES['pentad'][1][1]}), `skew` (x + 4y = 5z, n from {FAMILIES['skew'][1][0]} to {FAMILIES['skew'][1][1]}). The test split adds a family with an equation of the same form that training never shows."""
    signature_doc = """- `cand`: shape (k,), int: the candidate numbers (each between 1 and n), in a random order.
- `chosen`: shape (n,), bool: the current set S as a mask; `chosen[v - 1]` is True when the number v is in S (so `chosen[cand - 1]` is False for every candidate).
- `avail`: shape (n,), bool: the numbers that can still be added; `avail[v - 1]` is True exactly when v is a candidate.
- `n`: int: the numbers range over 1..n.
- `coef`: shape (3,), int: (a, b, c) of the equation a*x + b*y = c*z (a + b = c).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is added next."""
    metric_notes = {
        "size": "the final set's size (what the gap measures; bigger is better)",
        "density_pct": "100 x size / n",
        "low_half_pct": "% of the set's numbers that are at most n / 2",
        "max_run": "longest run of consecutive numbers in the set",
        "left_after_10": "candidates left after the first 10 additions, as % of n (how much the early choices excluded)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(cand, chosen, avail, n, coef):\n"
        "    \"\"\"Smaller numbers first.\"\"\"\n"
        "    return -cand.astype(float)\n",
        "import numpy as np\n\ndef feature(cand, chosen, avail, n, coef):\n"
        "    \"\"\"Two columns: distance from the middle of the range, and candidates left.\"\"\"\n"
        "    return np.stack([np.abs(cand - n / 2.0), np.full(len(cand), float(avail.sum()))], axis=1)\n",
    ]

    def __init__(self):
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            self._cache[split] = _instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    def run(self, instance, priority):
        size = build(instance, priority)
        return {"gap": 100.0 * (cz_size(instance) / size), "size": size}

    def diagnose(self, instance, priority):
        s = {}
        size = build(instance, priority, s)
        n = instance["n"]
        order = np.asarray(s["order"])
        return {
            "gap": round(100.0 * (cz_size(instance) / size), 3),
            "size": size,
            "density_pct": round(100.0 * size / n, 2),
            "low_half_pct": round(100.0 * float((order <= n / 2).mean()), 1),
            "max_run": _max_run(s["chosen"]),
            "left_after_10": round(100.0 * s["left10"] / n, 1),
        }
