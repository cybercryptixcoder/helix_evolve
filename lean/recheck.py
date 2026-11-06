"""Re-check every valid program of an experiment with the problem's current checker, and record the ones that now
fail in each run's recheck.json (the run's own records are never rewritten; reports read recheck.json).

    python -m lean.recheck experiments/lean/e1_core.json

Made for circle packing: experiments 1 and 2 checked overlaps in floating point, which let some results through that
overlap by a hair in exact arithmetic (docs/LEAN_RESULTS.md); the checker is now exact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from lean.bench import ROOT, jl
from lean.problems import load


def recheck(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    problem = load(spec["problem"], **(spec.get("params") or {}))
    for run in sorted(p for p in (ROOT / "runs" / "lean" / spec["name"]).glob("*") if p.is_dir()):
        bad = {}
        for p in jl(run / "programs.jsonl"):
            c = run / "constructions" / f"{p['id']}.npy"
            if p["valid"] and c.exists():
                x, why = problem.check(np.load(c))
                if x is None:
                    bad[p["id"]] = why
        (run / "recheck.json").write_text(json.dumps({"checker": "exact", "invalid": bad}, indent=1))
        print(f"{run.name}: {len(bad)} results invalid on re-check")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        recheck(s)
