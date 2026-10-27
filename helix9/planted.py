"""A planted problem for the real v9 run (an integration test, not a benchmark): the simulator's world
(helix9/sim.py) behind the evaluator, and a fake model that writes programs with an explicit design.

    run = helix9.run.Run(out, Config(problem="planted"), llm=FakeLLM(planted_answer), problem=PlantedProblem(spec))

- A program is a few lines with `DESIGN = {...}` (option names per axis) and `X = [...]` (the world's indices). Its
  construction is [effort, x_1, ..., x_d]: effort grows by one when it keeps its base's design, and is mostly reset
  when it changes it (the simulator's rules). The score is the world's height minus the closing gap, plus a little
  deterministic noise.
- The fake coder obeys a drop's, flip's or ablation's blueprint (each asked-for decision lands with probability
  `fidelity`), otherwise polishes (keeps the design) or tries one change of its own. The fake annotator reads DESIGN
  (helix9/annotate.py, fake_reply), so read-back, the codebook, the model and the race all run on real data.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

import numpy as np

from helix9.annotate import fake_reply
from helix9.run import fake_answer as fake_answer9
from helix9.sim import Spec, World

PROGRAM = '''import numpy as np
DESIGN = {design}
X = {x}


def construct(budget_seconds, start):
    x = np.array(X, dtype=float)
    if start is None or len(start) != len(X) + 1:
        e = 1.0
    else:
        moved = int(np.sum(np.asarray(start[1:]) != x))
        e0 = float(start[0])
        e = e0 + 1 if moved == 0 else (e0 * 0.6 + 1 if moved == 1 else min(e0 * 0.3, 2.0) + 1)
    return np.concatenate(([e], x))
'''


class PlantedProblem:
    NAME = "planted"
    TITLE = "A planted design problem (a test)"
    MAX_N = 1000

    def __init__(self, spec: Spec | None = None):
        self.spec = spec or Spec(warm=False)
        self.world = World(self.spec)
        self.DESCRIPTION = ("## The problem: a planted design problem (a test)\n\nWrite `construct(budget_seconds, start)`"
                            " returning a numpy array. Higher is better.\n")
        x0 = list(self.world.trap)
        self.CODE_ZERO = PROGRAM.format(design=json.dumps(self.design_of(x0)), x=json.dumps(x0))

    def design_of(self, x):
        return {f"D{i + 1}": f"option {v + 1}" for i, v in enumerate(x)}

    def check(self, arr):
        a = np.asarray(arr, dtype=float).ravel()
        if a.size != self.spec.d + 1 or not np.all(np.isfinite(a)) or np.any(a < 0):
            return None, "not a planted construction"
        return a, ""

    def score(self, h):
        x = tuple(int(v) for v in h[1:])
        noise = (int(hashlib.sha1(h.tobytes()).hexdigest()[:8], 16) / 0xFFFFFFFF - 0.5) * 2 * self.spec.noise
        return float(self.world.height(x) - self.spec.gap * np.exp(-float(h[0]) / self.world.tau(x)) + noise)

    def feedback(self, h, start_h, info, budget):
        s = self.score(h)
        lines = [f"score {s:.6f}" + (f" (its start scored {self.score(start_h):.6f})" if start_h is not None else "")]
        return s, lines


def _design(code):
    m = re.search(r"^X = (\[[^\]]*\])", code or "", re.M)
    return json.loads(m.group(1)) if m else None


def make_answer(problem: PlantedProblem, fidelity=0.8, seed=1):
    rng = random.Random(seed)
    w = problem.world

    def answer(role, system, user):
        if role == "annotator":
            return fake_reply("", user)
        if role in ("coder", "mutator"):
            blocks = re.findall(r"```python\n(.*?)```", user, re.S)
            base = _design(blocks[0]) if blocks else None
            x = list(base) if base else list(w.trap)
            # blueprint lines: "- <axis id> (<axis name>): <option>"; the world's decisions are named D1, D2, ...
            asked = re.findall(r"^- A\d+ \(([^)]*)\): (.+)$", user, re.M)
            if asked and ("builds a specific design" in user or "changes exactly one design decision" in user
                          or "undoes one design decision" in user):
                for name, what in asked:
                    m = re.fullmatch(r"D(\d+)", name.strip())
                    i = int(m.group(1)) - 1 if m else len(x)
                    if i >= len(x) or rng.random() > fidelity:
                        continue
                    m = re.match(r"option (\d+)", what)
                    if m:
                        x[i] = int(m.group(1)) - 1
                    else:                                  # "a new option": any other index
                        x[i] = rng.choice([v for v in range(problem.spec.k) if v != x[i]])
            elif rng.random() < 0.3:
                i = rng.randrange(len(x))
                x[i] = rng.choice([v for v in range(problem.spec.k) if v != x[i]])
            code = PROGRAM.format(design=json.dumps(problem.design_of(x)), x=json.dumps(x))
            return f"```python\n{code}```\nSUMMARY: design {x}"
        if role == "cartographer":
            ids = {m.group(2).strip(): m.group(1) for m in re.finditer(r"^(A\d+): (.+)$", user, re.M)}
            if "List the design decisions" in user:              # a scan names two of the world's decisions
                k = problem.spec.k
                picks = rng.sample(range(problem.spec.d), 2)
                return json.dumps({"shared": [{"decision": f"D{i + 1}", "everyone": f"option {1 + rng.randrange(k)}",
                                               "alternatives": [f"option {1 + rng.randrange(k)}"]} for i in picks]})
            if "design decisions named elsewhere" in user:      # matched by name
                items = re.findall(r"^(\d+)\. (D\d+)", user.split("Below are design decisions")[-1], re.M)
                return json.dumps({"matches": [{"item": int(n), "axis": ids.get(name, "new"), "question": name}
                                               for n, name in items]})
            if "What design decision differs" in user:          # a decision the codebook lacks, read off DESIGN
                designs = {pid: json.loads(d) for pid, d in
                           re.findall(r"^## (p\d{4})\n```python\n[^`]*?DESIGN = (\{[^}]*\})", user, re.M)}
                missing = [f"D{i + 1}" for i in range(problem.spec.d) if f"D{i + 1}" not in ids]
                if missing and designs:
                    name = missing[0]
                    return json.dumps({"decision": name, **{pid: d.get(name, "?") for pid, d in designs.items()}})
        return fake_answer9(role, system, user)
    return answer
