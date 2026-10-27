"""Start a v9 run from an earlier run (v8, v7, v4.7 or v4): the warm start (docs/V9_JOB.md).

    python -m helix9.warm --src results/v8warm/v8-s1 --out runs/v9warm/v9-s1 \\
        --pack results/v8warm/v8-s1/pack --replay results/v9warm/replay --seed 1 --budget 60

then `python -m helix9.run --out runs/v9warm/v9-s1 --gens 800` resumes it as a v9 run.

As helix8/warm.py (every program, finding, track, hill and the history kept; generations continue the source's
numbering; the warm start counts as a record), plus:
- the **continuation pack** (helix9/pack.py) restored: the constructions it holds and every program's signature, so
  the source can be the run folder as pushed to GitHub, with no local files (files pushed gzipped because of their
  size, name.jsonl.gz, are read as well);
- the **replay's map** (helix9/replay.py), if given: its codebook and the coordinates of the programs it read, so the
  design map starts with what the earlier run already knows;
- **the race, applied retroactively** to the earlier run's explorations (restarts, bold experiments, flips): each is
  judged at the rungs its curve reached, against the others, as v9 would have judged it. Those v9 would have kept
  climbing are live again; the rest stay paused (never closed).
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

from helix8.warm import prepare as prepare8
from helix9.pack import jl, restore
from helix9.race import Race, record_curve, retro_judge
from helix9.run import Config

RETRO_KINDS = ("restart", "bold", "flip")


def curves_from_history(rows):
    """{track id: [[experiments, best], ...]} from tracks.jsonl's rows (one per generation)."""
    curves = {}
    for row in rows:
        for t in row.get("tracks") or []:
            c = curves.setdefault(t["id"], [])
            pt = [t.get("exps") or 0, t.get("best")]
            if not c or c[-1] != pt:
                if c and c[-1][0] == pt[0]:
                    c[-1] = pt
                else:
                    c.append(pt)
    return curves


def retro_race(out, cfg, log=print):
    rows = jl(out / "tracks.jsonl")
    if not rows:
        return {}
    last = rows[-1]
    curves = curves_from_history(rows)
    race = Race(rungs=cfg.race_rungs, q=cfg.race_q, q_rising=cfg.race_q_rising, min_cohort=cfg.race_min_cohort,
                floor=lambda ref: max(cfg.gain_floor, 0.0) * max(abs(ref or 0.0), 1e-12), rule=cfg.race_rule)
    tracks = last.get("tracks") or []
    for t in tracks:
        t["curve"] = curves.get(t["id"], [])
    keep = max(1, int(getattr(cfg, "running_cap", 3)) - 1)
    status = retro_judge(race, tracks, last.get("gen"), keep, kinds=RETRO_KINDS, main=last.get("main"))
    last["tracks"] = tracks
    (out / "tracks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[:-1]) + json.dumps(last) + "\n")
    live = [t["id"] for t in tracks if (t.get("race") or {}).get("status") == "running"]
    log(f"the race, applied to the earlier explorations: {status}; racing again: {', '.join(live[:12]) or 'none'}"
        + (f"; {status['waiting']} more qualify and wait their turn (one is taken whenever a new exploration opens, "
           f"in turn with new drops)" if status.get("waiting") else ""))
    return status


def stage_source(src, tmp):
    """The source as earlier versions' warm starts read it (plain files): a file pushed to GitHub as name.jsonl.gz or
    in chunks (name/, helix9/publish.py) is unpacked into `tmp`, next to links to the other files. Returns the folder
    to read (src itself if every file is plain)."""
    from helix9.publish import read_chunks
    src = Path(src)
    packed = {}
    for f in src.iterdir():
        if f.is_file() and f.name.endswith(".jsonl.gz") and f.name != "trace.jsonl.gz" and not (src / f.name[:-3]).exists():
            packed[f.name[:-3]] = f
        elif f.is_dir() and (f / "index.json").exists() and f.name != "trace" and not (src / f"{f.name}.jsonl").exists():
            packed[f"{f.name}.jsonl"] = f
    if not packed:
        return src
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    skip = set(packed.values())
    for f in src.iterdir():
        if f not in skip and f.name not in ("trace", "trace.jsonl.gz"):
            (tmp / f.name).symlink_to(f.resolve())
    for name, f in packed.items():
        if f.is_dir():
            (tmp / name).write_bytes(read_chunks(f))
        else:
            with gzip.open(f, "rb") as fi, (tmp / name).open("wb") as fo:
                shutil.copyfileobj(fi, fo, 1 << 20)
    return tmp


def prepare(src, out, mode="continue", seed=1, budget=60.0, label="", pack=None, replay=None, log=print, **cfg_kw):
    src, out = Path(src), Path(out)
    if (out / "state.json").exists():
        log(f"{out} exists already: nothing done (it resumes as it is)")
        return out
    with tempfile.TemporaryDirectory(dir=out.parent if out.parent.exists() else None) as tmp:
        prepare8(stage_source(src, Path(tmp) / "src"), out, mode, seed, budget, label)
    if pack and Path(pack).is_dir() and (Path(pack) / "manifest.json").exists():
        restore(pack, out, log=log)
    state = json.loads((out / "state.json").read_text())
    state["warm_source"] = str(src)
    known = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in state["config"].items() if k in known and k != "condition"})
    for k, v in cfg_kw.items():
        setattr(cfg, k, v)
    warm_gen = state.get("warm_gen") if state.get("warm_gen") is not None else state["gen_done"]
    if replay and Path(replay).is_dir() and (Path(replay) / "codebook.json").exists():
        rp = Path(replay)
        cb = json.loads((rp / "codebook.json").read_text())
        (out / "codebook.jsonl").write_text(json.dumps({"gen": warm_gen, "codebook": cb}) + "\n")
        have = {p["id"] for p in jl(out / "programs.jsonl")}
        rows = [dict(r, gen=warm_gen) for r in jl(rp / "coords.jsonl") if r.get("id") in have]
        (out / "coords.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        ann = [dict(r, gen=warm_gen) for r in jl(rp / "annotations.jsonl") if r.get("id") in have]
        (out / "annotations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ann))
        log(f"the replay's map: {len(cb.get('axes', {}))} decisions, {len(rows)} programs placed, {len(ann)} read twice")
    if mode == "continue":
        retro_race(out, cfg, log=log)
    state["config"] = asdict(cfg)
    state["version"] = "v9"
    (out / "state.json").write_text(json.dumps(state, indent=1))
    log(f"prepared {out} as a v9 run ({mode}) from {src}, after generation {state['gen_done']}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="the earlier run's folder (as on GitHub is enough with --pack)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["continue", "best"], default="continue")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=60.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--pack", default=None, help="a continuation pack (helix9/pack.py)")
    ap.add_argument("--replay", default=None, help="the replay's folder (codebook.json, coords.jsonl)")
    a = ap.parse_args(argv)
    prepare(a.src, a.out, a.mode, a.seed, a.budget, a.label, pack=a.pack, replay=a.replay)


if __name__ == "__main__":
    main()
