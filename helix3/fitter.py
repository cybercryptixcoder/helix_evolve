"""The fitter: scores policies in parallel on a problem's splits and fits their weights. No LLM here.

score = mean over families of the mean gap % (lower is better). Feature code runs in worker processes with
restricted builtins; a feature that raises makes that policy invalid (score None) instead of crashing.
Weights are fitted with CMA-ES, warm-started from the current champion.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time

import numpy as np

_W = {}


def _init(problem_name):
    from helix3.problem import load_problem
    _W["problem"] = load_problem(problem_name)
    _W["sets"] = {}


def _instances(split):
    s = _W["sets"].get(split)
    if s is None:
        s = _W["sets"][split] = _W["problem"].instances(split)
    return s


def _task(args):
    codes, weights, split, idx = args
    try:
        from helix3.policy import make_priority
        p = _W["problem"]
        inst = _instances(split)[idx]
        np.random.seed(0)
        pr = make_priority(codes, weights, p.n_candidates)
        r = p.run(inst, pr)
        return inst["family"], float(r["gap"]), None
    except Exception as exc:  # noqa: BLE001 - a broken feature must never take the fitter down
        return None, None, f"{type(exc).__name__}: {exc}"[:300]


class Fitter:
    def __init__(self, problem, workers=None):
        self.problem = problem
        self.workers = workers or max(1, (os.cpu_count() or 2))
        self._pool = None
        self.evals = 0
        self.seconds = 0.0
        self._sizes = {}

    @property
    def pool(self):
        if self._pool is None:
            ctx = mp.get_context("fork")
            self._pool = ctx.Pool(self.workers, initializer=_init, initargs=(self.problem.name,))
        return self._pool

    def close(self):
        if self._pool is not None:
            self._pool.terminate()
            self._pool = None

    def size(self, split):
        if split not in self._sizes:
            self._sizes[split] = len(self.problem.instances(split))
        return self._sizes[split]

    def evaluate(self, codes, weight_sets, split="train"):
        """For each weight set: (score, {family: mean gap}, error). Codes are shared by all weight sets."""
        n = self.size(split)
        codes = tuple(codes)
        tasks = [(codes, [list(map(float, w)) for w in ws], split, i) for ws in weight_sets for i in range(n)]
        t = time.time()
        res = self.pool.map(_task, tasks, chunksize=max(1, len(tasks) // (self.workers * 4)))
        self.seconds += time.time() - t
        self.evals += len(weight_sets)
        out = []
        for j in range(len(weight_sets)):
            chunk = res[j * n:(j + 1) * n]
            errs = [e for _, _, e in chunk if e]
            if errs:
                out.append((None, {}, errs[0]))
                continue
            fams = {}
            for fam, gap, _ in chunk:
                fams.setdefault(fam, []).append(gap)
            fams = {f: float(np.mean(v)) for f, v in fams.items()}
            out.append((float(np.mean(list(fams.values()))), fams, None))
        return out

    def optimise(self, codes, x0, unpack, budget, sigma=0.3, split="train", seed=0, mask=None):
        """CMA-ES over x (scaled weights). unpack(x) -> per-feature weight lists. mask: which entries are free.
        Returns (best x, best score). Never returns worse than x0's score."""
        import cma
        x0 = np.asarray(x0, dtype=float)
        free = np.arange(len(x0)) if mask is None else np.nonzero(mask)[0]
        base = self.evaluate(codes, [unpack(x0)], split)[0][0]
        best_x, best = x0.copy(), base if base is not None else float("inf")
        if len(free) == 0 or budget <= 0:
            return best_x, best
        if len(free) == 1:                                   # a line search is better than CMA in 1-D
            v0 = x0[free[0]]
            grid = [v0 * m for m in (0.25, 0.5, 2.0, 4.0)] + [v0 + d for d in (-sigma, sigma)]
            grid = [g for g in grid if abs(g - v0) > 1e-9][:budget]
            xs = []
            for g in grid:
                x = x0.copy()
                x[free[0]] = g
                xs.append(x)
            for x, (s, _, _) in zip(xs, self.evaluate(codes, [unpack(x) for x in xs], split)):
                if s is not None and s < best - 1e-9:
                    best_x, best = x, s
            return best_x, best
        pop = max(4, min(8, 4 + int(3 * np.log(len(free)))))
        es = cma.CMAEvolutionStrategy(x0[free], sigma, {"popsize": pop, "seed": seed + 1, "verbose": -9,
                                                       "maxfevals": budget})
        used = 0
        while not es.stop() and used < budget:
            zs = es.ask()
            xs = []
            for z in zs:
                x = x0.copy()
                x[free] = z
                xs.append(x)
            res = self.evaluate(codes, [unpack(x) for x in xs], split)
            fit = []
            for x, (s, _, _) in zip(xs, res):
                s = s if s is not None else 1e6
                fit.append(s)
                if s < best - 1e-9:
                    best_x, best = x.copy(), s
            es.tell(zs, fit)
            used += len(zs)
        return best_x, best
