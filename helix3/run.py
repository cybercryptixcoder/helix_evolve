"""Run Helix v3 on one problem.

    python -m helix3.run binpack2d --generations 5
    python -m helix3.run tsp --generations 3 --label try-1
    python -m helix3.run binpack2d --generations 2 --fake      # crash test, no model calls

Runs are written to runs/<problem>/<timestamp>[-label]/ (trace.jsonl, ledger.json, history.json, summary.json,
champion.py, strategy/). Open the dashboard with `python -m ui`.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from .engine import ROOT, Engine, Strategy
from .llm import LLM, FakeLLM
from .problem import load_problem


def fake_answer(problem):
    rng = random.Random(0)
    feats = problem.example_features or ["import numpy as np\n\ndef feature(*args):\n    return 0.0\n"]

    def answer(role, system, user):
        if role == "navigator":
            ids = re.findall(r"- (f\d{3}) ", user)
            return json.dumps({"new_approaches": [{"title": f"idea {rng.randint(0, 999)}", "description": "test"}],
                               "research": [{"approach": "new: fake approach", "mode": "explore", "why": "test"}],
                               "mutate": {"vary": ids[:2], "fresh": 2}, "combine": [], "prune": []})
        if role == "researcher":
            metric = next(iter(problem.metric_notes), "gap")
            return "```json\n" + json.dumps({"experiments": [
                {"approach": "new: fake approach", "kind": k, "name": f"fake_{k}_{rng.randint(0, 99)}",
                 "hypothesis": "test", "feature": "test", "prediction": {"family": problem.families[0], "metric": metric,
                                                                          "direction": "down"}} for k in ("probe", "improve")]}) + "\n```"
        if role == "prover":
            return '{"certificates": []}'
        code = rng.choice(feats)
        if rng.random() < 0.5:   # perturb so not everything is a duplicate
            code = code.replace('"""', f'"""v{rng.randint(0, 9999)} ', 1)
        return f"```python\n{code}```\nname: fake_{rng.randint(0, 999)}"

    return answer


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("problem")
    ap.add_argument("--generations", "-g", type=int, default=5)
    ap.add_argument("--label", default="")
    ap.add_argument("--strategy", default=None, help="a strategy folder (default helix3/strategy)")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fake", action="store_true", help="no model calls: a crash test")
    ap.add_argument("--out", default=None, help="run folder (default runs/<problem>/<timestamp>)")
    a = ap.parse_args(argv)
    problem = load_problem(a.problem)
    stamp = time.strftime("%Y%m%d-%H%M%S") + (f"-{a.label}" if a.label else "")
    out = Path(a.out) if a.out else ROOT / "runs" / problem.name / stamp
    llm = FakeLLM(fake_answer(problem)) if a.fake else LLM()
    eng = Engine(problem, out, llm, Strategy(a.strategy), workers=a.workers, seed=a.seed, label=a.label)
    print(f"Helix v3 · {problem.title} · {a.generations} generations → {out}")
    eng.run(a.generations)
    s = json.loads((out / "summary.json").read_text())
    print(f"done: progress {s['champion']['progress']}% train, {s['champion'].get('valid_progress')}% valid, "
          f"test {((s.get('test') or {}).get('progress'))}% | {s['calls']} calls")


if __name__ == "__main__":
    main()
