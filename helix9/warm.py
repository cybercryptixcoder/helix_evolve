"""Start a v9 run from an earlier run (v8, v7, v4.7 or v4): the warm start (docs/V9_JOB.md).

    python -m helix9.warm --src results/v8warm/v8-s1 --out runs/v9warm/v9-s1 \\
        --pack results/v8warm/v8-s1/pack --replay results/v9warm/replay --seed 1 --budget 60

then `python -m helix9.run --out runs/v9warm/v9-s1 --gens 800` resumes it as a v9 run.

As helix8/warm.py (every program, finding, track, hill and the history kept; generations continue the source's
numbering; the warm start counts as a record), plus:
- the **continuation pack** (helix9/pack.py) restored: the constructions it holds and every program's signature, so
  the source can be the run folder as pushed to GitHub, with no local files;
- the **replay's map** (helix9/replay.py), if given: its codebook and the coordinates of the programs it read, so the
  design map starts with what the earlier run already knows;
- **the race, applied retroactively** to the earlier run's explorations (restarts, bold experiments, flips): each is
  judged at the rungs its curve reached, against the others, as v9 would have judged it. Those v9 would have kept
  climbing are live again; the rest stay paused (never closed).
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, fields
from pathlib import Path

from helix8.warm import prepare as prepare8
from helix9.pack import jl, restore
from helix9.race import Race, record_curve
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
    status = {}
    for t in sorted(tracks, key=lambda t: t.get("opened") or 0):
        if t.get("kind") not in RETRO_KINDS or t["id"] == last.get("main") or t.get("race"):
            continue
        race.start(t, bracket=0)
        t["served"] = t.get("opened")
        for _ in range(len(cfg.race_rungs)):
            if t["race"]["status"] != "running" or (t.get("exps") or 0) < t["race"]["budget"]:
                break
            race.decide(t, tracks, last.get("gen"), effort=t["race"]["budget"])
        status[t["race"]["status"]] = status.get(t["race"]["status"], 0) + 1
    last["tracks"] = tracks
    (out / "tracks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[:-1]) + json.dumps(last) + "\n")
    live = [t["id"] for t in tracks if (t.get("race") or {}).get("status") == "running"]
    log(f"the race, applied to the earlier explorations: {status}; racing again: {', '.join(live[:12]) or 'none'}")
    return status


def prepare(src, out, mode="continue", seed=1, budget=60.0, label="", pack=None, replay=None, log=print, **cfg_kw):
    src, out = Path(src), Path(out)
    if (out / "state.json").exists():
        log(f"{out} exists already: nothing done (it resumes as it is)")
        return out
    prepare8(src, out, mode, seed, budget, label)
    if pack and Path(pack).is_dir() and (Path(pack) / "manifest.json").exists():
        restore(pack, out, log=log)
    state = json.loads((out / "state.json").read_text())
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
