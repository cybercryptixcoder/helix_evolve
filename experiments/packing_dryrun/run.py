"""The dry run's experiments (results in this folder):

1. Is the surface smooth?  A grid over two dials (shift x shake) at n = 20, others fixed; and each dial swept alone.
2. Search over the dials: a mechanical climb (try one notch up and down on each dial, keep the best move, halve the
   notch when nothing helps) from several starting points spread across the dials (jumps); every step logged, so the
   path can be read back as reasoning. Against it, random sampling with the same number of evaluations.
3. Against the best known packings (Packomania) at n = 10, 20, 30.

    python run.py smooth | climb | all
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from pack import bounds, score

BEST_KNOWN = {10: 0.148204322565, 20: 0.111382347512, 30: 0.091671057986}   # Packomania (equal circles, unit square)
OUT = "results.json"


def load():
    try:
        return json.load(open(OUT))
    except Exception:                                   # noqa: BLE001
        return {}


def save(res):
    json.dump(res, open(OUT + ".tmp", "w"), indent=1)
    import os
    os.replace(OUT + ".tmp", OUT)


def base_point(n):
    return dict(rows=int(round(n ** 0.5)), shift=0.25, greedy=0.0, push=-2.0, sharp=12.0, shake=0.03)


def smooth(res, n=20):
    b = bounds(n)
    base = base_point(n)
    shifts = np.linspace(0, 0.5, 11)
    shakes = np.linspace(0, 0.12, 9)
    grid = [[score(n, {**base, "shift": float(s), "shake": float(k)}) for s in shifts] for k in shakes]
    res["smooth_grid"] = {"n": n, "base": base, "shift": shifts.tolist(), "shake": shakes.tolist(), "radius": grid}
    save(res)
    sweeps = {}
    for name, (lo, hi, integer) in b.items():
        vals = list(range(lo, hi + 1)) if integer else np.linspace(lo, hi, 11).tolist()
        sweeps[name] = {"values": vals, "radius": [score(n, {**base, name: v}) for v in vals]}
        res["smooth_sweeps"] = {"n": n, "base": base, "sweeps": sweeps}
        save(res)
    print("smooth done", flush=True)


def clip(n, name, v):
    lo, hi, integer = bounds(n)[name]
    v = min(max(v, lo), hi)
    return int(round(v)) if integer else float(v)


def climb(n, start, budget, log):
    """Coordinate climb. Notch: a quarter of each dial's range (1 for integers), halved when no move helps."""
    b = bounds(n)
    notch = {k: (1 if integer else (hi - lo) / 4) for k, (lo, hi, integer) in b.items()}
    cur = dict(start)
    h = score(n, cur)
    evals = 1
    log.append({"step": 0, "point": dict(cur), "radius": h, "move": "start"})
    while evals < budget:
        best_move, best_h = None, h
        for k in b:
            for sgn in (+1, -1):
                v = clip(n, k, cur[k] + sgn * notch[k])
                if v == cur[k]:
                    continue
                cand = {**cur, k: v}
                hv = score(n, cand)
                evals += 1
                if hv > best_h + 1e-7:
                    best_move, best_h = (k, cur[k], v), hv
                if evals >= budget:
                    break
            if evals >= budget:
                break
        if best_move is None:
            small = [k for k in notch if not b[k][2] and notch[k] > (b[k][1] - b[k][0]) / 64]
            if not small:
                break
            for k in small:
                notch[k] /= 2
            log.append({"step": len(log), "point": dict(cur), "radius": h, "move": "no move helps: finer notches",
                        "evals": evals})
            continue
        k, old, new = best_move
        cur[k] = new
        log.append({"step": len(log), "point": dict(cur), "radius": best_h, "evals": evals,
                    "move": f"{k} {old:.3g} -> {new:.3g}", "gain": best_h - h})
        h = best_h
    return cur, h, evals


def spread_starts(n, k, rng):
    """k starting points spread across the dials: farthest-point choice among random candidates (scaled to 0-1)."""
    b = bounds(n)
    names = list(b)

    def rand():
        return {nm: (int(rng.integers(lo, hi + 1)) if integer else float(rng.uniform(lo, hi)))
                for nm, (lo, hi, integer) in b.items()}

    def vec(p):
        return np.array([(p[nm] - b[nm][0]) / max(b[nm][1] - b[nm][0], 1e-9) for nm in names])
    cands = [rand() for _ in range(400)]
    chosen = [cands[0]]
    for _ in range(k - 1):
        d = [min(np.linalg.norm(vec(c) - vec(s)) for s in chosen) for c in cands]
        chosen.append(cands[int(np.argmax(d))])
    return chosen


def search(res, n, starts=5, budget=60):
    rng = np.random.default_rng(n)
    out = {"n": n, "best_known": BEST_KNOWN.get(n), "climbs": [], "random": None}
    total = 0
    for i, s in enumerate(spread_starts(n, starts, rng)):
        log = []
        t0 = time.time()
        p, h, e = climb(n, s, budget, log)
        total += e
        out["climbs"].append({"start": s, "end": p, "radius": h, "evals": e, "log": log,
                              "seconds": round(time.time() - t0, 1)})
        res.setdefault("search", {})[str(n)] = out
        save(res)
        print(f"n={n} climb {i + 1}: {log[0]['radius']:.5f} -> {h:.5f} in {e} evaluations", flush=True)
    b = bounds(n)
    rnd = []
    for _ in range(total):
        q = {nm: (int(rng.integers(lo, hi + 1)) if integer else float(rng.uniform(lo, hi)))
             for nm, (lo, hi, integer) in b.items()}
        rnd.append(score(n, q))
    out["random"] = {"evals": total, "best": max(rnd), "median": float(np.median(rnd))}
    res["search"][str(n)] = out
    save(res)
    print(f"n={n} random sampling, {total} evaluations: best {max(rnd):.5f}", flush=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = load()
    if what in ("smooth", "all"):
        smooth(res)
    if what in ("climb", "all"):
        for n in (10, 20, 30):
            search(res, n)
    print("all done", flush=True)
