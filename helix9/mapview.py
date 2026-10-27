"""The map viewer's data (viz/mapview.html): one format for a simulator run and for any Helix run (v4 to v9), live
or finished (docs/V9_DESIGN.md, "Seeing it").

    python -m helix9.mapview run runs/v9warm/v9-s1 --out results/v9warm/v9-s1/mapview.json     # a real run, any version
    python -m helix9.mapview sim --family easy --policy v9 --seed 3 --out viz/data/sim-easy-v9.json

The format (JSON):
- `kind`: "sim" or "run"; `title`, `subtitle`, `version`, `live`, `generated`.
- `field`: the landscape behind the map. A simulator run has the true one: every design of the planted world, laid out
  on a grid whose two directions each run through half the decisions in a Gray-code order (neighbouring cells differ
  in one decision), quantised to 0-255 between `lo` and `hi` and base64-encoded. A real run has none: the viewer
  estimates it from the programs' scores where they sit (a kernel smoother), and says so.
- `layout`: how programs were placed: "grid" (simulator), "signature" (what the programs produce: v8's shapes, by
  principal components), "design" (v9's coordinates, by principal components) or "tree" (generation by track).
- `programs`: id, gen, parent, score (and the true height in a simulator), track, kind, role, valid, x, y in [0, 1].
- `history`: per generation the best score (and the best's true height), the exploration level, records.
- `tracks`: exploration tracks with their curve of best against experiments, and their race decisions.
- `hills`: the register of hills (and, in a simulator, the planted hills with their peaks).
- `design`: v9's codebook (axes and values) and the model's importance; `events`: what happened, by generation.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import time
from itertools import product
from pathlib import Path

import numpy as np

KIND_OF_ROLE = {"seed": "seed", "warm": "seed", "alt": "alt", "wide": "wide"}


from helix9.pack import jl   # noqa: E402  (reads name.jsonl or, as pushed when large, name.jsonl.gz)


def quantise(values):
    v = np.asarray(values, dtype=float)
    lo, hi = float(np.min(v)), float(np.max(v))
    q = np.round(255 * (v - lo) / max(hi - lo, 1e-12)).astype(np.uint8)
    return {"lo": lo, "hi": hi, "b64": base64.b64encode(q.tobytes()).decode()}


def gray(k, n):
    """Mixed-radix reflected Gray code: all n-digit base-k tuples, consecutive ones differing in one digit by 1."""
    if n == 0:
        return [()]
    rest = gray(k, n - 1)
    out = []
    for d in range(k):
        seq = rest if d % 2 == 0 else list(reversed(rest))
        out += [(d,) + t for t in seq]
    return out


def pca2(X):
    X = np.asarray(X, dtype=float)
    if len(X) < 3:
        return np.full((len(X), 2), 0.5)
    Xc = X - X.mean(axis=0)
    _, _, vt = np.linalg.svd(Xc, full_matrices=False)
    Y = Xc @ vt[:2].T if vt.shape[0] >= 2 else np.column_stack([Xc @ vt[0], np.zeros(len(X))])
    out = np.zeros_like(Y)
    for j in range(2):
        lo, hi = np.percentile(Y[:, j], 1), np.percentile(Y[:, j], 99)
        out[:, j] = np.clip((Y[:, j] - lo) / max(hi - lo, 1e-12), 0, 1) * 0.92 + 0.04
    return out


# ---------------------------------------------------------------------------------------------- simulator runs
def sim_view(sim):
    w, s = sim.w, sim.s
    half = s.d // 2
    xs_axes, ys_axes = list(range(half)), list(range(half, s.d))
    gx, gy = gray(s.k, len(xs_axes)), gray(s.k, len(ys_axes))
    pos_x = {t: i for i, t in enumerate(gx)}
    pos_y = {t: i for i, t in enumerate(gy)}
    heights = np.zeros((len(gy), len(gx)))
    for j, ty in enumerate(gy):
        for i, tx in enumerate(gx):
            heights[j, i] = w.height(tuple(tx) + tuple(ty))
    W, H = len(gx), len(gy)

    def place(x):
        return (pos_x[tuple(x[:half])] + 0.5) / W, (pos_y[tuple(x[half:])] + 0.5) / H
    progs = []
    for p in sim.progs:
        px, py = place(p.x)
        progs.append({"id": p.id, "gen": p.gen, "parent": p.parent, "score": None if p.y is None else round(p.y, 6),
                      "true": round(w.height(p.x), 6), "track": p.track, "kind": p.kind, "valid": p.valid,
                      "moved": p.moved, "x": round(px, 5), "y": round(py, 5),
                      "basin": w.hills[p.basin]["name"] if not s.smooth else "one",
                      "design": list(p.x)})
    tracks = []
    for t in sim.tracks.values():
        tracks.append({"id": t["id"], "kind": t["kind"], "opened": t["opened"], "best": t["best"],
                       "best_id": t["best_id"], "exps": t["exps"], "curve": t.get("curve", []),
                       "status": (t.get("race") or {}).get("status") or ("landed" if t.get("landed") else
                                                                         "live" if sim.live(t) else "paused"),
                       "race": (t.get("race") or {}).get("decisions", [])})
    planted = []
    for h in w.hills:
        px, py = place(h["c"])
        planted.append({"name": h["name"], "peak": round(h["peak"], 4), "x": round(px, 5), "y": round(py, 5),
                        "tau": h["tau"]})
    res = sim.result()
    return {"kind": "sim", "version": sim.p.name, "live": False, "generated": time.strftime("%Y-%m-%d %H:%M"),
            "title": f"Simulator: {s.family} world, {sim.p.name}, seed {s.seed}",
            "subtitle": (f"{s.d} decisions with {s.k} options each ({len(w.hidden)} hidden at the start); "
                         f"best possible {w.best_peak:.4f}; the run ended at {res['true']:.4f} on the "
                         f"{res['basin']} hill"),
            "layout": "grid", "field": {"w": W, "h": H, "kind": "true", **quantise(heights.ravel()),
                                        "x_axes": [w.axes[i] for i in xs_axes], "y_axes": [w.axes[i] for i in ys_axes]},
            "programs": progs, "history": [{"gen": h["gen"], "best": round(h["best"], 6), "true": round(h["true"], 6),
                                            "level": h["level"], "hills": h["hills"]} for h in sim.hist],
            "tracks": tracks, "hills": [{"id": f"H{k}", "top": h["top"], "score": h["score"], "found": h["found"],
                                         "by": h["by"]} for k, h in sim.hills.items()],
            "planted": planted, "events": sim.events or [], "result": res,
            "design": {"axes": [{"id": a, "name": sim.cb.axes[a]["name"]} for a in sim.cb.active_axes()],
                       "importance": ({_sim_axis(sim, k): round(v, 4) for k, v in sim.model.importance().items()}
                                      if sim.model is not None and sim.model.ready else {})}}


def _sim_axis(sim, k):
    """The simulator's model keys (codebook ids, pairs) in the world's own axis names."""
    def one(a):
        i = sim.known.get(a)
        return sim.w.axes[i] if i is not None else str(a)
    if isinstance(k, tuple):
        return f"{one(k[0])} x {one(k[1])}"
    return "effort" if k == "effort" else one(k)


# ---------------------------------------------------------------------------------------------- real runs
def signatures(d, progs):
    sig = {r["id"]: r["sig"] for r in jl(d / "signatures.jsonl") if r.get("sig") is not None}
    for r in jl(d / "pack" / "signatures.jsonl"):           # a run on GitHub: its continuation pack has them all
        if r.get("sig") is not None:
            sig.setdefault(r["id"], r["sig"])
    cons = d / "constructions"
    if cons.is_dir():
        from helix8.hills import shape_signature
        for p in progs:
            if p["id"] in sig or not p.get("valid"):
                continue
            f = cons / f"{p['id']}.npy"
            if f.exists():
                try:
                    s = shape_signature(np.load(f))
                    if s is not None:
                        sig[p["id"]] = s.tolist()
                except Exception:                          # noqa: BLE001
                    pass
    return sig


def run_view(d, max_programs=6000):
    d = Path(d)
    state = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else {}
    summary = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else {}
    cfg = state.get("config") or {}
    version = state.get("version") or summary.get("version") or cfg.get("condition") or "?"
    raw = jl(d / "programs.jsonl")
    progs = []
    for p in raw:
        plan = p.get("plan") or {}
        progs.append({"id": p["id"], "gen": p["gen"], "parent": p.get("parent"), "valid": bool(p.get("valid")),
                      "score": p.get("score") if p.get("valid") else None, "role": p.get("role"),
                      "track": plan.get("track") or plan.get("line") or "T1",
                      "kind": plan.get("kind") or KIND_OF_ROLE.get(p.get("role"), "main" if p.get("role") == "deep" else p.get("role"))})
    if len(progs) > max_programs:
        keep = sorted(progs, key=lambda p: (-(p["score"] or -1e9)))[: max_programs // 2]
        ids = {p["id"] for p in keep} | {p["id"] for p in progs[-max_programs // 2:]}
        progs = [p for p in progs if p["id"] in ids]
    byid = {p["id"]: p for p in progs}
    sig = signatures(d, progs)
    coords = {r["id"]: r.get("coord") or {} for r in jl(d / "coords.jsonl")}
    layout = "tree"
    placed = [p for p in progs if p["id"] in sig]
    if len(placed) >= max(10, 0.3 * sum(1 for p in progs if p["valid"])):
        layout = "signature"
        Y = pca2([sig[p["id"]] for p in placed])
        for p, (x, y) in zip(placed, Y):
            p["x"], p["y"] = round(float(x), 5), round(float(y), 5)
    elif sum(1 for p in progs if coords.get(p["id"])) >= 10:
        layout = "design"
        cols = sorted({f"{a}={v}" for c in coords.values() for a, v in c.items()})
        idx = {c: i for i, c in enumerate(cols)}
        placed = [p for p in progs if coords.get(p["id"])]
        X = np.zeros((len(placed), len(cols)))
        for r, p in enumerate(placed):
            for a, v in coords[p["id"]].items():
                X[r, idx[f"{a}={v}"]] = 1.0
        Y = pca2(X + np.random.default_rng(0).normal(0, 0.02, X.shape))
        for p, (x, y) in zip(placed, Y):
            p["x"], p["y"] = round(float(x), 5), round(float(y), 5)
    # the rest: next to its parent (or by generation and track, for a tree)
    tracks_order = {}
    gmax = max((p["gen"] for p in progs), default=1) or 1
    for p in sorted(progs, key=lambda p: int(p["id"][1:])):
        if "x" in p:
            continue
        par = byid.get(p["parent"])
        if layout != "tree" and par is not None and "x" in par:
            rng = np.random.default_rng(int(p["id"][1:]))
            p["x"] = round(float(np.clip(par["x"] + rng.normal(0, 0.01), 0, 1)), 5)
            p["y"] = round(float(np.clip(par["y"] + rng.normal(0, 0.01), 0, 1)), 5)
            p["placed"] = "near its parent"
        else:
            k = tracks_order.setdefault(p["track"], len(tracks_order))
            p["x"] = round(0.04 + 0.92 * p["gen"] / gmax, 5)
            p["y"] = round(0.04 + 0.92 * ((k * 0.618) % 1.0), 5)
    for p in progs:
        if coords.get(p["id"]):
            p["design"] = coords[p["id"]]
    hist = []
    for h in jl(d / "history.jsonl"):
        hist.append({"gen": h["gen"], "best": h.get("best"), "level": h.get("level"), "record": bool(h.get("new_best")),
                     "hills": h.get("hills"), "map": h.get("map"), "events": (h.get("track_events") or [])[:12]})
    rows = jl(d / "tracks.jsonl")
    tracks = []
    if rows:
        from helix9.warm import curves_from_history
        curves = curves_from_history(rows)
        for t in rows[-1].get("tracks") or []:
            if t.get("kind") in ("seed",) or not t.get("exps"):
                continue
            tracks.append({"id": t["id"], "kind": t.get("kind"), "opened": t.get("opened"), "best": t.get("best"),
                           "best_id": t.get("best_id"), "exps": t.get("exps"), "curve": t.get("curve") or curves.get(t["id"], []),
                           "status": (t.get("race") or {}).get("status") or ("main" if t["id"] == rows[-1].get("main") else
                                                                            "paused" if t.get("misses", 0) else "live"),
                           "race": (t.get("race") or {}).get("decisions", []), "hill": t.get("hill"),
                           "target": t.get("target"), "landing": t.get("landing"), "source": t.get("source")})
    hills = []
    hrow = (jl(d / "hills.jsonl")[-1:] or [{}])[0]
    for h in hrow.get("hills") or []:
        hills.append({"id": h["id"], "top": h["top"], "score": h.get("top_score"), "found": h.get("found_gen"),
                      "by": h.get("founder"), "reached": h.get("reached"), "description": h.get("description")})
    design = {}
    cbf = d / "codebook.json"
    cbrows = jl(d / "codebook.jsonl") if not cbf.exists() else []
    cbj = json.loads(cbf.read_text()) if cbf.exists() else (cbrows[-1]["codebook"] if cbrows else None)
    if cbj:
        from helix9.codebook import Codebook
        cb = Codebook(cbj)
        last_map = next((h["map"] for h in reversed(hist) if h.get("map")), {}) or {}
        design = {"axes": [{"id": a, "name": cb.axes[a].get("question") or cb.name(a),
                            "values": [{"id": v, "name": cb.value_name(v)} for v in cb.values(a)],
                            "agreement": cb.axes[a].get("agreement")} for a in cb.active_axes()],
                  "importance": last_map.get("importance") or {}}
    best = max((p for p in progs if p["valid"] and p["score"] is not None), key=lambda p: p["score"], default=None)
    gens_done = state.get("gen_done")
    live = not summary or (summary.get("gens_done") or -1) < (cfg.get("gens") or 0)
    return {"kind": "run", "version": version, "live": bool(live), "generated": time.strftime("%Y-%m-%d %H:%M"),
            "title": f"{d.name} ({version}, {cfg.get('problem', '?')})",
            "subtitle": (f"generation {gens_done}; best {best['score']:.9f} ({best['id']})" if best else ""),
            "layout": layout, "field": {"kind": "estimated"}, "programs": progs, "history": hist, "tracks": tracks,
            "hills": hills, "design": design, "events": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("dir")
    r.add_argument("--out", required=True)
    s = sub.add_parser("sim")
    s.add_argument("--family", default="easy")
    s.add_argument("--policy", default="v9")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        view = run_view(a.dir)
    else:
        from helix9.sim import Sim, policy, spec_for
        sim = Sim(spec_for(a.family, a.seed), policy(a.policy), record_events=True)
        sim.run()
        view = sim_view(sim)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(view, separators=(",", ":")))
    print(f"wrote {a.out} ({len(view['programs'])} programs, layout {view['layout']}, "
          f"{Path(a.out).stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
