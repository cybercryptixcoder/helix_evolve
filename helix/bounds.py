"""The best any program could possibly do: bounds on the optimal packing of every instance.

The evaluator's lower bound (total demand ÷ capacity) ignores job shapes, so it can sit below the true
optimum (by about 2-3% on `anticorr`; on most families the optimum is within a bin or two of it). This
module computes, for every train and test instance, how many bins the *optimal* packing needs:

  lower   no packing can use fewer bins. From the configuration LP (Gilmore–Gomory): a column-generation
          bound with 2D-knapsack pricing, the classic bound behind exact bin-packing solvers. Proven
          valid at any point (Farley's bound), and usually within a bin of the optimum.
  upper   a real packing with this many bins (offline best-fit decreasing, which sees every job in
          advance), so the optimum is at most this.

The optimum lies in [lower, upper]. Online programs see jobs one at a time, so no program can beat
`lower`, and none is expected to reach `upper` either.

The results are stored in helix/bounds.json, keyed by instance id, together with a fingerprint of each
instance, so a change to the evaluator's instances is noticed instead of silently using stale bounds.

  python -m helix.bounds                 print the stored bounds, by family
  python -m helix.bounds --compute       recompute them (needs: pip install highspy; ~minutes per instance)
"""
import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np

from .sandbox import REPO_ROOT

BOUNDS_FILE = Path(__file__).resolve().parent / "bounds.json"
SPLITS = ("train", "test")


def _instances(split):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from evaluator.problem import load_split
    return load_split(split)


def fingerprint(inst):
    return hashlib.sha1(json.dumps([inst["capacity"], inst["items"]]).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- reading the stored bounds
def version():
    """Changes whenever bounds.json does, so caches built on it can tell when to refresh."""
    try:
        st = BOUNDS_FILE.stat()
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def load():
    """{instance id: {"lower", "upper", "naive", "family", "split", "fingerprint"}}; {} if not computed yet."""
    return _load(version())


@lru_cache(maxsize=4)
def _load(_version):
    try:
        return json.loads(BOUNDS_FILE.read_text())["instances"]
    except (OSError, ValueError, KeyError):
        return {}


def family_floor(split="train"):
    return _family_floor(split, version())


@lru_cache(maxsize=8)
def _family_floor(split, _version):
    """Per family, the excess % (in the evaluator's units) of the best packing that could possibly exist:
    {family: {"lower": %, "upper": %}}. A program can't score below "lower" on that family. {} if the
    bounds file is missing or doesn't match the evaluator's instances."""
    stored = load()
    out = {}
    try:
        instances = _instances(split)
    except Exception:
        return {}
    for inst in instances:
        key = f"{split}/{inst['id']}"
        b = stored.get(key)
        if not b or b.get("fingerprint") != fingerprint(inst):
            return {}
        f = out.setdefault(inst["family"], {"lower": [], "upper": []})
        f["lower"].append(b["lower"] / inst["lower_bound"] - 1)
        f["upper"].append(b["upper"] / inst["lower_bound"] - 1)
    return {fam: {k: round(100 * sum(v) / len(v), 4) for k, v in d.items()} for fam, d in out.items()}


# ---------------------------------------------------------------- computing them
def _knapsack(sizes, values, cap, extra=0):
    """2D 0/1 knapsack by dynamic programming over (cpu, memory) capacity. Returns the best value and its
    item set, plus up to `extra` more good item sets (best ones that fit in smaller capacities)."""
    c1, c2 = int(cap[0]), int(cap[1])
    table = np.zeros((c1 + 1, c2 + 1))
    takes = []
    for i in np.nonzero(values > 1e-9)[0]:
        a, b = sizes[i]
        if a > c1 or b > c2:
            continue
        cand = table[:c1 + 1 - a, :c2 + 1 - b] + values[i]
        sub = table[a:, b:]
        take = cand > sub + 1e-12
        if take.any():
            table[a:, b:] = np.where(take, cand, sub)
            takes.append((i, a, b, take))

    def trace(x, y):
        chosen = []
        for i, a, b, take in reversed(takes):
            if x >= a and y >= b and take[x - a, y - b]:
                chosen.append(int(i))
                x, y = x - a, y - b
        return chosen

    sets = [trace(c1, c2)]
    if extra:
        flat = np.argsort(table, axis=None)[::-1]
        seen = {tuple(sorted(sets[0]))}
        for cell in flat[: extra * 20]:
            x, y = np.unravel_index(cell, table.shape)
            if table[x, y] <= 1 + 1e-6:
                break
            s = trace(int(x), int(y))
            key = tuple(sorted(s))
            if key not in seen:
                seen.add(key)
                sets.append(s)
                if len(sets) > extra:
                    break
    return table[c1, c2], sets


def _greedy_packing(sizes, cap, order):
    rem, bins = [], []
    for i in order:
        a, b = sizes[i]
        for k, r in enumerate(rem):
            if r[0] >= a and r[1] >= b:
                r[0] -= a
                r[1] -= b
                bins[k].append(int(i))
                break
        else:
            rem.append([cap[0] - a, cap[1] - b])
            bins.append([int(i)])
    return bins


def optimal_bounds(items, cap, seconds=600, extra_columns=20, naive=0, dive_seconds=180):
    """(lower, upper, lp, iterations, proven): bounds on the optimal number of bins for one instance.
    `naive` is the simple bound: once the LP can't beat it, column generation stops early."""
    import highspy
    from .reference import bins_used

    sizes = np.asarray(items, dtype=np.int64)
    n = len(sizes)
    upper = bins_used(items, cap)
    norm = sizes / np.asarray(cap, dtype=float)

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("solver", "simplex")          # warm-starts from the last basis as columns are added
    h.setOptionValue("simplex_strategy", 4)        # primal simplex: new columns keep the old basis feasible
    inf = highspy.kHighsInf
    h.addRows(n, np.ones(n), np.full(n, inf), 0, np.array([0], dtype=np.int32), np.array([], dtype=np.int32),
              np.array([], dtype=float))
    seen, columns = set(), []

    def add(columns_in, duals=None):
        """Add the columns not seen before; with `duals`, only those that can improve the LP."""
        new = [sorted(c) for c in columns_in if c and tuple(sorted(c)) not in seen
               and (duals is None or duals[c].sum() > 1 + 1e-9)]
        for c in new:
            seen.add(tuple(c))
            columns.append(c)
        if not new:
            return 0
        starts = np.cumsum([0] + [len(c) for c in new[:-1]]).astype(np.int32)
        idx = np.concatenate([np.asarray(c, dtype=np.int32) for c in new])
        h.addCols(len(new), np.ones(len(new)), np.zeros(len(new)), np.full(len(new), inf), len(idx), starts, idx,
                  np.ones(len(idx)))
        return len(new)

    add(_greedy_packing(sizes, cap, np.argsort(-norm.max(axis=1), kind="stable")))
    add(_greedy_packing(sizes, cap, np.argsort(-norm.sum(axis=1), kind="stable")))

    lower, lp, it, proven, center = 0.0, float(n), 0, False, None
    deadline = time.time() + seconds
    while time.time() < deadline:
        it += 1
        h.run()
        lp = h.getInfo().objective_function_value
        duals = np.maximum(np.asarray(h.getSolution().row_dual), 0.0)
        # Wentges smoothing: price at a point between the best duals so far and the current ones, which
        # cuts the zig-zagging that makes plain column generation slow on bin packing.
        price_at = duals if center is None else 0.5 * center + 0.5 * duals
        best, sets = _knapsack(sizes, price_at, cap, extra=extra_columns)
        if center is not None and best <= 1 + 1e-7:
            best, sets = _knapsack(sizes, duals, cap, extra=extra_columns)   # smoothing found nothing: check exactly
            price_at = duals
        farley = float(price_at.sum()) / max(best, 1.0)                     # valid for any dual-feasible scaling
        if farley > lower:
            lower, center = farley, price_at.copy()
        if best <= 1 + 1e-7:
            lower, proven = max(lower, lp), True                            # LP optimal: its value is the bound
            break
        if math.ceil(lower - 1e-6) >= math.ceil(lp - 1e-6):
            proven = True                                                   # the bound can't rise any further
            break
        if math.ceil(lp - 1e-6) <= naive:
            lower, proven = max(lower, naive), True                         # the LP only falls from here: the
            break                                                           # simple bound is as good as it gets
        # A whole packing guided by the duals adds many useful columns at once.
        order = np.argsort(-(duals / (norm.sum(axis=1) + 1e-9)), kind="stable")
        added = add(sets, duals if price_at is duals else None) + add(_greedy_packing(sizes, cap, order), duals)
        if added == 0:
            break
    if math.ceil(lower - 1e-6) < upper:
        upper = min(upper, _dive(h, columns, add, sizes, cap, time.time() + dive_seconds, extra_columns))
    return math.ceil(lower - 1e-6), upper, round(lp, 4), it, proven


def _dive(h, columns, add, sizes, cap, deadline, extra_columns):
    """A real packing from the LP (an upper bound on the optimum): repeatedly commit the bins the LP is
    surest about, drop their jobs from the problem, re-solve with fresh columns for the jobs still left,
    and pack whatever remains biggest first when time runs out."""
    n = len(sizes)
    covered = np.zeros(n, dtype=bool)
    bins = 0
    inf = 1e30
    steps = 0
    while not covered.all() and time.time() < deadline:
        steps += 1
        for _ in range(2):                                   # a little re-pricing for the jobs still left
            h.run()
            duals = np.maximum(np.asarray(h.getSolution().row_dual), 0.0)
            duals[covered] = 0.0
            best, sets = _knapsack(sizes, duals, cap, extra=extra_columns)
            if best <= 1 + 1e-7 or not add(sets, duals):
                break
        x = np.asarray(h.getSolution().col_value)
        ranked = np.argsort(-x, kind="stable")
        sure = [j for j in ranked[:50] if x[j] >= 0.9] or list(ranked[:3])
        newly = []
        for j in sure:
            rest = [i for i in columns[j] if not covered[i]]
            if rest:
                covered[rest] = True
                newly += rest
                bins += 1
        if not newly:
            break
        idx = np.asarray(sorted(set(newly)), dtype=np.int32)
        h.changeRowsBounds(len(idx), idx, np.zeros(len(idx)), np.full(len(idx), inf))   # these jobs are placed
    left = np.nonzero(~covered)[0]
    if len(left):
        norm = sizes[left] / np.asarray(cap, dtype=float)
        bins += len(_greedy_packing(sizes, cap, left[np.argsort(-norm.max(axis=1), kind="stable")]))
    return bins


def _compute_one(args):
    split, inst, seconds = args
    t = time.time()
    lower, upper, lp, it, proven = optimal_bounds(inst["items"], inst["capacity"], seconds=seconds,
                                                  naive=inst["lower_bound"])
    lower = max(lower, inst["lower_bound"])
    return f"{split}/{inst['id']}", {
        "split": split, "family": inst["family"], "naive": inst["lower_bound"], "lower": lower, "upper": upper,
        "lp": lp, "proven": proven, "iterations": it, "seconds": round(time.time() - t, 1),
        "fingerprint": fingerprint(inst)}


def compute(seconds=600, workers=2, only=None, force=False):
    stored = load()
    jobs = [(split, inst, seconds) for split in SPLITS for inst in _instances(split)
            if (only is None or inst["family"] in only)
            and (force or stored.get(f"{split}/{inst['id']}", {}).get("fingerprint") != fingerprint(inst))]
    jobs.sort(key=lambda j: -len(j[1]["items"]))
    results = dict(stored)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for key, r in pool.map(_compute_one, jobs):
            results[key] = r
            print(f"{key:28s} naive {r['naive']:4d}  optimum in [{r['lower']}, {r['upper']}]  "
                  f"lp {r['lp']:.2f}  {'proven' if r['proven'] else 'time limit'}  {r['seconds']}s", flush=True)
            BOUNDS_FILE.write_text(json.dumps({"about": __doc__.split("\n\n")[1].strip(), "instances": results},
                                              indent=1, sort_keys=True))


def show():
    for split in SPLITS:
        floor = family_floor(split)
        if not floor:
            print(f"{split}: no bounds stored for these instances (run: python -m helix.bounds --compute)")
            continue
        print(f"{split}: excess % of the best possible packing (evaluator units), by family")
        for fam, b in floor.items():
            print(f"  {fam:12s} at least {b['lower']:6.2f}   at most {b['upper']:6.2f}")
        lo = sum(b["lower"] for b in floor.values()) / len(floor)
        hi = sum(b["upper"] for b in floor.values()) / len(floor)
        print(f"  best possible score: between {-hi:.3f} and {-lo:.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m helix.bounds", description="Bounds on the optimal packing.")
    ap.add_argument("--compute", action="store_true", help="recompute the bounds (needs highspy)")
    ap.add_argument("--seconds", type=float, default=600, help="time limit per instance")
    ap.add_argument("--workers", type=int, default=2, help="instances solved in parallel")
    ap.add_argument("--family", action="append", help="only these families (repeatable)")
    ap.add_argument("--force", action="store_true", help="recompute instances that already have bounds")
    a = ap.parse_args()
    if a.compute:
        compute(a.seconds, a.workers, set(a.family) if a.family else None, a.force)
    show()
