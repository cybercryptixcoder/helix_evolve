"""Tests for Helix v4.7 (helix47/): alternatives, the noise floor, stall detection, the challenger line, the step
slot, the balanced map, resuming, the problem view, and the prompts.

    python -m pytest tests/test_helix47.py -q
"""
import json
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix47-slots-"))

from helix4.archive import Program                       # noqa: E402
from helix4.llm import FakeLLM                           # noqa: E402
from helix4.problems import ac2                          # noqa: E402
from helix47 import prompts as P                         # noqa: E402
from helix47.evaluate import evaluate, same_shape        # noqa: E402
from helix47.memory import outcome                       # noqa: E402
from helix47.run import Config, ProblemView, Run, fake_answer  # noqa: E402

PROBLEM = ProblemView(ac2, 1_000_000)


def run(tmp, gens, **kw):
    cfg = Config(gens=gens, budget=2.0, **kw)
    r = Run(tmp, cfg, llm=FakeLLM(fake_answer), gens=gens, log=lambda m: None)
    r.go()
    return r


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------------------------- the evaluator
ALT = '''import numpy as np
def construct(budget_seconds, start):
    return {"best": np.asarray(start, float), "alternative": np.array([1.0, 0.2, 1.0, 0.4])}
'''
SAME = '''import numpy as np
def construct(budget_seconds, start):
    return {"best": np.asarray(start, float), "alternative": 2 * np.asarray(start, float)}
'''
PLAIN = '''import numpy as np
def construct(budget_seconds, start):
    return np.asarray(start, float)
'''
BAD = '''def construct(budget_seconds, start):
    return {"alternative": [1.0]}
'''


def test_an_alternative_is_scored_and_a_plain_array_still_works():
    start = np.ones(30)
    r = evaluate(PROBLEM, ALT, start, 2)
    assert r["valid"] and abs(r["score"] - 2 / 3) < 1e-12
    assert r["alternative"] is not None and abs(r["alternative"]["score"] - ac2.score(np.array([1, .2, 1, .4]))) < 1e-12
    assert evaluate(PROBLEM, PLAIN, start, 2)["alternative"] is None
    assert evaluate(PROBLEM, SAME, start, 2)["alternative"] is None       # the same function, scaled: not new
    bad = evaluate(PROBLEM, BAD, start, 2)
    assert not bad["valid"] and "best" in bad["error"]


def test_same_shape():
    assert same_shape([1, 2, 3], [2, 4, 6]) and not same_shape([1, 2, 3], [1, 2, 4]) and not same_shape([1], [1, 1])


# ---------------------------------------------------------------------------------------------- the noise floor
def test_gains_below_the_floor_are_no_gain():
    cfg = Config()
    p = Program(id="p1", gen=1, role="deep", parent="p0", intent="", code="", valid=True, score=0.94 + 1e-9,
                start_score=0.94, delta=1e-9)
    assert outcome(p, cfg) == "no gain"
    p.delta = p.score = 2e-6
    p.score = 0.94 + 2e-6
    assert outcome(p, cfg) == "gain"


def test_stall_detection(tmp_path):
    r = Run(tmp_path, Config(), llm=FakeLLM(fake_answer), log=lambda m: None)
    rows = [0.6667, 0.80, 0.85, 0.88, 0.88, 0.88001, 0.88001, 0.88002]
    (tmp_path / "history.jsonl").write_text("".join(json.dumps({"gen": i, "best": b}) + "\n" for i, b in enumerate(rows)))
    # windows of 3 generations: 5 vs 2 (+0.03) is moving; 6 vs 3 and 7 vs 4 are stalled: flat since generation 3
    assert r.stalled_for() == 4
    (tmp_path / "history.jsonl").write_text("".join(json.dumps({"gen": i, "best": b}) + "\n" for i, b in enumerate(rows[:5])))
    assert r.stalled_for() == 0


# ---------------------------------------------------------------------------------------------- whole runs
def test_a_run_that_climbs_is_v4(tmp_path):
    r = run(tmp_path / "climb", 4, stall_gain=0.0)        # never stalled
    hist = jl(tmp_path / "climb" / "history.jsonl")
    assert [h["gen"] for h in hist] == [0, 1, 2, 3, 4]
    assert all(h.get("challenger") is None and not h.get("step") for h in hist[1:])
    plans = jl(tmp_path / "climb" / "plans.jsonl")
    assert all(len(p["experiments"]) == 3 for p in plans)
    assert sum(1 for p in r.archive.programs.values() if p.role == "alt") > 0      # alternatives are kept


def test_a_stalled_run_gets_a_challenger_line_and_a_step_slot(tmp_path):
    out = tmp_path / "stall"
    r = run(out, 6, stall_gain=1.0, stall_gens=1, line_patience=2, line_max_gens=3)
    hist = jl(out / "history.jsonl")
    lines = jl(out / "lines.jsonl")
    plans = jl(out / "plans.jsonl")
    ch = [h for h in hist if h.get("challenger")]
    assert ch and ch[0]["gen"] == 2
    # one deep slot went to the line, and the main plan had one step-change experiment with twice the budget
    p2 = [p for p in plans if p["gen"] == 2][0]
    assert len(p2["experiments"]) == 3 and p2["experiments"][-1]["line"] == "C1"
    assert sum(1 for e in p2["experiments"] if e.get("step")) == 1
    step_child = r.archive.programs[hist[2]["step"][0]]
    assert step_child.intent.startswith("[step]") and step_child.plan.get("step")
    line_child = r.archive.programs[ch[0]["challenger"]["child"]]
    assert line_child.intent.startswith("[challenger C1]") and line_child.plan["line"] == "C1"
    # the challenger's planner saw its own view, without the overall record
    trace = [json.loads(l) for l in (out / "trace.jsonl").read_text().splitlines()]
    cview = [t for t in trace if t["role"] == "challenger"][0]["user"]
    assert "challenger line C1" in cview and "The best program so far" not in cview and "Starting your line" in cview
    # lines end and new ones start while the search stays stalled
    closed = lines[-1]["closed"]
    assert closed and all(c.get("why") for c in closed)
    s = json.loads((out / "summary.json").read_text())
    assert s["lines"] and s["alternatives"] > 0


def test_resume_keeps_the_line(tmp_path):
    out = tmp_path / "res"
    run(out, 3, stall_gain=1.0, stall_gens=1, line_patience=9, line_max_gens=9)
    a = jl(out / "lines.jsonl")[-1]["active"]
    assert a and re.fullmatch(r"C\d+", a["id"])
    r = Run(out, llm=FakeLLM(fake_answer), gens=5, log=lambda m: None)
    assert r.line["id"] == a["id"] and r.cfg.stall_gain == 1.0     # the line and the v4.7 settings survive a resume
    r.go()
    hist = jl(out / "history.jsonl")
    assert [h["gen"] for h in hist] == [0, 1, 2, 3, 4, 5]
    assert hist[4]["challenger"] is not None and hist[4]["challenger"]["line"].startswith("C")


# ---------------------------------------------------------------------------------------------- the map
def test_the_map_is_balanced_and_failures_are_scoped(tmp_path):
    r = run(tmp_path / "m", 1)
    mem = r.memory
    base = r.archive.best()
    ids = [p.id for p in r.archive.programs.values() if p.parent == base.parent or p.parent]
    for i in range(60):
        mem._append({"op": "new", "id": f"F{len(mem.events) + 1}", "gen": 1, "kind": "fails",
                     "claim": f"failure {i} is confirmed saturated", "evidence": ids[:1], "links": []})
    for i in range(5):
        mem._append({"op": "new", "id": f"F{len(mem.events) + 1}", "gen": 1, "kind": "works",
                     "claim": f"works {i}", "evidence": ids[:1], "links": []})
    mem.rebuild()
    text, shown = mem.findings_view()
    assert text.count("[fails") <= r.cfg.map_fails
    assert text.count("[works") == 5 + sum(1 for f in mem.findings.values() if f["kind"] == "works") - 5
    assert "more failures tried on the construction scoring" in text and "not about the problem" in text
    assert "tried on p" in text


def test_the_header_has_no_countdown_and_states_the_room(tmp_path):
    r = run(tmp_path / "h", 1)
    h = r.memory.header(2)
    assert "# Generation 2\n" in h and " of 1" not in h
    assert "proven upper bound is 1" in h and "% of the range is still open" in h


# ---------------------------------------------------------------------------------------------- problem and prompts
def test_the_problem_view_raises_the_size_limit_without_touching_the_module():
    big = np.ones(500_000)
    assert ac2.check(big)[0] is None
    assert PROBLEM.check(big)[0] is not None
    assert ac2.MAX_N == 200_000 and ac2.check(big)[0] is None
    assert "1,000,000" in PROBLEM.DESCRIPTION and "200,000" not in PROBLEM.DESCRIPTION
    assert "main way progress is made" not in PROBLEM.DESCRIPTION
    assert "main way progress is made" in ac2.DESCRIPTION


def test_prompts_carry_no_problem_specific_hints():
    texts = [v for k, v in vars(P).items() if k.isupper() and isinstance(v, str)]
    words = r"autoconv|convolution|spike|comb|plateau|softmax|L-BFGS|Dinkelbach|resolution|upsampl|heights? of|saturat"
    for t in texts:
        found = re.findall(words, t, re.I)
        assert not found or found == ["heights"], found


def test_v4_prompts_are_unchanged_by_importing_v47():
    from helix4 import prompts as P4
    assert "confirm or refute" in P4.RESEARCHER_SYSTEM and "alternative" not in P4.CODER_SYSTEM
