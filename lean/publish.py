"""Copy an experiment's runs into results/lean/<experiment>/ for GitHub: everything a reader needs to check a claim,
nothing that is only bulk.

    python -m lean.publish experiments/lean/e1_core.json

Per run: programs.jsonl (every program: code, parent, idea, result), rounds.jsonl, notes.jsonl, state.json,
summary.json, best.py, best.npy, calls.jsonl.gz (every model call, prompt and reply, compressed) and the
constructions of the programs that set a record (records/). Plus the experiment's report (report.md, curves.csv,
curves.png).
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

from lean.bench import ROOT, jl, report

FILES = ("programs.jsonl", "rounds.jsonl", "notes.jsonl", "state.json", "summary.json", "best.py", "best.npy",
         "run.log")


def publish(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    src = ROOT / "runs" / "lean" / spec["name"]
    dst = ROOT / "results" / "lean" / spec["name"]
    for run in sorted(p for p in src.glob("*") if p.is_dir()):
        out = dst / run.name
        (out / "records").mkdir(parents=True, exist_ok=True)
        for f in FILES:
            if (run / f).exists():
                shutil.copy2(run / f, out / f)
        if (run / "calls.jsonl").exists():
            with (run / "calls.jsonl").open("rb") as fi, gzip.open(out / "calls.jsonl.gz", "wb", compresslevel=6) as fo:
                shutil.copyfileobj(fi, fo)
        best = None
        for p in jl(run / "programs.jsonl"):
            if p["valid"] and (best is None or p["score"] > best):
                best = p["score"]
                c = run / "constructions" / f"{p['id']}.npy"
                if c.exists():
                    shutil.copy2(c, out / "records" / c.name)
    report(spec, dst)
    return dst


if __name__ == "__main__":
    for s in sys.argv[1:]:
        print(publish(s))
