"""Start a v8 run from an earlier run (v7, v4.7 or v4): the warm start (docs/V8_JOB.md).

    python -m helix8.warm --src runs/v7warm/v7-s1 --out runs/v8warm/v8-s1 --mode continue --seed 1 --budget 60

then `python -m helix8.run --out runs/v8warm/v8-s1 --gens 390` resumes it as a v8 run.

As helix7/warm.py (programs, constructions, findings, history and plans kept; generations continue the source's
numbering; the warm start counts as a record), plus what v8 needs from a v7 run: its tracks (so they become the first
entries on the map), its noise measurement, and any signatures and hills it already has. The first v8 generation
registers the hills the run knows: every earlier track's best is placed.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, fields
from pathlib import Path

from helix7.warm import prepare as prepare7
from helix8.run import Config


def prepare(src, out, mode="continue", seed=1, budget=60.0, label="", **cfg_kw):
    src, out = Path(src), Path(out)
    if (out / "state.json").exists():
        print(f"{out} exists already: nothing done (it resumes as it is)")
        return out
    prepare7(src, out, mode, seed, budget, label)
    state = json.loads((out / "state.json").read_text())
    known = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in state["config"].items() if k in known and k != "condition"})
    for k, v in cfg_kw.items():
        setattr(cfg, k, v)
    if mode == "continue":
        src_state = json.loads((src / "state.json").read_text()) if (src / "state.json").exists() else {}
        for k, v in (src_state.get("config") or {}).items():        # the source's settings carry over (the floor, ...)
            if k in known and k not in ("condition", "seed", "gens", "label", "budget") and k not in cfg_kw:
                setattr(cfg, k, v)
        for f in ("tracks.jsonl", "noise.json", "signatures.jsonl", "hills.jsonl"):
            if (src / f).exists():
                shutil.copy(src / f, out / f)
    state["config"] = asdict(cfg)
    state["version"] = "v8"
    (out / "state.json").write_text(json.dumps(state, indent=1))
    print(f"prepared {out} as a v8 run ({mode}) from {src}, after generation {state['gen_done']}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="the earlier run's folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["continue", "best"], default="continue")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=60.0)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    prepare(a.src, a.out, a.mode, a.seed, a.budget, a.label)


if __name__ == "__main__":
    main()
