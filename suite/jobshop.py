"""Job-shop scheduling by dispatching (Giffler-Thompson active schedules).

Each job visits every machine once in its own fixed order. The schedule is built one operation at a time:
among the next operations of all jobs, take the one that could finish earliest; its machine is the machine
to decide on, and the candidates are the next operations that need that machine and could start before
that earliest finish (job-index order). The chosen operation is scheduled at its earliest start. Every
schedule built this way is active, and some ordering reaches the optimum.

The gap is makespan over the best schedule known for the instance (cached in suite/data/jobshop_refs.json,
rebuilt with `python -m suite.jobshop --refs`: best of many randomised dispatching runs, then tabu searches
on the critical path, the N5 swap neighbourhood with move estimates). The cache also stores the trivial
lower bound max(machine load, job length); where they are equal the reference is optimal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "suite" / "data" / "jobshop_refs.json"
SPLIT_SEED = {"train": 1301, "valid": 2402, "test": 3503}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family: (seed code, jobs, machines)
FAMILIES = {"small": (1, 10, 5), "medium": (2, 15, 10), "skewed": (3, 10, 10), "large": (4, 20, 10)}
TRAIN_FAMILIES = ["small", "medium", "skewed"]
HELD_OUT = ["large"]


# ---------------------------------------------------------------------------------------------- instances
def make_shop(family, rng):
    """(machine (J, M) int, proc (J, M) int): job j's s-th operation runs on machine[j, s] for proc[j, s]."""
    code, J, M = FAMILIES[family]
    machine = np.argsort(rng.random((J, M)), axis=1)         # Taillard: each job a random machine order
    if family == "skewed":
        # a machine-dependent scale (two machines are much slower) times a heavy-tailed draw
        scale = np.ones(M)
        scale[rng.choice(M, 2, replace=False)] = 2.5
        proc = np.ceil(scale[machine] * rng.lognormal(2.8, 0.7, size=(J, M)))
        proc = np.clip(proc, 1, 300)
    else:
        proc = rng.integers(1, 100, size=(J, M))
    return machine.astype(np.int64), proc.astype(np.int64)


def lower_bound(machine, proc):
    M = machine.shape[1]
    loads = np.bincount(machine.ravel(), weights=proc.ravel(), minlength=M)
    return int(max(loads.max(), proc.sum(1).max()))


def _hash(machine, proc):
    return hashlib.sha1(machine.tobytes() + proc.tobytes()).hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code = FAMILIES[fam][0]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            machine, proc = make_shop(fam, rng)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split,
                        "machine": machine, "proc": proc, "lower_bound": lower_bound(machine, proc)})
    return out


# ---------------------------------------------------------------------------------------------- simulator
def dispatch(machine, proc, choose):
    """Giffler-Thompson. choose(args, k) -> index into the conflict set. Returns start times (J, M)."""
    J, M = machine.shape
    pf = proc.astype(float)
    ns = np.zeros(J, dtype=np.int64)                         # next step of every job
    job_ready = np.zeros(J)
    mach_free = np.zeros(M)
    job_left = pf.sum(1)
    mach_left = np.bincount(machine.ravel(), weights=pf.ravel(), minlength=M)
    start = np.zeros((J, M))
    jobs = np.arange(J)
    for _ in range(J * M):
        act = jobs[ns < M]
        s = ns[act]
        mj = machine[act, s]
        pj = pf[act, s]
        est = np.maximum(job_ready[act], mach_free[mj])
        ect = est + pj
        i = int(np.argmin(ect))
        m, cut = mj[i], ect[i]
        conf = np.flatnonzero((mj == m) & (est < cut))
        k = len(conf)
        if k == 1:
            c = 0
        else:
            jc = act[conf]
            sc = s[conf]
            has_next = sc + 1 < M
            nm = machine[jc, np.minimum(sc + 1, M - 1)]
            args = (pj[conf], job_ready[jc], job_left[jc], (M - sc).astype(float),
                    np.where(has_next, mach_left[nm], 0.0), float(mach_free[m]), float(mach_left[m]))
            c = choose(args, k)
        j = act[conf[c]]
        st = est[conf[c]]
        p = pj[conf[c]]
        start[j, ns[j]] = st
        job_ready[j] = mach_free[m] = st + p
        job_left[j] -= p
        mach_left[m] -= p
        ns[j] += 1
    return start


def schedule_metrics(machine, proc, start, ref, lb):
    J, M = machine.shape
    end = start + proc
    cmax = float(end.max())
    loads = np.bincount(machine.ravel(), weights=proc.ravel(), minlength=M)
    b = int(np.argmax(loads))
    job_end = end.max(1)
    wait = job_end - proc.sum(1)
    last = int(np.argmax(job_end))
    return {
        "gap": round(100 * (cmax / ref - 1), 3),
        "makespan": int(cmax),
        "idle_pct": round(100 * (1 - float(proc.sum()) / (M * cmax)), 2),
        "bottleneck_idle_pct": round(100 * (1 - float(loads[b]) / cmax), 2),
        "mean_wait_pct": round(100 * float(wait.mean()) / cmax, 2),
        "last_job_wait_pct": round(100 * float(wait[last]) / cmax, 2),
        "over_bound_pct": round(100 * (cmax / lb - 1), 2),
    }


def _chooser(priority):
    def choose(args, k):
        s = np.asarray(priority(*[a.copy() if hasattr(a, "copy") else a for a in args]), dtype=float)
        if s.shape != (k,):
            raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
        if not np.all(np.isfinite(s)):
            raise ValueError("priority returned a non-finite score")
        return int(np.argmax(np.round(s, 9)))
    return choose


# ---------------------------------------------------------------------------------------------- the problem
class JobShop(Problem):
    name = "jobshop"
    title = "Job-shop scheduling by dispatching"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    signature = "feature(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left)"
    candidates_arg = 0
    description = """A workshop has M machines and J jobs. Every job is a chain of M operations, one on each machine, in an order fixed by the job (different jobs visit the machines in different orders). An operation needs its machine for a fixed processing time, cannot be interrupted, and cannot start before the job's previous operation has finished. A machine runs one operation at a time. The goal is the smallest **makespan**: the time when the last operation finishes.

The schedule is built one operation at a time, moving forward in time. Among the next unscheduled operation of every job, find the one that could finish earliest; call its machine the decision machine and that finish time the cut. The **candidates** are the next operations, of any job, that need the decision machine and could start before the cut (always at least one), in job-index order. Jobs are numbered at random, so the index carries no information. The policy picks one; it is scheduled at the earliest time its job and the machine allow, and the others wait for a later decision. Each decision fixes the order of operations on one machine; when only one operation is a candidate it is taken automatically.

Three training families, Taillard-style random shops: `small` (10 jobs x 5 machines, times 1-99), `medium` (15 jobs x 10 machines, times 1-99) and `skewed` (10 jobs x 10 machines, heavy-tailed times, two machines much slower than the rest). The test split adds a family that training never shows. The **gap** of an instance is makespan / the best makespan known for that instance - 1, in %. The best-known schedules come from a long offline search, so 0 is about the best possible."""
    signature_doc = """All arrays have one entry per candidate operation (shape (k,), float), in job-index order; the scalars describe the decision machine. Times are in the instance's own units (normalise if you compare across instances).
- `proc_time`: processing time of the candidate operation.
- `job_ready`: when the candidate's job finished its previous operation (0 for a job's first operation). The operation can start at max(job_ready, machine_free).
- `job_work_left`: total processing time of the job's unscheduled operations, including this one.
- `job_ops_left`: number of the job's unscheduled operations, including this one (1 = the job's last operation).
- `next_machine_work`: total unscheduled processing time still due on the machine that the job's next operation needs (that operation included); 0 if this is the job's last operation.
- `machine_free`: float: when the decision machine finishes its current work.
- `machine_work_left`: float: total unscheduled processing time still due on the decision machine (the candidates included).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring operation is scheduled next."""
    metric_notes = {
        "makespan": "the time the last operation finishes",
        "idle_pct": "% of total machine time (M x makespan) left idle",
        "bottleneck_idle_pct": "% of the makespan the most loaded machine stands idle",
        "mean_wait_pct": "average time a job spends waiting (finish time - its total work), % of makespan",
        "last_job_wait_pct": "waiting time of the job that finishes last, % of makespan",
        "over_bound_pct": "makespan above the trivial lower bound max(machine load, job length), % (0 = provably optimal)",
    }
    # hidden textbook baseline (never shown to agents): the job with the most work left
    baseline = [("import numpy as np\n\ndef feature(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):\n    return job_work_left\n", 1.0)]
    example_features = [
        "import numpy as np\n\ndef feature(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):\n"
        "    \"\"\"Remaining work of the job, relative to the machine's remaining work.\"\"\"\n"
        "    return job_work_left / max(machine_work_left, 1.0)\n",
        "import numpy as np\n\ndef feature(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):\n"
        "    \"\"\"Processing time of the operation.\"\"\"\n"
        "    return proc_time / 100.0\n",
    ]

    def __init__(self):
        self._cache = {}
        self._refs = None

    def refs(self):
        if self._refs is None:
            try:
                self._refs = json.loads(REFS.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                raise RuntimeError(f"missing {REFS.relative_to(ROOT)}: run `python -m suite.jobshop --refs`")
        return self._refs

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            refs = self.refs()
            out = raw_instances(split)
            for inst in out:
                r = refs.get(inst["id"])
                if r is None or r["hash"] != _hash(inst["machine"], inst["proc"]):
                    raise RuntimeError(f"jobshop reference for {inst['id']} is missing or stale: "
                                       "run `python -m suite.jobshop --refs`")
                inst["ref"] = float(r["makespan"])
            self._cache[split] = out
        return self._cache[split]

    def run(self, instance, priority):
        start = dispatch(instance["machine"], instance["proc"], _chooser(priority))
        cmax = float((start + instance["proc"]).max())
        return {"gap": 100.0 * (cmax / instance["ref"] - 1.0), "makespan": cmax}

    def n_candidates(self, args):
        return len(args[0])

    def diagnose(self, instance, priority):
        start = dispatch(instance["machine"], instance["proc"], _chooser(priority))
        return schedule_metrics(instance["machine"], instance["proc"], start, instance["ref"], instance["lower_bound"])

    def reference_metrics(self, instance):
        r = self.refs().get(instance["id"])
        if not r:
            return {}
        start = np.asarray(r["start"], dtype=float)
        return schedule_metrics(instance["machine"], instance["proc"], start, instance["ref"], instance["lower_bound"])


# ---------------------------------------------------------------------------------------------- references
class _Shop:
    """Disjunctive-graph evaluation for the tabu search. Operation o = j * M + s."""

    def __init__(self, machine, proc):
        self.J, self.M = machine.shape
        self.n = self.J * self.M
        self.mach = [int(x) for x in machine.ravel()]
        self.p = [int(x) for x in proc.ravel()]
        M = self.M
        self.PJ = [o - 1 if o % M else -1 for o in range(self.n)]
        self.SJ = [o + 1 if (o + 1) % M else -1 for o in range(self.n)]

    def seqs_from_start(self, start):
        st = start.ravel()
        return [sorted((o for o in range(self.n) if self.mach[o] == m), key=lambda o: (st[o], o)) for m in range(self.M)]

    def evaluate(self, seqs):
        n, p, PJ, SJ = self.n, self.p, self.PJ, self.SJ
        PM, SM = [-1] * n, [-1] * n
        for seq in seqs:
            for a, b in zip(seq, seq[1:]):
                PM[b] = a
                SM[a] = b
        indeg = [(PJ[o] >= 0) + (PM[o] >= 0) for o in range(n)]
        stack = [o for o in range(n) if indeg[o] == 0]
        order = []
        while stack:
            o = stack.pop()
            order.append(o)
            for s in (SJ[o], SM[o]):
                if s >= 0:
                    indeg[s] -= 1
                    if indeg[s] == 0:
                        stack.append(s)
        if len(order) < n:
            return None
        r = [0] * n
        for o in order:
            a, b = PJ[o], PM[o]
            r[o] = max(r[a] + p[a] if a >= 0 else 0, r[b] + p[b] if b >= 0 else 0)
        q = [0] * n
        for o in reversed(order):
            a, b = SJ[o], SM[o]
            q[o] = max(q[a] + p[a] if a >= 0 else 0, q[b] + p[b] if b >= 0 else 0)
        cmax = max(r[o] + p[o] for o in range(n))
        return r, q, PM, SM, cmax

    def critical_blocks(self, r, q, SM, cmax):
        p, SJ = self.p, self.SJ
        o = next(o for o in range(self.n) if r[o] == 0 and p[o] + q[o] == cmax)
        path = [o]
        while True:
            nxt = -1
            for s in (SM[o], SJ[o]):
                if s >= 0 and r[s] == r[o] + p[o] and r[s] + p[s] + q[s] == cmax:
                    nxt = s
                    break
            if nxt < 0:
                break
            path.append(nxt)
            o = nxt
        blocks, cur = [], [path[0]]
        for a in path[1:]:
            if self.mach[a] == self.mach[cur[-1]]:
                cur.append(a)
            else:
                blocks.append(cur)
                cur = [a]
        blocks.append(cur)
        return blocks

    def n5(self, blocks):
        moves = []
        last = len(blocks) - 1
        for bi, b in enumerate(blocks):
            if len(b) < 2:
                continue
            if bi > 0:
                moves.append((b[0], b[1]))
            if bi < last and (len(b) > 2 or bi == 0):
                moves.append((b[-2], b[-1]))
        return list(dict.fromkeys(moves))

    def estimate(self, u, v, r, q, PM, SM):
        """Makespan estimate after swapping u (directly before v on a machine) and v."""
        p, PJ, SJ = self.p, self.PJ, self.SJ

        def head(x):
            return r[x] + p[x] if x >= 0 else 0

        def tail(x):
            return q[x] + p[x] if x >= 0 else 0
        rv = max(head(PJ[v]), head(PM[u]))
        ru = max(head(PJ[u]), rv + p[v])
        qu = max(tail(SJ[u]), tail(SM[v]))
        qv = max(tail(SJ[v]), qu + p[u])
        return max(rv + p[v] + qv, ru + p[u] + qu)


def tabu_search(shop, seqs, rng, iters=4000, stall=800):
    pos = {}

    def swap(seqs, u, v):
        m = shop.mach[u]
        i = seqs[m].index(u)
        seqs[m][i], seqs[m][i + 1] = v, u

    ev = shop.evaluate(seqs)
    best_c, best_seqs = ev[4], [s[:] for s in seqs]
    tabu = {}
    since = 0
    for it in range(iters):
        r, q, PM, SM, cmax = ev
        blocks = shop.critical_blocks(r, q, SM, cmax)
        moves = shop.n5(blocks)
        if not moves:
            break                                            # one block: makespan = that machine's load: optimal
        scored = sorted((shop.estimate(u, v, r, q, PM, SM), rng.random(), u, v) for u, v in moves)
        pick = None
        for est, _, u, v in scored:
            if tabu.get((u, v), -1) < it or est < best_c:
                pick = (u, v)
                break
        if pick is None:
            pick = scored[int(rng.integers(len(scored)))][2:]
        u, v = pick
        swap(seqs, u, v)
        new = shop.evaluate(seqs)
        if new is None:                                      # cannot happen for critical swaps; be safe
            swap(seqs, v, u)
            tabu[(u, v)] = it + 1000
            continue
        ev = new
        tabu[(v, u)] = it + 8 + int(rng.integers(0, 7))
        if ev[4] < best_c:
            best_c, best_seqs, since = ev[4], [s[:] for s in seqs], 0
        else:
            since += 1
        if since >= stall:                                   # restart from the best with a random kick
            seqs = [s[:] for s in best_seqs]
            ev = shop.evaluate(seqs)
            for _ in range(5):
                r, q, PM, SM, cmax = ev
                mv = [(a, b) for blk in shop.critical_blocks(r, q, SM, cmax) for a, b in zip(blk, blk[1:])]
                if not mv:
                    break
                a, b = mv[int(rng.integers(len(mv)))]
                swap(seqs, a, b)
                ev = shop.evaluate(seqs)
            tabu, since = {}, 0
    return best_seqs, best_c


def solve(machine, proc, seed, restarts=60, iters=6000, runs=4):
    rng = np.random.default_rng(seed)
    shop = _Shop(machine, proc)
    best_start, best_c = None, np.inf
    for t in range(restarts):                                # randomised dispatching: random scores mixed with work left
        w = 0.0 if t == 0 else float(rng.random())

        def choose(args, k):
            return int(np.argmax(w * rng.random(k) + (1 - w) * args[2] / max(1.0, args[2].max())))
        st = dispatch(machine, proc, choose)
        c = (st + proc).max()
        if c < best_c:
            best_start, best_c = st, c
    seqs, c = None, np.inf
    for _ in range(runs):                                    # independent tabu runs from the best dispatch
        sq, cc = tabu_search(shop, shop.seqs_from_start(best_start), rng, iters=iters, stall=500)
        if cc < c:
            seqs, c = sq, cc
    r = shop.evaluate(seqs)[0]
    start = np.asarray(r, dtype=float).reshape(machine.shape)
    return start, int(c)


def build_refs(restarts=60, iters=6000, runs=4):
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in raw_instances(split):
            seed = int(hashlib.sha1(inst["id"].encode()).hexdigest()[:8], 16)
            start, c = solve(inst["machine"], inst["proc"], seed, restarts, iters, runs)
            assert _feasible(inst["machine"], inst["proc"], start) and int((start + inst["proc"]).max()) == c
            out[inst["id"]] = {"makespan": c, "lower_bound": inst["lower_bound"],
                               "start": start.astype(int).tolist(), "hash": _hash(inst["machine"], inst["proc"])}
            print(f"  {inst['id']:14s} best {c:5d}  lower bound {inst['lower_bound']:5d}  ({time.time() - t0:.0f}s)", flush=True)
    REFS.parent.mkdir(parents=True, exist_ok=True)
    REFS.write_text(json.dumps({"method": f"best of {restarts} randomised dispatching runs, then the best of {runs} runs "
                                          f"of N5 tabu search on the critical path ({iters} iterations each)", "instances": out}, indent=0))
    print(f"wrote {REFS} ({len(out)} instances, {time.time() - t0:.0f}s)")


def _feasible(machine, proc, start):
    end = start + proc
    if (start[:, 1:] < end[:, :-1] - 1e-9).any():
        return False
    for m in range(machine.shape[1]):
        idx = np.argsort(start[machine == m])
        s, e = start[machine == m][idx], end[machine == m][idx]
        if (s[1:] < e[:-1] - 1e-9).any():
            return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs", action="store_true", help="rebuild suite/data/jobshop_refs.json")
    ap.add_argument("--restarts", type=int, default=60)
    ap.add_argument("--iters", type=int, default=6000)
    ap.add_argument("--runs", type=int, default=4)
    a = ap.parse_args(argv)
    if a.refs:
        build_refs(a.restarts, a.iters, a.runs)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
