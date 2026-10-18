"""Fairshare (open suite): staff a week of volunteer shifts, one position at a time.

A week has 7 days x 5 shifts; each shift needs a number of positions. Volunteers have an availability (the shifts
they can work), preferred shifts (a subset), a target number of shifts and a maximum. Positions are filled in
chronological order; at each decision the policy gives the position to one eligible volunteer or leaves it
uncovered (candidates shuffled per decision with the instance's seed, so Code Zero is a random policy).

This is the judgement-call objective of the open suite: there is no ground truth for how to trade coverage against
preferences against fairness, so the blend below is a choice, fixed once:
    cost = 5 * uncovered + 1 * unmet + 1 * unfairness
where a volunteer's dissatisfaction is (non-preferred shifts worked) + |shifts worked - target|, `unmet` is the sum
of dissatisfaction over volunteers, and `unfairness` is the sum over volunteers of |dissatisfaction - its mean|.
The three components are reported separately (run() and diagnose()).

Open ceiling (docs/OPEN_SUITE.md): no reference, no floor, no textbook rule. gap = 100 * cost / Code Zero's cost
on the same instance (computed once per process and cached by instance id), so Code Zero scores exactly 100.
"""
from __future__ import annotations

import numpy as np

from helix3.problem import Problem

SPLIT_SEED = {"train": 9101, "valid": 9202, "test": 9303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
TRAIN_FAMILIES = ["balanced", "scarce", "skewed"]
HELD_OUT = ["large"]
CODES = {"balanced": 1, "scarce": 2, "skewed": 3, "large": 4}
DAYS, PER_DAY = 7, 5
W_UNCOVERED, W_UNMET, W_UNFAIR = 5.0, 1.0, 1.0
_CZ = {}                      # instance id -> Code Zero's cost (in-process cache)


# ---------------------------------------------------------------------------------------------- instances
def make_week(family, rng):
    """(demand (35,), availability (V, 35) bool, preferred (V, 35) bool, target (V,), max load (V,))."""
    NS = DAYS * PER_DAY
    slot = np.tile(np.arange(PER_DAY), DAYS)
    weekend = np.repeat(np.arange(DAYS) >= 5, PER_DAY)
    if family == "balanced":
        V = 60
        demand = rng.integers(4, 9, NS)
        p_avail = rng.uniform(0.25, 0.6, V)
        f_avail = np.array([0.7, 1.0, 1.0, 0.85, 0.45])[slot] * np.where(weekend, 0.8, 1.0)
        q_pref = rng.uniform(0.3, 0.7, V)
        f_pref = np.ones(NS)
        target = rng.integers(2, 6, V)
        extra = rng.integers(0, 3, V)
    elif family == "scarce":
        V = 45
        demand = rng.integers(5, 10, NS)
        p_avail = rng.uniform(0.15, 0.5, V)
        f_avail = np.array([0.6, 1.0, 0.95, 0.7, 0.25])[slot] * np.where(weekend, 0.55, 1.0)
        q_pref = rng.uniform(0.3, 0.7, V)
        f_pref = np.array([0.8, 1.0, 1.0, 0.8, 0.5])[slot]
        target = rng.integers(2, 6, V)
        extra = rng.integers(1, 4, V)
    elif family == "skewed":
        V = 60
        demand = rng.integers(4, 9, NS)
        p_avail = rng.uniform(0.25, 0.6, V)
        f_avail = np.array([0.7, 1.0, 1.0, 0.85, 0.45])[slot] * np.where(weekend, 0.8, 1.0)
        q_pref = rng.uniform(0.4, 0.9, V)
        f_pref = np.array([0.15, 1.0, 0.9, 0.3, 0.03])[slot] * np.where(weekend, 0.4, 1.0)
        target = np.clip(np.round(rng.lognormal(np.log(3.0), 0.55, V)), 1, 8).astype(np.int64)
        extra = rng.integers(0, 3, V)
    elif family == "large":
        V = 120
        demand = rng.integers(8, 17, NS)
        p_avail = rng.uniform(0.2, 0.55, V)
        f_avail = np.array([0.65, 1.0, 1.0, 0.8, 0.35])[slot] * np.where(weekend, 0.7, 1.0)
        q_pref = rng.uniform(0.3, 0.8, V)
        f_pref = np.array([0.4, 1.0, 0.9, 0.6, 0.15])[slot] * np.where(weekend, 0.6, 1.0)
        target = np.clip(np.round(rng.lognormal(np.log(3.2), 0.45, V)), 1, 8).astype(np.int64)
        extra = rng.integers(0, 3, V)
    else:
        raise KeyError(family)
    avail = rng.random((V, NS)) < np.clip(p_avail[:, None] * f_avail[None, :] * 1.6, 0, 1)
    pref = avail & (rng.random((V, NS)) < np.clip(q_pref[:, None] * f_pref[None, :], 0, 1))
    order = rng.permutation(V)                                        # volunteer numbering means nothing
    return (demand.astype(np.int64), avail[order], pref[order], target[order].astype(np.int64),
            (target + extra)[order].astype(np.int64))


def _instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for fam in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], CODES[fam], i])
            demand, avail, pref, target, max_load = make_week(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "seed": [SPLIT_SEED[split], CODES[fam], i, 99], "demand": demand,
                        "avail": avail, "pref": pref, "availf": avail.astype(float), "preff": pref.astype(float),
                        "target": target, "max_load": max_load})
    return out


# ---------------------------------------------------------------------------------------------- simulate
def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


def score(inst, taken, uncovered):
    """The cost and its parts for an assignment matrix taken (V, 35) bool."""
    assigned = taken.sum(1)
    unpref = (taken & ~inst["pref"]).sum(1)
    dis = unpref + np.abs(assigned - inst["target"])
    unmet = float(dis.sum())
    unfair = float(np.abs(dis - dis.mean()).sum())
    return {"cost": W_UNCOVERED * uncovered + W_UNMET * unmet + W_UNFAIR * unfair, "uncovered": int(uncovered),
            "unmet": unmet, "unfairness": round(unfair, 6), "dis": dis, "assigned": assigned, "unpref": unpref}


def simulate(inst, priority=None):
    """Fill the week under `priority` (None = Code Zero: always the first shuffled candidate). Returns score()."""
    demand, avail, pref = inst["demand"], inst["avail"], inst["pref"]
    availf, preff = inst["availf"], inst["preff"]
    target, max_load = inst["target"], inst["max_load"]
    targetf, maxf = target.astype(float), max_load.astype(float)
    V, NS = avail.shape
    rng = np.random.default_rng(inst["seed"])
    assigned = np.zeros(V, dtype=np.int64)
    unpref = np.zeros(V, dtype=np.int64)
    taken = np.zeros((V, NS), dtype=bool)
    uncovered = decisions = 0
    for s in range(NS):
        for pos in range(int(demand[s])):
            elig = np.flatnonzero(avail[:, s] & (assigned < max_load) & ~taken[:, s])
            k = len(elig) + 1
            cand = np.append(elig, -1)[rng.permutation(k)]             # -1 = leave the position uncovered
            if k == 1:
                c = -1
            else:
                decisions += 1
                if priority is None:
                    c = int(cand[0])
                else:
                    args = (s, cand, pos, assigned.astype(float), targetf, maxf, unpref.astype(float),
                            availf, preff, taken.astype(float), demand)
                    c = int(cand[_choose(priority, args, k)])
            if c < 0:
                uncovered += 1
            else:
                taken[c, s] = True
                assigned[c] += 1
                if not pref[c, s]:
                    unpref[c] += 1
    out = score(inst, taken, uncovered)
    out["decisions"] = decisions
    return out


def cz_cost(inst):
    c = _CZ.get(inst["id"])
    if c is None:
        c = _CZ[inst["id"]] = simulate(inst)["cost"]
        if not c > 0:
            raise RuntimeError(f"fairshare: Code Zero has cost {c} on {inst['id']}")
    return c


# ---------------------------------------------------------------------------------------------- the problem
class FairShare(Problem):
    name = "fairshare"
    title = "Fairshare: staffing a week of volunteer shifts"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand)"
    candidates_arg = 1
    description = f"""A volunteer organisation staffs one week: {DAYS} days x {PER_DAY} shifts a day ({DAYS * PER_DAY} shifts, numbered chronologically: shift = day * {PER_DAY} + time of day, days 0-6 with days 5 and 6 the weekend, times of day 0-4 from the early shift to the night shift). Each shift needs `demand[shift]` positions, each filled by a different volunteer. Every volunteer has an **availability** (the shifts they can work), a set of **preferred** shifts (some of their available shifts), a **target** number of shifts for the week (what they would like to work) and a **maximum** (they never work more). A volunteer works at most one position per shift and only shifts they are available for.

The positions are filled one at a time in chronological order (shift 0 first; within a shift, position 0 first). One **decision** = one position: the **candidates** are the volunteers who are available for this shift, below their maximum and not already on this shift, plus the option to **leave the position uncovered** (a candidate with volunteer index -1). Candidates come in a random order (reshuffled at every decision), so the position in the list carries no information. A decision whose only candidate is "uncovered" is taken automatically. Decisions are final.

**Cost** of an instance (lower is better), computed when the week is complete:
- `uncovered`: the number of positions left uncovered;
- a volunteer's **dissatisfaction** = (shifts they work that are not among their preferred shifts) + |shifts they work - their target|;
- `unmet`: the sum of all volunteers' dissatisfaction;
- `unfairness`: the sum over volunteers of |dissatisfaction - the mean dissatisfaction over all volunteers| (0 when everyone is equally dissatisfied);
- **cost = {W_UNCOVERED:g} x uncovered + {W_UNMET:g} x unmet + {W_UNFAIR:g} x unfairness.**
The weights are a fixed judgement call (there is no ground truth for how to trade coverage, preferences and fairness); the three parts are reported separately.

Families differ in scarcity (volunteers and availability against demand), how preferences are spread over the week, targets, and size. Three training families: `balanced`, `scarce`, `skewed`; the test split adds a family that training never shows. All volunteers' data is known from the start.

There is no known best solution: the score of an instance is **gap = 100 x cost / cost of Code Zero** on that instance, where Code Zero is the policy that always takes the first candidate (a random choice, because the order is shuffled). Code Zero scores 100; lower is better and nothing tells where the best possible lies."""
    signature_doc = f"""- `shift`: int: the shift being staffed (0-{DAYS * PER_DAY - 1}; day = shift // {PER_DAY}, time of day = shift % {PER_DAY}).
- `cand`: shape (k,), int: the volunteer index of each candidate, in a random order; **-1 is the leave-uncovered option**. To read per-volunteer arrays for the candidates use e.g. `v = np.maximum(cand, 0)` and mask with `cand >= 0` (indexing with -1 would read the last volunteer).
- `position`: int: which position of this shift this is (0 = the first); positions still to fill on this shift after this one = demand[shift] - position - 1.
- `assigned`: shape (V,), float: shifts each volunteer works so far.
- `target`: shape (V,), float: each volunteer's target number of shifts.
- `max_load`: shape (V,), float: each volunteer's maximum number of shifts.
- `unpreferred`: shape (V,), float: shifts each volunteer works so far that are not among their preferred shifts.
- `avail`: shape (V, {DAYS * PER_DAY}), float: 1 where the volunteer is available for the shift, else 0.
- `pref`: shape (V, {DAYS * PER_DAY}), float: 1 where the shift is one of the volunteer's preferred shifts (always a subset of `avail`), else 0.
- `taken`: shape (V, {DAYS * PER_DAY}), float: 1 where the volunteer has been given a position on that shift so far.
- `demand`: shape ({DAYS * PER_DAY},), int: positions each shift needs.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate gets the position."""
    metric_notes = {
        "cost": f"{W_UNCOVERED:g} x uncovered + {W_UNMET:g} x unmet + {W_UNFAIR:g} x unfairness (what the gap measures)",
        "uncovered": "positions left uncovered",
        "unmet": "sum of all volunteers' dissatisfaction (non-preferred shifts worked + |shifts worked - target|)",
        "unfairness": "sum over volunteers of |dissatisfaction - mean dissatisfaction|",
        "worst_off": "the largest dissatisfaction of any volunteer",
        "pref_share_pct": "% of filled positions given to a volunteer who prefers that shift",
    }
    example_features = [
        "import numpy as np\n\ndef feature(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):\n"
        "    \"\"\"Does the candidate prefer this shift (0 for the uncovered option)?\"\"\"\n"
        "    v = np.maximum(cand, 0)\n"
        "    return np.where(cand >= 0, pref[v, shift], 0.0)\n",
        "import numpy as np\n\ndef feature(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):\n"
        "    \"\"\"Two columns: shifts still below target, and is it the uncovered option.\"\"\"\n"
        "    v = np.maximum(cand, 0)\n"
        "    return np.stack([np.where(cand >= 0, target[v] - assigned[v], 0.0), (cand < 0).astype(float)], axis=1)\n",
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
        return {"gap": 100.0 * (s["cost"] / base), "cost": s["cost"], "uncovered": s["uncovered"],
                "unmet": s["unmet"], "unfairness": s["unfairness"]}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        base = cz_cost(instance)
        s = simulate(instance, priority)
        filled = int(s["assigned"].sum())
        return {
            "gap": round(100.0 * (s["cost"] / base), 3),
            "cost": round(s["cost"], 2),
            "uncovered": s["uncovered"],
            "unmet": s["unmet"],
            "unfairness": round(s["unfairness"], 2),
            "worst_off": int(s["dis"].max()),
            "pref_share_pct": round(100 * (filled - int(s["unpref"].sum())) / max(1, filled), 2),
        }
