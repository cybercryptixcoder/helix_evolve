"""The fitter: scores policies in parallel and fits their weights. No LLM is involved here.

Scoring uses the evaluator's own simulator (`evaluator.problem.run_instance`, imported read-only) and its
own scoring formula (mean over families of the mean excess %, negated), so a score here equals the score
`python -m evaluator` gives the composed program. Feature code is run with the evaluator's restricted
builtins (only numpy and math can be imported), in worker processes, with a timeout.

Instance sets:
  train        the evaluator's train split: the official score, and the base for reported numbers
  train-fast   the first two instances of every train family (the same jobs as train's first two):
               searches, refits and probes run on this smaller set — 12 simulations instead of 18, so a
               generation fits in about a minute; the champion is still recorded on the full train split
               through the evaluator CLI
  valid        new instances from the evaluator's own generator, two seeds (6 families x 4 x 2 = 48):
               new features are accepted only if they help here too, so the search can't overfit train
  test         never touched by the search (the held-out check at the end uses it)

Weights are fitted with CMA-ES (the `cma` package), warm-started from the current champion.
"""
from __future__ import annotations

import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np

from .features import code_hash, flat, module_source
from .sandbox import REPO_ROOT

VALID_SEEDS, VALID_PER_FAMILY, VALID_ITEMS = (1001, 1002), 4, 1000
_STATE = {}


# ================================================================ worker side
def _init():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from evaluator.evaluate import _SAFE_BUILTINS
    from evaluator.problem import TRAIN_FAMILIES, load_split, make_instance
    _STATE["builtins"] = _SAFE_BUILTINS
    _STATE["sets"] = {"train": load_split("train"),
                      "train-fast": [make_instance(f, 1, i, 1000) for f in TRAIN_FAMILIES for i in (0, 1)],
                      "valid": [make_instance(f, seed, i, VALID_ITEMS)
                                for seed in VALID_SEEDS for f in TRAIN_FAMILIES
                                for i in range(VALID_PER_FAMILY)]}
    _STATE["mods"] = {}


def _module(src):
    key = code_hash(src)
    ns = _STATE["mods"].get(key)
    if ns is None:
        if len(_STATE["mods"]) > 16:
            _STATE["mods"].clear()
        ns = {"__name__": "helix_policy", "__builtins__": _STATE["builtins"]}
        exec(compile(src, "<feature policy>", "exec"), ns)
        _STATE["mods"][key] = ns
    return ns


def _simulate(inst, priority, members=False, probe=None):
    """The evaluator's simulator (same rules, same tie-breaking), optionally recording which jobs went into
    which bin, or the values of one extra function at sampled steps."""
    from evaluator.problem import run_instance
    if not members and probe is None:
        return run_instance(inst, priority), None
    cap = np.asarray(inst["capacity"], dtype=np.int64)
    items = np.asarray(inst["items"], dtype=np.int64)
    remaining = np.empty((len(items), 2), dtype=np.int64)
    groups, values, n_open = [], [], 0
    for step, item in enumerate(items):
        fit_idx = (remaining[:n_open] >= item).all(axis=1).nonzero()[0]
        cand = np.vstack([remaining[fit_idx], cap[None, :]])
        scores = np.asarray(priority(item.copy(), cand.copy(), cap.copy()), dtype=float)
        if probe is not None and step % 7 == 0:
            v = np.asarray(probe(item.copy(), cand.copy(), cap.copy()), dtype=float)
            if v.ndim not in (1, 2) or v.shape[0] != len(cand):
                raise ValueError(f"the feature returned shape {v.shape} for {len(cand)} candidate bins; "
                                 "it must return one value per row of bins")
            values.append(v)
        c = int(np.argmax(scores))
        if c == len(fit_idx):
            remaining[n_open] = cap - item
            groups.append([step])
            n_open += 1
        else:
            remaining[fit_idx[c]] -= item
            groups[fit_idx[c]].append(step)
    return {"bins_used": n_open, "family": inst["family"], "excess": n_open / inst["lower_bound"] - 1}, \
        (groups if members else values)


def _task(args):
    """One policy on one instance. Returns (family, excess or None, error, extra)."""
    kind, src, weights, split, index = args[:5]
    try:
        ns = _module(src)
        ns["_W"] = [np.asarray(w, dtype=float) for w in weights]
        np.random.seed(0)
        inst = _STATE["sets"][split][index] if split in _STATE["sets"] else None
        if kind == "score":
            r, _ = _simulate(inst, ns["priority"])
            return inst["family"], r["excess"], None, None
        if kind == "members":
            r, groups = _simulate(inst, ns["priority"], members=True)
            return inst["family"], r["excess"], None, {"id": inst["id"], "bins": groups}
        if kind == "probe":                       # sample one feature's values along the policy's own path
            fn = ns["_FUNCS"][args[5]]
            r, vals = _simulate(inst, ns["priority"], probe=fn)
            rows = [v if v.ndim == 2 else v.reshape(-1, 1) for v in vals] if vals else [np.zeros((1, 1))]
            width = max(r_.shape[1] for r_ in rows)
            stack = np.concatenate([r_ for r_ in rows if r_.shape[1] == width])
            stds = [float(np.nanstd(np.where(np.isfinite(c), c, np.nan))) if np.isfinite(c).any() else 0.0
                    for c in stack.T]
            bad = int((~np.isfinite(stack)).sum())
            return inst["family"], r["excess"], None, {"stds": stds, "nonfinite": bad, "width": width}
        if kind == "time":
            t = time.time()
            _simulate(inst, ns["priority"])
            return inst["family"], None, None, {"seconds": time.time() - t}
        raise ValueError(f"unknown task {kind}")
    except Exception as exc:  # a broken feature must never take the fitter down
        return None, None, f"{type(exc).__name__}: {exc}"[:400], None


# ================================================================ main side
class FitError(RuntimeError):
    pass


class Fitter:
    def __init__(self, workers=None, timeout=600, fit_split="train"):
        self.workers = workers or max(1, (os.cpu_count() or 2) - 1)
        self.timeout = timeout
        self.fit_split = fit_split          # "train" or "train-fast": the set searches and refits run on
        self.evals = 0
        self._pool = None

    # ------------------------------------------------------------ pool
    def pool(self):
        if self._pool is None:
            self._pool = mp.get_context("spawn").Pool(self.workers, initializer=_init)
        return self._pool

    def close(self):
        if self._pool is not None:
            self._pool.terminate()
            self._pool = None

    def _map(self, tasks, timeout=None):
        try:
            return self.pool().map_async(_task, tasks, chunksize=1).get(timeout or self.timeout)
        except mp.TimeoutError:
            self.close()                                   # a feature hung: start the workers afresh
            raise FitError(f"timed out after {timeout or self.timeout:.0f}s (a feature is too slow or hangs)")

    def sizes(self):
        if "train" not in _STATE:
            _init()
        return {k: len(v) for k, v in _STATE["sets"].items()}

    # ------------------------------------------------------------ scoring
    def evaluate(self, features, weight_vectors, split=None, timeout=None):
        """[(score, {family: excess %}) or (None, error)] for each weight vector (in scaled units)."""
        src = module_source(features)
        split = split or self.fit_split
        n = self.sizes()[split]
        tasks = [("score", src, self._per_feature(features, w), split, i) for w in weight_vectors for i in range(n)]
        out = self._map(tasks, timeout)
        self.evals += len(weight_vectors)
        results = []
        for v in range(len(weight_vectors)):
            chunk = out[v * n:(v + 1) * n]
            err = next((e for _, _, e, _ in chunk if e), None)
            if err:
                results.append((None, err))
                continue
            fams = {}
            for fam, excess, _, _ in chunk:
                fams.setdefault(fam, []).append(excess)
            fams = {f: 100 * sum(x) / len(x) for f, x in fams.items()}
            results.append((-sum(fams.values()) / len(fams), fams))
        return results

    @staticmethod
    def _per_feature(features, x):
        """Optimiser vector (scaled units) -> one array of weight x scale per feature."""
        x = np.asarray(x, dtype=float)
        out, k = [], 0
        for f in features:
            out.append(list(x[k:k + f.width] * np.asarray(f.scales, dtype=float)))
            k += f.width
        return out

    def score(self, features, weights, split="train"):
        s, fams = self.evaluate(features, [weights], split)[0]
        if s is None:
            raise FitError(fams)
        return s, fams

    # ------------------------------------------------------------ fitting
    def optimise(self, features, x0, budget, sigma=0.3, split=None, seed=0, base=None, on_step=None, free=None):
        """CMA-ES from x0. Returns (x, score, families) of the best vector seen (x0 included).
        `base` is x0's known (score, families), to save an evaluation. `free`: indices of the weights to
        search (default all); the others stay as in x0. One free weight gets a line search instead."""
        import cma
        x0 = np.asarray(x0, dtype=float)
        split = split or self.fit_split
        best = (base[0], x0.copy(), base[1]) if base else None
        if best is None:
            s, fams = self.score(features, x0, split)
            best = (s, x0.copy(), fams)
        idx = np.arange(len(x0)) if free is None else np.asarray(free, dtype=int)
        if budget <= 0 or len(idx) == 0:
            return best[1], best[0], best[2]
        if len(idx) == 1:
            return self.line_search(features, x0, int(idx[0]), budget, best, split, scale=sigma * 2)

        def full(z):
            x = x0.copy()
            x[idx] = z
            return x
        # CMA-ES's own population size (12 for 18 weights). Parallelism doesn't depend on it: every
        # (weights, instance) pair is its own task.
        pop = 4 + int(3 * math.log(len(idx)))
        es = cma.CMAEvolutionStrategy(x0[idx], sigma, {"popsize": pop, "maxfevals": budget, "verbose": -9,
                                                       "seed": seed + 1, "CMA_diagonal": len(idx) > 20})
        while not es.stop():
            Z = es.ask()
            X = [full(z) for z in Z]
            res = self.evaluate(features, X, split)
            es.tell(Z, [(-s if s is not None else 1e9) for s, _ in res])
            for x, (s, fams) in zip(X, res):
                if s is not None and s > best[0]:
                    best = (s, x.copy(), fams)
            if on_step:
                on_step(es.countevals, best[0])
        return best[1], best[0], best[2]

    def line_search(self, features, x0, index, budget, best, split="train", scale=1.0):
        """One weight: steps of both signs from its current value on a log-spaced grid, in one batch, then a
        finer grid around the best point."""
        mags = scale * np.array([0.01, 0.03, 0.1, 0.3, 1.0, 3.0])
        grid = sorted(set(np.round(x0[index] + np.concatenate([-mags, [0.0], mags]), 6)))
        tried = {}

        def run(values):
            nonlocal best
            values = [v for v in values if round(v, 6) not in tried][: max(0, budget - len(tried))]
            if not values:
                return
            X = []
            for v in values:
                x = x0.copy()
                x[index] = v
                X.append(x)
            for v, x, (s, fams) in zip(values, X, self.evaluate(features, X, split)):
                tried[round(v, 6)] = s
                if s is not None and s > best[0]:
                    best = (s, x, fams)
        run(sorted((v for v in grid if v != round(x0[index], 6)), key=lambda v: abs(v - x0[index])))   # small steps first
        if budget > len(tried):
            w = best[1][index]
            pos = grid.index(min(grid, key=lambda g: abs(g - w)))
            lo, hi = grid[max(0, pos - 1)], grid[min(len(grid) - 1, pos + 1)]
            n = min(6, budget - len(tried))
            run(list(np.linspace(lo, hi, n + 2)[1:-1]))
        return best[1], best[0], best[2]

    def importance(self, features, x, split="valid", base=None):
        """Score lost on `split` when each feature's weight is set to 0 (positive = the feature helps)."""
        x = np.asarray(x, dtype=float)
        base_score = base if base is not None else self.score(features, x, split)[0]
        X, idx = [], []
        for i in range(len(x)):
            if x[i] != 0:
                y = x.copy()
                y[i] = 0.0
                X.append(y)
                idx.append(i)
        out = [0.0] * len(x)
        for i, (s, _) in zip(idx, self.evaluate(features, X, split) if X else []):
            out[i] = round(base_score - s, 4) if s is not None else 0.0
        return out

    def feature_scales(self, features, x, index):
        """(width, [1 / spread of each column]) of feature `index` along the policy's own path on a few
        instances of the fit set. Raises FitError if the feature crashes or returns NaN or infinity."""
        src = module_source(features)
        tasks = [("probe", src, self._per_feature(features, x), self.fit_split, i, index)
                 for i in range(0, self.sizes()[self.fit_split], 3)]
        out = self._map(tasks)
        err = next((e for _, _, e, _ in out if e), None)
        if err:
            raise FitError(err)
        if any(o[3]["nonfinite"] for o in out):
            raise FitError("the feature returned NaN or infinity for some bins; guard divisions and logs")
        width = out[0][3]["width"]
        stds = np.median(np.asarray([o[3]["stds"] for o in out if o[3]["width"] == width]), axis=0)
        return width, [1.0 / s if s > 1e-9 else 1.0 for s in stds]

    def seconds_per_eval(self, features, x):
        src = module_source(features)
        w = self._per_feature(features, x)
        out = self._map([("time", src, w, self.fit_split, i) for i in range(0, self.sizes()[self.fit_split], 3)])
        err = next((e for _, _, e, _ in out if e), None)
        if err:
            raise FitError(err)
        return sum(o[3]["seconds"] for o in out) * 3

    def packings(self, features, x, instance_indices):
        """Which jobs the policy put in which bin, on the given train instances: {instance id: bins}."""
        src = module_source(features)
        out = self._map([("members", src, self._per_feature(features, x), "train", i) for i in instance_indices])
        err = next((e for _, _, e, _ in out if e), None)
        if err:
            raise FitError(err)
        return {o[3]["id"]: o[3]["bins"] for o in out}


def train_index(instance_id):
    """Position of a train instance in the evaluator's train split."""
    if "sets" not in _STATE:
        _init()
    return next(i for i, inst in enumerate(_STATE["sets"]["train"]) if inst["id"] == instance_id)
