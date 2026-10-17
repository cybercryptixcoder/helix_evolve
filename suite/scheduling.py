"""Online makespan scheduling on identical parallel machines (P||Cmax, online over a list).

Jobs arrive one by one and must be assigned at once to one of m machines; candidates = all machines in
index order (so Code Zero puts every job on machine 0). The gap is makespan over a lower bound that is
exact to compute, max(ceil(sum/m), max p, p_(m) + p_(m+1)). Because that bound is not always reachable,
floor(family) is the mean gap of an offline schedule that sees all jobs in advance (longest-first list
scheduling + a move/swap local search), which is at or very near the offline optimum.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from helix3.problem import Problem

SPLIT_SEED = {"train": 4101, "valid": 5202, "test": 6303}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
# family: (seed code, machines, jobs)
FAMILIES = {"uniform": (1, 4, 100), "exponential": (2, 10, 200), "bimodal": (3, 20, 300), "lognormal": (4, 8, 150)}
TRAIN_FAMILIES = ["uniform", "exponential", "bimodal"]
HELD_OUT = ["lognormal"]


def make_jobs(family, rng):
    code, m, n = FAMILIES[family]
    if family == "uniform":
        p = rng.integers(1, 101, size=n)
    elif family == "exponential":
        p = np.ceil(rng.exponential(20.0, size=n))
    elif family == "bimodal":
        big = rng.random(n) < 0.06
        p = np.where(big, rng.integers(80, 201, size=n), rng.integers(1, 11, size=n))
    elif family == "lognormal":
        p = np.ceil(rng.lognormal(3.0, 0.9, size=n))
    else:
        raise KeyError(family)
    return np.minimum(p, 1000).astype(np.int64)


def lower_bound(p, m):
    s = np.sort(p)[::-1]
    lb = max(int(-(-int(s.sum()) // m)), int(s[0]))
    if len(s) > m:
        lb = max(lb, int(s[m - 1] + s[m]))
    return lb


def offline_best(p, m):
    """Longest-first list scheduling, then improving moves/swaps off the most loaded machine."""
    order = np.argsort(-p, kind="stable")
    assign = np.empty(len(p), dtype=np.int64)
    loads = np.zeros(m, dtype=np.int64)
    for j in order:
        i = int(np.argmin(loads))
        assign[j] = i
        loads[i] += p[j]
    lb = lower_bound(p, m)
    for _ in range(10000):
        cmax = loads.max()
        if cmax <= lb:
            break
        a = int(np.argmax(loads))
        ja = np.flatnonzero(assign == a)
        improved = False
        # move one job off machine a (to the machine where the pair max drops the most)
        new_b = loads[None, :] + p[ja][:, None]          # (|ja|, m)
        new_a = loads[a] - p[ja]
        pair = np.maximum(new_b, new_a[:, None])
        pair[:, a] = cmax
        r, b = np.unravel_index(int(np.argmin(pair)), pair.shape)
        if pair[r, b] < cmax:
            assign[ja[r]] = b
            loads[a] -= p[ja[r]]
            loads[b] += p[ja[r]]
            improved = True
        else:
            # swap a job on a with a smaller job elsewhere
            others = np.flatnonzero(assign != a)
            d = p[ja][:, None] - p[others][None, :]            # > 0: a gets lighter
            bl = loads[assign[others]][None, :]
            val = np.maximum(loads[a] - d, bl + d)
            val = np.where(d > 0, val, cmax)
            r, c = np.unravel_index(int(np.argmin(val)), val.shape)
            if val[r, c] < cmax:
                b = int(assign[others[c]])
                assign[ja[r]], assign[others[c]] = b, a
                loads[a] -= d[r, c]
                loads[b] += d[r, c]
                improved = True
        if not improved:
            break
    return assign


def schedule_metrics(p, m, assign, ref):
    loads = np.bincount(assign, weights=p, minlength=m)
    cmax = float(loads.max())
    n = len(p)
    tail = max(1, n // 10)
    head_loads = np.bincount(assign[:n - tail], weights=p[:n - tail], minlength=m)
    return {
        "gap": round(100 * (cmax / ref - 1), 3),
        "makespan": int(cmax),
        "idle_pct": round(100 * (1 - float(p.sum()) / (m * cmax)), 2),
        "spread_pct": round(100 * float(loads.max() - loads.min()) / float(loads.mean()), 2),
        "late_growth_pct": round(100 * (cmax - float(head_loads.max())) / cmax, 2),
        "max_machine_jobs": int(np.bincount(assign, minlength=m)[int(np.argmax(loads))]),
    }


@lru_cache(maxsize=None)
def _instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code, m, n = FAMILIES[fam]
        for i in range(PER_FAMILY):
            rng = np.random.default_rng([SPLIT_SEED[split], code, i])
            p = make_jobs(fam, rng)
            ref = lower_bound(p, m)
            best = offline_best(p, m)
            out.append({"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "m": m,
                        "jobs": p, "ref": float(ref), "offline": best,
                        "offline_gap": 100 * (np.bincount(best, weights=p, minlength=m).max() / ref - 1)})
    return out


def _choose(priority, args, k):
    s = np.asarray(priority(*args), dtype=float)
    if s.shape != (k,):
        raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
    if not np.all(np.isfinite(s)):
        raise ValueError("priority returned a non-finite score")
    return int(np.argmax(np.round(s, 9)))


class Scheduling(Problem):
    name = "scheduling"
    title = "Online makespan scheduling on parallel machines"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    signature = "feature(job, loads, past_jobs, jobs_left)"
    candidates_arg = 1
    description = """There are m identical machines. Jobs arrive one at a time, each with a processing time. Each job must be assigned immediately and permanently to one machine, before the next job is seen. A machine's load is the total processing time of its jobs. The goal is to make the **makespan** (the largest machine load, i.e. when the last machine finishes) as small as possible.

The number of jobs in the instance is known in advance (so you know how many are still to come), but their sizes are not.

One **decision** = one arriving job; the **candidates** are all m machines, in index order (machines are identical; the index means nothing).

Three training families: `uniform` (4 machines, 100 jobs, sizes 1-100), `exponential` (10 machines, 200 jobs, many short jobs and a few long ones), `bimodal` (20 machines, 300 jobs, mostly tiny jobs plus about 6% very large ones). The test split adds a family that training never shows. The **gap** of an instance is makespan / a lower bound - 1, in %. The bound is max(total work / m rounded up, the largest job, the sum of the m-th and (m+1)-th largest jobs). It cannot always be reached even by someone who sees every job in advance; the floor of each family is the gap of such an offline schedule."""
    signature_doc = """- `job`: float: processing time of the arriving job.
- `loads`: shape (m,), float: current load of every machine, in index order. These are the candidates.
- `past_jobs`: shape (t,), float: processing times of the jobs already assigned, in arrival order (t = 0 for the first job).
- `jobs_left`: int: how many jobs will still arrive after this one (0 for the last job).
- Return one finite number per machine (shape (m,)), or a few columns (shape (m, c)). The job goes to the highest-scoring machine."""
    metric_notes = {
        "makespan": "the largest machine load",
        "idle_pct": "% of total machine time (m x makespan) left idle",
        "spread_pct": "(largest load - smallest load) / mean load, %",
        "late_growth_pct": "how much the makespan grew during the last 10% of jobs, % of the final makespan",
        "max_machine_jobs": "number of jobs on the most loaded machine",
    }
    example_features = [
        "import numpy as np\n\ndef feature(job, loads, past_jobs, jobs_left):\n"
        "    \"\"\"Minus the load after adding the job.\"\"\"\n"
        "    return -(loads + job)\n",
        "import numpy as np\n\ndef feature(job, loads, past_jobs, jobs_left):\n"
        "    \"\"\"Is the machine empty?\"\"\"\n"
        "    return (loads == 0).astype(float)\n",
    ]

    def instances(self, split):
        return _instances(split)

    def floor(self, family, split="train"):
        g = [i["offline_gap"] for i in _instances(split) if i["family"] == family]
        return float(np.mean(g)) if g else 0.0

    def assign(self, instance, priority):
        p = instance["jobs"]
        pf = p.astype(float)
        m = instance["m"]
        n = len(p)
        loads = np.zeros(m)
        out = np.empty(n, dtype=np.int64)
        for j in range(n):
            c = _choose(priority, (np.float64(pf[j]), loads.copy(), pf[:j].copy(), n - j - 1), m)
            out[j] = c
            loads[c] += pf[j]
        return out

    def run(self, instance, priority):
        a = self.assign(instance, priority)
        cmax = float(np.bincount(a, weights=instance["jobs"], minlength=instance["m"]).max())
        return {"gap": 100.0 * (cmax / instance["ref"] - 1.0), "makespan": cmax}

    def n_candidates(self, args):
        return len(args[1])

    def diagnose(self, instance, priority):
        return schedule_metrics(instance["jobs"], instance["m"], self.assign(instance, priority), instance["ref"])

    def reference_metrics(self, instance):
        return schedule_metrics(instance["jobs"], instance["m"], instance["offline"], instance["ref"])
