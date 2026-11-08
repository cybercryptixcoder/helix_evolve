"""Run Helix on one problem.

    python -m lean.run --problem circles --out runs/lean/c1 --rounds 50
    python -m lean.run --out runs/lean/c1 --rounds 80          # resumes (state.json is there), runs to round 80
    python -m lean.run --problem circles --out /tmp/x --rounds 2 --fake    # no model calls (crash test only)

    python -m lean.run --problem helix_vrp.lean_adapter --param blackbox=... --out ...   # an adapter outside this repo

--rounds is the number of generations. --planned and --mutations are v4's --deep and --wide (3 each).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time

from lean.loop import Config, Run


def fake_answer(role, system, user):
    """Plausible replies with no model: random local search programs, plans on real ids."""
    if role == "planner":
        ids = re.findall(r"\bp\d{4}\b", user) or ["p0001"]
        k = int(re.search(r"Give exactly (\d+)", user).group(1))
        return "```json\n" + json.dumps({"analysis": "fake", "experiments": [
            {"base": ids[0], "hypothesis": f"fake {i}", "change": f"jitter {i}", "prediction": "small gain"}
            for i in range(k)]}) + "\n```"
    tag = random.randint(1, 10 ** 9)
    return f'''```python
import numpy as np, time
# fake {tag}
def construct(budget_seconds, start):
    rng = np.random.default_rng({tag} % 2**32)
    x = np.asarray(start, dtype=float).copy()
    x = x * (1 - 1e-3) if x.ndim == 2 else x * (1 + 0.01 * rng.random(x.shape))
    return x
```
SUMMARY: fake jitter'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--problem", default="circles")
    ap.add_argument("--param", action="append", default=[], help="a problem parameter, e.g. n=26 or max_n=50000")
    ap.add_argument("--rounds", type=int, default=50)
    ap.add_argument("--planned", type=int, default=3)
    ap.add_argument("--mutations", type=int, default=3)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--effort", default="low", help="the planner's thinking effort")
    ap.add_argument("--fake", action="store_true")
    a = ap.parse_args(argv)
    params = {k: int(v) if v.lstrip("-").isdigit() else v for k, v in (p.split("=", 1) for p in a.param)}
    cfg = Config(problem=a.problem, params=params, rounds=a.rounds, planned=a.planned, mutations=a.mutations,
                 budget=a.budget, seed=a.seed, effort=a.effort)
    llm = None
    if a.fake:
        from lean.llm import FakeLLM
        llm = FakeLLM(fake_answer)
    run = Run(a.out, cfg, llm=llm, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()
    return 0


if __name__ == "__main__":
    sys.exit(main())
