"""Start a v10 run from an earlier run (v9): the warm start, in one of two modes (docs/V10_JOB.md).

    python -m helix10.warm --src results/v9warm/v9-s1 --out runs/v10/v10-axes --mode axes --pack results/v9warm/v9-s1/pack
    python -m helix10.warm --src results/v9warm/v9-s1 --out runs/v10/v10-warm --mode warm --pack ... --field runs/field

then `python -m helix10.job --out runs/v10/v10-axes --gens 920` runs it.

Both modes continue the source run as it stands (every program, construction, finding, track, hill and its design
map: codebook, coordinates, readings), with generations continuing its numbering, and add the field's knowledge
(helix10/sota.py, docs/AC2_SOTA.md):
- **axes**: the field's design decisions and options on the map (borrowed axes; an option is new, a decision is new
  only when the map has nothing for it), recorded in borrowed.json so exploration can favour them, and the field's
  findings in the Atlas (kind "field", with sources). No construction and no program of the field.
- **warm**: the same, plus the field's constructions (sota.IMPORTS, verified) as programs with their own tracks
  (paused, available to backtracks; each becomes a hill at the first generation) and the field's methods
  (helix10/programs/) run once on the record's construction (and the resolution transfer on Hyra's), so the run's
  main track starts from the world record and the coder starts from the field's own polish code.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

from helix4.archive import Archive, Program
from helix8.warm import prepare as prepare8
from helix9.codebook import Codebook
from helix9.pack import jl, restore
from helix9.warm import stage_source
from helix10 import sota
from helix10.run import Config

V10_SETTINGS = ("max_n", "mem_mb", "min_explore", "borrow_share", "race_rungs", "record_hill_wide", "upkeep_every",
                "max_axes", "map_axes", "big_n", "keep_top", "gc_age", "tidy_values")
MAP_FILES = ("codebook.jsonl", "coords.jsonl", "annotations.jsonl", "discoveries.jsonl", "rebuilt.jsonl", "refs.jsonl",
             "borrowed.json", "gc.jsonl")

IMPORT_CODE = '''import numpy as np


def construct(budget_seconds, start):
    """A construction of the field, imported (its program's intent says whose, and how it was made): handed back as
    it is. A program built on this one starts from that construction."""
    if start is None:
        raise ValueError("this program only hands back an imported construction")
    return np.asarray(start, dtype=float)
'''


def find_attach(cb, names):
    for nm in names or ():
        low = nm.lower()
        for a in cb.active_axes():
            if cb.axes[a]["name"].lower().startswith(low[:60]) or low.startswith(cb.axes[a]["name"].lower()[:60]):
                return a
        a = cb.find_axis(nm)
        if a is not None and a in cb.active_axes():
            return a
    return None


def seed_axes(cb, gen, log=print):
    """The field's decisions and options into codebook `cb`. Returns borrowed.json's content."""
    out = {"axes": {}, "values": {}, "matched": {}}
    for ax in sota.AXES:
        aid = find_attach(cb, ax.get("attach"))
        attached = aid is not None
        if aid is None:
            aid = cb.add_axis(ax["question"], gen, source="borrowed", question=ax["question"])
        out["axes"][aid] = {"key": ax["key"], "question": ax["question"], "attached": attached}
        for name, note in ax["options"]:
            before = set(cb.values(aid))
            vid = cb.add_value(aid, name, gen, source="borrowed")
            if vid in before:
                out["matched"][vid] = {"name": name, "note": note}          # the map has this choice already
            else:
                out["values"][vid] = {"name": name, "note": note, "axis_key": ax["key"]}
    log(f"the field's decisions: {len(out['axes'])} ({sum(1 for a in out['axes'].values() if a['attached'])} on "
        f"decisions the map had), {len(out['values'])} new options, {len(out['matched'])} options the map had already")
    return out


def add_findings(out, gen, log=print):
    path = out / "findings.jsonl"
    events = jl(path)
    n = sum(1 for e in events if e.get("op") == "new")
    have = {e.get("claim") for e in events if e.get("op") == "new" and e.get("kind") == "field"}
    added = 0
    with path.open("a") as fh:
        for claim, source in sota.FINDINGS:
            if claim in have:                                   # a v10 source has it already
                continue
            n += 1
            added += 1
            fh.write(json.dumps({"op": "new", "id": f"F{n}", "gen": gen, "kind": "field", "claim": claim,
                                 "source": source, "evidence": [], "links": []}) + "\n")
    log(f"the field's findings: {added} added to the Atlas (kind field, with sources)"
        + (f"; {len(sota.FINDINGS) - added} were there already" if added < len(sota.FINDINGS) else ""))


def import_field(out, cfg, field_dir, gen, log=print, run_programs=True):
    """The field's constructions as programs with their own tracks, then the field's methods run on the record."""
    from helix4.problems import ac2
    from helix47.evaluate import evaluate
    from helix47.run import ProblemView
    from helix10.programs import load
    field_dir = Path(field_dir)
    from helix10.run import Archive10
    problem = ProblemView(ac2, cfg.max_n)
    arch = Archive10(out)
    arch.big_n = cfg.big_n
    rows = jl(out / "tracks.jsonl")
    last = rows[-1] if rows else {"gen": gen, "tracks": [], "main": None}
    tracks = {t["id"]: t for t in last.get("tracks", [])}
    nt = len(tracks) + 1
    by_key = {}
    for item in sorted(sota.IMPORTS, key=lambda x: -x["score"]):
        f = field_dir / f"{item['key']}.npy"
        if not f.exists():
            log(f"field: {item['key']} not at hand; skipped")
            continue
        h, why = problem.check(np.load(f))
        if h is None:
            log(f"field: {item['key']} refused: {why}")
            continue
        s = problem.score(h)
        if abs(s - item["score"]) > 1e-9:
            log(f"field: {item['key']} refused: scores {s:.12f}, listed {item['score']:.12f}")
            continue
        while f"T{nt}" in tracks:
            nt += 1
        tid = f"T{nt}"
        _, fb = problem.feedback(h, None, {"cpu": 0, "wall": 0}, cfg.budget)
        src = f"{item.get('arena_id') and 'EinsteinArena solution ' + str(item['arena_id']) or item.get('url')}"
        p = Program(id=arch.new_id(), gen=gen, role="import", parent=None,
                    intent=f"the field's construction: {item['who']} ({item['date']}), {item['family']}: {item['how']}",
                    code=IMPORT_CODE, plan={"track": tid, "import": item["key"], "source": src}, valid=True, score=s,
                    n=int(len(h)), feedback=[f"imported from {src}"] + fb,
                    summary=f"imported: {item['who']}, {item['family']}")
        arch.add(p, h)
        tracks[tid] = {"id": tid, "kind": "import", "root": p.id, "opened": gen,
                       "source": f"the field's construction by {item['who']} ({item['date']}; {item['family']})",
                       "revives": None, "best": s, "best_id": p.id, "misses": cfg.track_patience, "last_gain": gen,
                       "closing": 0.0, "exps": 0, "hill": None, "hill_status": None, "import": item["key"]}
        by_key[item["key"]] = p
        log(f"field: {item['key']} ({item['who']}, n = {len(h):,}) imported as {p.id} on {tid}: {s:.12f}")
    rec = by_key.get(f"arena-{sota.RECORD['arena_id']}") or (max(by_key.values(), key=lambda q: q.score)
                                                             if by_key else None)
    if rec is None:
        raise SystemExit("field: no construction of the field could be imported")
    main = rec.plan["track"]
    last["main"] = main
    tracks[main]["misses"] = 0
    if run_programs:
        jobs = [("dinkelbach_polish", rec), ("velocity_cycles", rec)]
        if "arena-2361" in by_key:
            jobs.append(("resolution_transfer", by_key["arena-2361"]))
        for name, base in jobs:
            code = load(name)
            start = arch.construction(base.id)
            res = evaluate(problem, code, start, cfg.budget, cfg.mem_mb)
            tid = base.plan["track"]
            p = Program(id=arch.new_id(), gen=gen, role="import", parent=base.id,
                        intent=f"the field's method: {name.replace('_', ' ')} (helix10/programs/{name}.py), run on "
                               f"{base.id}", code=code, plan={"track": tid, "field_program": name},
                        valid=res["valid"], score=res["score"], start_score=res["start_score"], delta=res["delta"],
                        feedback=res["feedback"], error=res["error"], cpu=res["cpu"], n=res["n"],
                        summary=f"the field's {name.replace('_', ' ')}")
            arch.add(p, res["construction"] if res["valid"] else None)
            t = tracks[tid]
            if p.valid and p.score is not None and p.score >= (t["best"] or -1):
                t["best"], t["best_id"] = p.score, p.id
            log(f"field: {name} on {base.id}: " + (f"{p.score:.13f} ({p.delta:+.3e} on its start), {p.cpu} s CPU"
                                                    if p.valid else f"failed: {p.error[:200]}"))
    last["tracks"] = list(tracks.values())
    last["gen"] = gen
    (out / "tracks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[:-1]) + json.dumps(last) + "\n")
    return by_key


def prepare(src, out, mode="axes", seed=1, budget=150.0, pack=None, field=None, log=print, run_programs=True,
            **cfg_kw):
    src, out = Path(src), Path(out)
    if (out / "state.json").exists():
        log(f"{out} exists already: nothing done (it resumes as it is)")
        return out
    if mode not in ("axes", "warm"):
        raise SystemExit(f"mode must be axes or warm, not {mode}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        staged = stage_source(src, Path(tmp) / "src")
        prepare8(staged, out, "continue", seed, budget, "")
        for f in MAP_FILES:
            if (staged / f).exists():
                shutil.copy(staged / f, out / f)
    if pack and Path(pack).is_dir() and (Path(pack) / "manifest.json").exists():
        restore(pack, out, log=log)
    state = json.loads((out / "state.json").read_text())
    warm_gen = state.get("warm_gen") if state.get("warm_gen") is not None else state["gen_done"]
    known = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in state["config"].items() if k in known and k != "condition"})
    fresh = Config()
    for k in V10_SETTINGS:
        setattr(cfg, k, getattr(fresh, k))
    cfg.tidy_values = 12
    cfg.mode, cfg.seed, cfg.budget = mode, seed, budget
    for k, v in cfg_kw.items():
        setattr(cfg, k, v)
    # the design map: the source's, plus the field's decisions
    rows = [r for r in jl(out / "codebook.jsonl") if r.get("gen", 0) <= warm_gen]
    cb = Codebook(rows[-1]["codebook"]) if rows else Codebook()
    borrowed = seed_axes(cb, warm_gen, log)
    if (out / "borrowed.json").exists():                         # a v10 source: its borrowed options stay borrowed
        old = json.loads((out / "borrowed.json").read_text())
        for k in ("axes", "values"):
            borrowed[k] = {**old.get(k, {}), **borrowed[k]}
    for r in jl(out / "refs.jsonl"):                             # a v10 source: constructions kept by reference
        (out / "constructions").mkdir(exist_ok=True)
        (out / "constructions" / f"{r['id']}.ref").write_text(r["of"])
    with (out / "codebook.jsonl").open("a") as fh:
        fh.write(json.dumps({"gen": warm_gen, "codebook": cb.to_json()}) + "\n")
    (out / "borrowed.json").write_text(json.dumps(borrowed, indent=1))
    add_findings(out, warm_gen, log)
    if mode == "warm":
        if not field:
            raise SystemExit("mode warm needs --field (a folder of the field's constructions: python -m helix10.field get)")
        import_field(out, cfg, field, warm_gen, log, run_programs)
    state["config"] = asdict(cfg)
    state["version"] = "v10"
    state["mode"] = mode
    state["warm_source"] = str(src)
    (out / "state.json").write_text(json.dumps(state, indent=1))
    log(f"prepared {out} as a v10 run (mode {mode}) from {src}, after generation {state['gen_done']}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["axes", "warm"], required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--pack", default=None)
    ap.add_argument("--field", default=None, help="the field's constructions (python -m helix10.field get --out ...)")
    ap.add_argument("--no-programs", action="store_true", help="warm mode: don't run the field's methods at the start")
    a = ap.parse_args(argv)
    prepare(a.src, a.out, a.mode, a.seed, a.budget, pack=a.pack, field=a.field, run_programs=not a.no_programs)


if __name__ == "__main__":
    main()
