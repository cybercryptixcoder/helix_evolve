"""The fitter: scores policies in parallel on a problem's splits and fits their weights. No LLM here.

score = mean over families of the mean gap % (lower is better). Feature code runs in worker processes with
restricted builtins; a feature that raises makes that policy invalid (score None) instead of crashing.
Weights are fitted with CMA-ES, warm-started from the current champion.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import signal
import threading
import time

import numpy as np

_W = {}
RUN_LIMIT = float(os.environ.get("HELIX_RUN_LIMIT", 120))     # seconds one simulation may take (a feature that hangs)


def _init(problem_name, cache_mb=256):
    from helix3.policy import ValueCache
    from helix3.problem import load_problem
    _W["problem"] = load_problem(problem_name)
    _W["sets"] = {}
    _W["cache"] = ValueCache(cache_mb) if cache_mb else None


def _instances(split):
    s = _W["sets"].get(split)
    if s is None:
        s = _W["sets"][split] = _W["problem"].instances(split)
    return s


def _alarm(*_):
    raise TimeoutError(f"one simulation took longer than {RUN_LIMIT:.0f}s (a feature is too slow or never returns)")


def _run_one(codes, weights, split, idx):
    try:
        from helix3.policy import make_priority
        p = _W["problem"]
        inst = _instances(split)[idx]
        np.random.seed(0)
        pr = make_priority(codes, weights, p.n_candidates, cache=_W.get("cache"), tag=(split, idx))
        signal.setitimer(signal.ITIMER_REAL, RUN_LIMIT)
        try:
            r = p.run(inst, pr)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        return inst["family"], float(r["gap"]), None
    except Exception as exc:  # noqa: BLE001 - a broken feature must never take the fitter down
        return None, None, f"{type(exc).__name__}: {exc}"[:300]


def _task(args):
    """One (weights, instance) task: kept for callers that use a plain multiprocessing pool."""
    codes, weights, split, idx = args
    return _run_one(codes, weights, split, idx)


def _worker(problem_name, cache_mb, inq, outq):
    signal.signal(signal.SIGALRM, _alarm)
    _init(problem_name, cache_mb)
    while True:
        msg = inq.get()
        if msg is None:
            return
        jid, part, codes, wsets, split, idxs = msg
        out = [(wi, idx, *_run_one(codes, ws, split, idx)) for idx in idxs for wi, ws in wsets]
        c = _W.get("cache")
        outq.put((jid, part, out, (c.hits, c.misses) if c else (0, 0)))


class Fitter:
    """Scores policies on a problem's splits with persistent worker processes.

    Each instance always goes to the same worker, so that worker's ValueCache already holds the feature values
    of nearby policies (the champion, the previous CMA step). One request per worker carries every weight set
    of a batch. Safe to call from several threads at once; a worker that dies is restarted and its part redone."""

    def __init__(self, problem, workers=None, cache_mb=None):
        self.problem = problem
        self.workers = workers or max(1, (os.cpu_count() or 2))
        self.cache_mb = int(os.environ.get("HELIX_CACHE_MB", 256)) if cache_mb is None else cache_mb
        self.evals = 0
        self.seconds = 0.0
        self.cache_stats = (0, 0)
        self._sizes = {}
        self._procs = None
        self._lock = threading.Lock()
        self._jobs = {}
        self._jid = 0

    # ---------------------------------------------------------------- workers
    def _spawn(self, i):
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        pr = ctx.Process(target=_worker, args=(self.problem.name, self.cache_mb, q, self._outq), daemon=True)
        pr.start()
        return pr, q

    def _start(self):
        with self._lock:
            if self._procs is not None:
                return
            ctx = mp.get_context("fork")
            self._outq = ctx.Queue()
            self._procs = [self._spawn(i) for i in range(self.workers)]
            self._stats = [(0, 0)] * self.workers
            threading.Thread(target=self._collect, daemon=True).start()

    def _collect(self):
        while True:
            try:
                jid, part, out, stats = self._outq.get()
            except (EOFError, OSError):
                return
            with self._lock:
                job = self._jobs.get(jid)
                if job is None:
                    continue
                w = job["owner"][part]
                self._stats[w] = stats
                job["res"].extend(out)
                job["left"].discard(part)
                if not job["left"]:
                    job["done"].set()

    def close(self):
        if self._procs is None:
            return
        for pr, q in self._procs:
            try:
                q.put(None)
            except (OSError, ValueError):
                pass
        for pr, _ in self._procs:
            pr.join(timeout=2)
            if pr.is_alive():
                pr.terminate()
        self._procs = None

    def size(self, split):
        if split not in self._sizes:
            self._sizes[split] = len(self.problem.instances(split))
        return self._sizes[split]

    def _plan(self, n, m):
        """Parts of a batch: (worker, instance indices, weight-set indices). Instance i lives on worker i % W;
        with more workers than instances, an instance's weight sets are split over extra workers."""
        W = self.workers
        chunks = max(1, min(m, W // n)) if n < W else 1
        parts = []
        for i in range(n):
            for c in range(chunks):
                parts.append(((i * chunks + c) % W, i, list(range(c, m, chunks))))
        merged = {}
        for w, i, wis in parts:                      # one message per (worker, weight-set chunk)
            merged.setdefault((w, tuple(wis)), []).append(i)
        return [(w, idxs, list(wis)) for (w, wis), idxs in merged.items()]

    def evaluate(self, codes, weight_sets, split="train"):
        """For each weight set: (score, {family: mean gap}, error). Codes are shared by all weight sets."""
        self._start()
        n, m = self.size(split), len(weight_sets)
        codes = tuple(codes)
        wl = [[list(map(float, w)) for w in ws] for ws in weight_sets]
        t = time.time()
        with self._lock:
            self._jid += 1
            jid = self._jid
            plan = self._plan(n, m)
            job = {"res": [], "left": set(range(len(plan))), "done": threading.Event(), "owner": {},
                   "msgs": {}}
            self._jobs[jid] = job
        for part, (w, idxs, wis) in enumerate(plan):
            msg = (jid, part, codes, [(wi, wl[wi]) for wi in wis], split, idxs)
            job["owner"][part], job["msgs"][part] = w, msg
            self._procs[w][1].put(msg)
        while not job["done"].wait(2.0):
            self._revive(job)
        with self._lock:
            del self._jobs[jid]
            h = sum(s[0] for s in self._stats)
            mi = sum(s[1] for s in self._stats)
            self.cache_stats = (h, mi)
        self.seconds += time.time() - t
        self.evals += m
        by = {}
        for wi, idx, fam, gap, err in job["res"]:
            by.setdefault(wi, []).append((fam, gap, err))
        out = []
        for j in range(m):
            chunk = by.get(j, [])
            errs = [e for _, _, e in chunk if e]
            if errs or len(chunk) < n:
                out.append((None, {}, errs[0] if errs else "missing results"))
                continue
            fams = {}
            for fam, gap, _ in chunk:
                fams.setdefault(fam, []).append(gap)
            fams = {f: float(np.mean(v)) for f, v in fams.items()}
            out.append((float(np.mean(list(fams.values()))), fams, None))
        return out

    def _revive(self, job):
        """Restart dead workers and resend this job's parts that were theirs."""
        with self._lock:
            dead = [w for w, (pr, _) in enumerate(self._procs) if not pr.is_alive()]
            for w in dead:
                self._procs[w] = self._spawn(w)
                self._stats[w] = (0, 0)
            resend = [job["msgs"][p] for p in job["left"] if job["owner"][p] in dead]
        for msg in resend:
            self._procs[job["owner"][msg[1]]][1].put(msg)

    def hit_rate(self):
        h, m = self.cache_stats
        return h / (h + m) if h + m else 0.0

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
