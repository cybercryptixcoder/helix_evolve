"""Start a v7 run from an earlier run (v4 or v4.7): the warm start (docs/V7_JOB.md).

    python -m helix7.warm --src runs/v47warm/v47-s2 --out runs/v7warm/v7-s1 --mode continue --seed 1 --budget 60
    python -m helix7.warm --src <run folder> --out runs/v7warm/v7-s2 --mode best --seed 2 --budget 60

then `python -m helix7.run --out runs/v7warm/v7-s1 --gens 290` resumes it as a v7 run.

- **continue:** the next generation of the same run, under v7. Every program, construction and finding is kept, and
  the history, so the run's own record gaps set its typical gap. A v4.7 run's lines become paused side tracks (the
  line holding the best program is the main track); a v4 run is one track. The warm start counts as a record, so the
  first generations are main only, and exploration opens if the record then stalls longer than usual.
- **best:** the best program and its construction, with a fresh Atlas: Code Zero (p0001) and the best program (p0002).

Generations continue the source's numbering. The source folder needs programs.jsonl; its constructions/ folder is
used if present (without it, only the best program's construction is known, from best.npy).
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np

from helix4.archive import Program
from helix7.run import Config


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()] if Path(p).exists() else []


def prepare(src, out, mode, seed=1, budget=60.0, label="", **cfg_kw):
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
    cfg = Config(seed=seed, gens=gen_done, budget=budget, label=label, **cfg_kw)
    if mode == "continue":
        with (out / "programs.jsonl").open("w") as f:
            for p in progs:
                f.write(json.dumps(asdict(p)) + "\n")
        n = 0
        if (src / "constructions").is_dir():
            for c in (src / "constructions").glob("*.npy"):
                shutil.copy(c, out / "constructions" / c.name)
                n += 1
        if h_best is not None and not (out / "constructions" / f"{best.id}.npy").exists():
            np.save(out / "constructions" / f"{best.id}.npy", h_best)
        for f in ("findings.jsonl", "history.jsonl", "plans.jsonl", "lines.jsonl"):
            if (src / f).exists():
                shutil.copy(src / f, out / f)
        hist = jl(out / "history.jsonl")
        if hist:      # an unfinished generation's row would be dropped on resume anyway; keep the file consistent
            (out / "history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in hist if r.get("gen", -1) <= gen_done))
        valid = sum(1 for p in progs if p.valid)
        rows = jl(out / "lines.jsonl")
        print(f"continue: {len(progs)} programs ({valid} valid), {n} constructions copied"
              f"{' (no constructions/ folder: only the best program starts from its construction)' if n == 0 else ''}, "
              f"best {best.id} {best.score:.9f}, {len(jl(out / 'findings.jsonl'))} findings events, "
              f"{len(rows[-1]['lines']) if rows else 0} lines of a v4.7 run")
    elif mode == "best":
        seed_p = next((p for p in progs if p.role == "seed"), None)
        if seed_p is None or h_best is None:
            raise SystemExit("mode best needs the source's Code Zero (programs.jsonl) and best.npy")
        p1 = Program(**{**asdict(seed_p), "id": "p0001", "gen": 0, "parent": None, "plan": {}})
        p2 = Program(**{**asdict(best), "id": "p0002", "gen": 0, "role": "warm", "parent": "p0001",
                        "intent": f"warm start: the best program of the {gen_done}-generation run ({best.id}), with its "
                                  f"construction", "plan": {"track": "T1"}, "delta": None, "start_score": None,
                        "diff": ""})
        with (out / "programs.jsonl").open("w") as f:
            for p in (p1, p2):
                f.write(json.dumps(asdict(p)) + "\n")
        sc = src / "constructions" / f"{seed_p.id}.npy"
        if sc.exists():
            shutil.copy(sc, out / "constructions" / "p0001.npy")
        np.save(out / "constructions" / "p0002.npy", h_best)
        (out / "history.jsonl").write_text(json.dumps({"gen": gen_done, "best": best.score, "best_id": "p0002",
                                                       "seconds": 0, "warm_start": True}) + "\n")
        print(f"best: Code Zero and {best.id} ({best.score:.9f}) as p0002; a fresh Atlas")
    else:
        raise SystemExit(f"unknown mode {mode}")
    (out / "state.json").write_text(json.dumps({"gen_done": gen_done, "config": asdict(cfg), "version": "v7",
                                                "warm": mode, "warm_gen": gen_done, "warm_source": str(src)}, indent=1))
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
