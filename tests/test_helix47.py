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


# ---------------------------------------------------------------------------------------------- lines
def test_a_climbing_run_is_v4_shaped(tmp_path):
    r = run(tmp_path / "climb", 4, stall_gain=0.0)        # a line never closes
    hist = jl(tmp_path / "climb" / "history.jsonl")
    assert [h["gen"] for h in hist] == [0, 1, 2, 3, 4]
    assert all(h["allocation"] == {"L1": 3} and not h["line_events"] for h in hist[1:])
    plans = jl(tmp_path / "climb" / "plans.jsonl")
    assert all(len(p["experiments"]) == 3 and {e["line"] for e in p["experiments"]} == {"L1"} for p in plans)
    assert all(r.line_of(p) == "L1" for p in r.archive.programs.values())
    assert sum(1 for p in r.archive.programs.values() if p.role == "alt") > 0      # alternatives are kept


def test_a_stalled_line_closes_and_new_lines_take_its_slots(tmp_path):
    out = tmp_path / "stall"
    r = run(out, 8, stall_gain=1.0, line_patience=2)          # every line closes 2 generations after it opens
    hist = jl(out / "history.jsonl")
    lines = jl(out / "lines.jsonl")[-1]["lines"]
    assert lines[0]["id"] == "L1" and lines[0]["status"] == "closed" and lines[0]["ended"] == 2
    assert hist[3]["allocation"].keys() == {"L2", "L3"} and sum(hist[3]["allocation"].values()) == 3
    sources = [ln["source"] for ln in lines[1:4]]
    assert any("alternative" in s for s in sources) and any("fresh" in s or "branch" in s for s in sources)
    # experiments go to their line, with bases from that line
    plans = jl(out / "plans.jsonl")
    for pl in plans:
        for e in pl["experiments"]:
            ln = next(l for l in lines if l["id"] == e["line"])
            assert e["base"] == ln["root"] or r.line_of(r.archive.programs[e["base"]]) == e["line"]
    # the planner sees the active lines and the closed ones by name, never a closed line's score
    trace = [json.loads(l) for l in (out / "trace.jsonl").read_text().splitlines()]
    user = [t for t in trace if t["role"] == "researcher" and t.get("gen") == 4][0]["user"]
    assert "## Line L2" in user or "## Line L3" in user or "## Line L4" in user
    assert "## Closed lines" in user and "- L1: started at generation 1 from Code Zero" in user
    l1_best = f"{lines[0]['best']:.6f}"
    assert l1_best not in user.split("## Closed lines")[1].split("## Findings")[0]
    assert "of 8" not in user and "Generation 4\n" in user
    s = json.loads((out / "summary.json").read_text())
    assert len(s["lines"]) >= 4 and s["best"] >= max(ln["best"] for ln in s["lines"]) - 1e-12


def test_experiments_follow_the_allocation(tmp_path):
    r = run(tmp_path / "a", 1, stall_gain=0.0)
    r.lines.append({**r.lines[0], "id": "L2", "root": "p0001", "best_id": "p0001"})
    plan = {"experiments": [{"line": "L1", "base": "p0001", "change": "x"}, {"line": "L1", "base": "p0001", "change": "y"},
                            {"line": "L1", "base": "p9999", "change": "z"}]}
    exps = r.experiments(plan, {"L1": 2, "L2": 1})
    assert [e["line"] for e in exps] == ["L1", "L1", "L2"]
    assert exps[2]["line_requested"] == "L1" and exps[2]["base"] == "p0001"


def test_resume_keeps_the_lines(tmp_path):
    out = tmp_path / "res"
    run(out, 3, stall_gain=1.0, line_patience=2)
    before = jl(out / "lines.jsonl")[-1]["lines"]
    r = Run(out, llm=FakeLLM(fake_answer), gens=5, log=lambda m: None)
    assert [l["id"] for l in r.lines] == [l["id"] for l in before] and r.cfg.stall_gain == 1.0
    r.go()
    hist = jl(out / "history.jsonl")
    assert [h["gen"] for h in hist] == [0, 1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------------------------- the map
def test_the_map_is_balanced_and_failures_are_grouped_by_line(tmp_path):
    r = run(tmp_path / "m", 3, stall_gain=1.0, line_patience=2)
    mem = r.memory
    l1 = [p.id for p in r.archive.programs.values() if r.line_of(p) == "L1" and p.parent][:2]
    for i in range(40):
        mem._append({"op": "new", "id": f"F{len(mem.events) + 1}", "gen": 1, "kind": "fails",
                     "claim": f"failure {i}: the point is confirmed saturated", "evidence": l1[:1], "links": []})
    mem.rebuild()
    text, shown = mem.findings_view()
    assert "Line L1 (closed): " in text and "not about the problem" in text
    assert "confirmed saturated" not in text          # closed lines' failures are only counted, not listed


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


# ---------------------------------------------------------------------------------------------- warm starts
def test_warm_starts_from_an_earlier_run(tmp_path):
    from helix47.warm import prepare
    from helix4.run import Config as Config4, Run as Run4, fake_answer as fake4
    src = tmp_path / "v4"
    Run4(src, Config4(gens=2, budget=2.0), llm=FakeLLM(fake4), gens=2, log=lambda m: None).go()
    import shutil as _sh
    best = max((json.loads(l) for l in (src / "programs.jsonl").read_text().splitlines()), key=lambda p: p["score"] or 0)
    for mode, out in (("continue", tmp_path / "c"), ("best", tmp_path / "b")):
        prepare(src, out, mode, budget=2.0)
        r = Run(out, llm=FakeLLM(fake_answer), gens=3, log=lambda m: None)
        assert r.gen_done == 2 and r.lines[0]["best"] == pytest.approx(best["score"]) and r.cfg.budget == 2.0
        r.go()
        hist = jl(out / "history.jsonl")
        assert hist[-1]["gen"] == 3 and hist[-1]["best"] >= best["score"] - 1e-12
    assert len(jl(tmp_path / "b" / "programs.jsonl")) < len(jl(tmp_path / "c" / "programs.jsonl"))
    assert not (tmp_path / "b" / "findings.jsonl").exists() or len(jl(tmp_path / "b" / "findings.jsonl")) <= 6
