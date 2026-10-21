"""Behaviour of a set of Helix runs, from their files (the numbers in docs/V4_ANALYSIS.md).

    python tools/analyse_runs.py results/v4            # trajectories, records, failure points, planner effort
    python tools/analyse_runs.py results/v4 atlas-s1   # one run, generation by generation (plans and children)

Reads history.jsonl, plans.jsonl, programs.jsonl and trace.jsonl.gz of each run directory.
"""
from __future__ import annotations

import collections
import gzip
import json
import statistics as st
import sys
from pathlib import Path


def jl(path):
    path = Path(path)
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def runs(root):
    return sorted(d for d in Path(root).iterdir() if d.is_dir() and (d / "history.jsonl").exists())


def trajectories(root):
    out = []
    for d in runs(root):
        h = jl(d / "history.jsonl")
        prev, ev = h[0]["best"], []
        for x in h[1:]:
            if x["best"] - prev > 1e-6:
                ev.append(f"g{x['gen']}{(x.get('best_role') or '?')[0]}+{x['best'] - prev:.4f}")
            prev = x["best"]
        marks = [h[i]["best"] for i in (1, 5, 10, 15, 20) if i < len(h)]
        out.append(f"{d.name:12} " + " ".join(f"{v:.4f}" for v in marks) + f"  final {h[-1]['best']:.6f}\n"
                   f"{'':12} records: {' '.join(ev)}")
    return "best at g1/g5/g10/g15/g20\n" + "\n".join(out)


def failure_points(root):
    head = (f"{'run':12} {'fail':>4} {'kill':>4} {'noeff':>5} {'ident':>5} {'1base':>5} {'wrec':>4} {'stale':>5} "
            f"{'plan_s':>6} {'plmax':>5} {'rtok':>6} {'cut':>3}")
    rows = [head]
    for d in runs(root):
        P = {p["id"]: p for p in jl(d / "programs.jsonl")}
        H = jl(d / "history.jsonl")
        kids = [p for p in P.values() if int(p["gen"]) > 0]
        deep = [p for p in kids if p["role"] == "deep"]
        fail = sum(not p["valid"] for p in kids)
        kill = sum("signal" in str(p["error"]) or "CPU limit" in str(p["error"]) for p in kids)
        noeff = sum(p["valid"] and p["delta"] is not None and abs(p["delta"]) < 1e-9 for p in deep)
        by = collections.defaultdict(list)
        for p in deep:
            if p["valid"] and p["score"] is not None:
                by[(p["gen"], p["parent"])].append(round(p["score"], 10))
        ident = sum(n for v in by.values() for n in collections.Counter(v).values() if n > 1)
        onebase = sum(len(set(h.get("bases") or [])) == 1 for h in H[1:])
        wrec = sum(1 for h in H[1:] if h.get("best_role") == "wide" and h.get("new_best"))
        bb = [h["best"] for h in H]
        stale = sum(1 for p in kids if p["role"] == "wide" and p["parent"] in P and P[p["parent"]]["score"] is not None
                    and P[p["parent"]]["score"] < bb[min(int(p["gen"]) - 1, len(bb) - 1)] - 0.01)
        ps = [h.get("researcher_seconds") or 0 for h in H[1:]]
        T = jl(d / "trace.jsonl.gz")
        rt = [int(t.get("reasoning_tokens") or 0) for t in T if t.get("role") == "researcher"]
        cut = sum(t.get("finish") == "length" for t in T)
        rows.append(f"{d.name:12} {fail:4} {kill:4} {noeff:5} {ident:5} {onebase:5} {wrec:4} {stale:5} "
                    f"{st.mean(ps) if ps else 0:6.0f} {max(ps or [0]):5.0f} {st.mean(rt) if rt else 0:6.0f} {cut:3}")
    rows.append("fail: failed programs; kill: killed at the CPU limit; noeff: planned children returning their start "
                "exactly; ident: planned children with a sibling's exact score; 1base: generations with every planned "
                "experiment on one base; wrec: records from the wide loop; stale: wide children on parents > 0.01 below "
                "the record; plan_s/plmax: planner seconds mean/max; rtok: planner reasoning tokens (mean); cut: "
                "length cut-offs")
    return "\n".join(rows)


def detail(run_dir, width=500):
    P = jl(run_dir / "programs.jsonl")
    plans = {r["gen"]: r for r in jl(run_dir / "plans.jsonl")}
    out = []
    for h in jl(run_dir / "history.jsonl")[1:]:
        g = h["gen"]
        pl = (plans.get(g) or {}).get("plan") or {}
        out.append(f"===== gen {g}: best {h['best']:.6f} ({h['best_id']}), {h.get('seconds')} s, planner "
                   f"{h.get('researcher_seconds')} s, roles {h.get('roles')}")
        out.append("ANALYSIS: " + str(pl.get("analysis") or pl.get("thinking") or "")[:width])
        for p in P:
            if int(p["gen"]) == g:
                d = p.get("delta")
                res = "FAILED " + str(p.get("error"))[:100] if not p["valid"] else (
                    f"{p['score']:.6f} ({'fresh' if d is None else f'{d:+.6f}'})")
                out.append(f"  {p['id']} {p['role']:4} on {p['parent']} N={p.get('n')} cpu={p.get('cpu')} {res} | "
                           f"{str(p.get('intent') or '')[:110]}")
    return "\n".join(out)


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "results/v4")
    if len(sys.argv) > 2:
        print(detail(root / sys.argv[2]))
    else:
        print(trajectories(root) + "\n\n" + failure_points(root))
