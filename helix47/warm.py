"""Start v4.7 runs from an earlier run's best: the warm-start experiment (docs/V47_WARM.md).

    python -m helix47.warm --src <v4 run folder> --out runs/v47warm/v47-s1 --mode continue --seed 1 --budget 60
    python -m helix47.warm --src <v4 run folder> --out runs/v47warm/v47-s2 --mode best --seed 2 --budget 60

then `python -m helix47.run --out runs/v47warm/v47-s1 --gens 190` resumes it as a v4.7 run.

- **continue:** generation 151 of the same run, under v4.7.
  - It keeps every program, constructions, findings and the history.
  - All earlier programs form line L1, with a fresh start for its stall count, so it gets `line_patience` generations
    under v4.7 before it can close.
  - When it closes, new lines start from alternatives, other branches of the 150-generation tree, or Code Zero.
- **best:** the best program and its construction, with a fresh Atlas and nothing else.
  - The archive holds Code Zero (p0001, for fresh lines) and the best program (p0002, with its construction).
  - Line L1 starts from p0002.
  - Generations are numbered from 151 too, so both runs can share one generation count.

The source folder needs programs.jsonl and best.npy. Its constructions/ folder is used if present; without it, only
the best program's construction is known, and an experiment based on another old program starts from nothing.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np

from helix4.archive import Program
from helix47.run import Config


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()] if Path(p).exists() else []


def prepare(src, out, mode, seed=1, budget=60.0, label=""):
    src, out = Path(src), Path(out)
    if (out / "state.json").exists():
        print(f"{out} exists already: nothing done (it resumes as it is)")
        return out
    progs = [Program(**p) for p in jl(src / "programs.jsonl")]
    if not progs:
        raise SystemExit(f"{src}/programs.jsonl has no programs")
    best = max((p for p in progs if p.valid and p.score is not None), key=lambda p: p.score)
    h_best = np.load(src / "best.npy") if (src / "best.npy").exists() else None
    gen_done = max(p.gen for p in progs)
    out.mkdir(parents=True, exist_ok=True)
    (out / "constructions").mkdir(exist_ok=True)
    cfg = Config(seed=seed, gens=gen_done, budget=budget, label=label)
    if mode == "continue":
        with (out / "programs.jsonl").open("w") as f:
            for p in progs:
                f.write(json.dumps(asdict(p)) + "\n")
        n = 0
        if (src / "constructions").is_dir():
            for c in (src / "constructions").glob("*.npy"):
                shutil.copy(c, out / "constructions" / c.name)
                n += 1
        if h_best is not None:
            np.save(out / "constructions" / f"{best.id}.npy", h_best)
        for f in ("findings.jsonl", "history.jsonl", "plans.jsonl"):
            if (src / f).exists():
                shutil.copy(src / f, out / f)
        line = {"id": "L1", "root": best.id, "source": f"the {gen_done}-generation v4 run (all its programs)",
                "kind": "seed", "started": gen_done + 1, "status": "active", "best": best.score, "best_id": best.id,
                "curve": [[gen_done, best.score]], "ended": None, "why": None}
        print(f"continue: {len(progs)} programs, {n} constructions copied, best {best.id} {best.score:.9f}, "
              f"{len(jl(src / 'findings.jsonl'))} findings events")
    elif mode == "best":
        seed_p = next((p for p in progs if p.role == "seed"), None)
        if seed_p is None or h_best is None:
            raise SystemExit("mode best needs the source's Code Zero (programs.jsonl) and best.npy")
        p1 = Program(**{**asdict(seed_p), "id": "p0001", "gen": 0, "parent": None})
        p2 = Program(**{**asdict(best), "id": "p0002", "gen": 0, "role": "warm", "parent": "p0001",
                        "intent": f"warm start: the best program of the {gen_done}-generation v4 run ({best.id}), "
                                  f"with its construction", "plan": {"line": "L1"}, "delta": None,
                        "start_score": None, "diff": ""})
        with (out / "programs.jsonl").open("w") as f:
            for p in (p1, p2):
                f.write(json.dumps(asdict(p)) + "\n")
        sc = src / "constructions" / f"{seed_p.id}.npy"
        if sc.exists():
            shutil.copy(sc, out / "constructions" / "p0001.npy")
        np.save(out / "constructions" / "p0002.npy", h_best)
        (out / "history.jsonl").write_text(json.dumps({"gen": gen_done, "best": best.score, "best_id": "p0002",
                                                       "seconds": 0, "warm_start": True}) + "\n")
        line = {"id": "L1", "root": "p0002", "source": "the warm start (the best program of the earlier run)",
                "kind": "seed", "started": gen_done + 1, "status": "active", "best": best.score, "best_id": "p0002",
                "curve": [[gen_done, best.score]], "ended": None, "why": None}
        print(f"best: Code Zero and {best.id} ({best.score:.9f}) as p0002; a fresh Atlas")
    else:
        raise SystemExit(f"unknown mode {mode}")
    (out / "lines.jsonl").write_text(json.dumps({"gen": gen_done, "lines": [line]}) + "\n")
    (out / "state.json").write_text(json.dumps({"gen_done": gen_done, "config": asdict(cfg), "warm": mode,
                                                "warm_source": str(src)}, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="the earlier run's folder (programs.jsonl, best.npy, constructions/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["continue", "best"], required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=60.0)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    prepare(a.src, a.out, a.mode, a.seed, a.budget, a.label)


if __name__ == "__main__":
    main()
