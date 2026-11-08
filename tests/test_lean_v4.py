"""Lean against v4, by their own code: the same archive and findings, rendered by helix4's Atlas and by lean's, must
give the same text (numbers aside: lean shows 9 digits where v4 showed 5 or 6). python -m pytest tests/test_lean_v4.py
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HELIX_SLOTS_DIR", "/tmp/helix_test_slots")

import helix4.archive as A4                      # noqa: E402
import helix4.memory as M4                       # noqa: E402
import helix4.problems.ac2 as AC2_V4             # noqa: E402
import helix4.prompts as P4                      # noqa: E402

from lean.llm import FakeLLM                     # noqa: E402
from lean.loop import Config, Run                # noqa: E402
from lean.run import fake_answer                 # noqa: E402

NUM = re.compile(r"[-+]?\d+\.\d+(e[-+]?\d+)?")


def norm(s):
    return NUM.sub("#", s)


def answer(role, system, user):
    """Plans on real ids; the Navigator opens two programs and a finding; the Distiller writes linked findings with
    evidence and attaches evidence to an older finding."""
    ids = re.findall(r"\bp\d{4}\b", user)
    fs = re.findall(r"\bF\d+\b", user)
    if role == "navigator":
        return json.dumps({"open": (ids[:2] + fs[:1]), "why": "fake"})
    if role == "distiller":
        part = user.split("every program and its result")[-1]
        pids = re.findall(r"\bp\d{4}\b", part)
        old = re.findall(r"\bF\d+\b", user.split("## Findings so far")[-1].split("##")[0])
        new = [{"kind": "works", "claim": f"fake: {pids[0]} helped", "evidence": pids[:2],
                "links": [{"to": old[0], "type": "refines"}] if old else []},
               {"kind": "fails", "claim": "fake: this failed", "evidence": pids[2:3]},
               {"kind": "question", "claim": "fake: worth testing?", "evidence": []}]
        return json.dumps({"new": new, "evidence": [{"finding": old[0], "programs": pids[3:4]}] if old else []})
    return fake_answer(role, system, user)


def v4_view(lean_dir, tmp):
    """helix4's Atlas over the same programs and findings (programs converted to helix4's record)."""
    d = tmp / "v4"
    d.mkdir()
    role = {"planned": "deep", "mutation": "wide", "seed": "seed"}
    with (d / "programs.jsonl").open("w") as f:
        for l in (lean_dir / "programs.jsonl").read_text().splitlines():
            p = json.loads(l)
            plan = {k: v for k, v in (p.get("plan") or {}).items() if k in ("base", "hypothesis", "change",
                                                                             "prediction", "builds_on")}
            f.write(json.dumps({"id": p["id"], "gen": p["round"], "role": role[p["role"]], "parent": p["parent"],
                                "intent": p["idea"], "code": p["code"], "plan": plan, "diff": p["diff"],
                                "valid": p["valid"], "score": p["score"], "start_score": p["start_score"],
                                "delta": p["delta"], "feedback": p["feedback"], "error": p["error"], "cpu": p["cpu"],
                                "summary": p["summary"], "duplicate_of": p["duplicate_of"]}) + "\n")
    shutil.copy(lean_dir / "findings.jsonl", d / "findings.jsonl")

    class Shim:
        pass
    run = Shim()
    run.dir, run.archive, run.problem = d, A4.Archive(d), AC2_V4
    run.cfg = Shim()
    run.cfg.gens, run.cfg.budget, run.cfg.deep = 3, 2.0, 3
    return run, M4.Atlas(run)


def test_atlas_renders_as_v4s(tmp_path):
    seen = []
    llm = FakeLLM(lambda r, s, u: (seen.append((r, s, u)), answer(r, s, u))[1])
    d = tmp_path / "lean"
    run = Run(d, Config(problem="ac2", params={"max_n": 200000}, rounds=3, budget=2), llm=llm, log=lambda m: None)
    run.go()
    rows = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
    assert rows[-1]["findings"] >= 5 and rows[-1]["links"] >= 1
    v4run, v4 = v4_view(d, tmp_path)
    mine = run.atlas
    gen = 4                                      # the map a planner of the next generation would see
    run.round_now = gen
    assert norm(mine.map(gen)) == norm(v4.map(gen))
    for pid in ("p0002", "p0005", "p0012"):
        assert norm(mine.open_program(pid)) == norm(v4.open_program(pid))
    for fid in mine.findings:
        assert norm(mine.finding_line(fid)) == norm(v4.finding_line(fid))
        assert norm(mine.open_finding(fid)) == norm(v4.open_finding(fid))
        assert mine.status(mine.findings[fid]) == v4.status(v4.findings[fid])
    assert mine.stats() == v4.stats()
    # the planner's view in generation 3: v4's header, best block and map, the items it opened, v4's plan format
    planner = [u for r, s, u in seen if r == "planner"]
    nav = [u for r, s, u in seen if r == "navigator"]
    assert len(planner) == 3 and len(nav) == 2                       # no Navigator in generation 1, as in v4
    assert "## What you opened\n### p0" in planner[2] and "\n### F" in planner[2]
    assert planner[2].endswith(P4.PLAN_FORMAT.format(k=3, findings=" or findings"))
    assert "## The strongest programs" not in planner[2]            # v4's Atlas view has no scoreboard
    assert nav[0].endswith(P4.NAVIGATOR_ASK.format(k=6))
    head = M4.header(v4run, 3) + "\n" + "## The best program so far"
    assert norm(planner[2]).startswith(norm(head).replace("# Generation 3 of 3", "# Generation 3 of 3"))
    # the Distiller's request: v4's system prompt and task, v4's title
    dist = [(s, u) for r, s, u in seen if r == "distiller"]
    assert len(dist) == 3 and all(s == P4.DISTILLER_SYSTEM for s, _ in dist)
    assert dist[2][1].startswith(AC2_V4.TITLE + "\n\n## Findings so far\n")
    assert dist[2][1].endswith(P4.DISTILLER_ASK.format(gen=3))


def test_resume_keeps_the_atlas_consistent(tmp_path):
    d = tmp_path / "r"
    Run(d, Config(problem="ac2", rounds=2, budget=2), llm=FakeLLM(answer), log=lambda m: None).go()
    n2 = len(Run(d, Config(rounds=2), llm=FakeLLM(answer), log=lambda m: None).atlas.findings)
    # a crash mid-generation 3: findings of generation 3 were written but the generation never finished
    with (d / "findings.jsonl").open("a") as f:
        f.write(json.dumps({"op": "new", "id": "F99", "gen": 3, "kind": "works", "claim": "x", "evidence": ["p0002"],
                            "links": []}) + "\n")
    r = Run(d, Config(rounds=3), llm=FakeLLM(answer), log=lambda m: None)
    assert len(r.atlas.findings) == n2 and "F99" not in r.atlas.findings
    r.go()
    assert len([json.loads(l) for l in (d / "plans.jsonl").read_text().splitlines()]) == 3


def test_control_view_is_v4s(tmp_path):
    seen = []
    llm = FakeLLM(lambda r, s, u: (seen.append((r, u)), answer(r, s, u))[1])
    Run(tmp_path / "c", Config(problem="ac2", rounds=2, budget=2, memory="none"), llm=llm, log=lambda m: None).go()
    planner = [u for r, u in seen if r == "planner"]
    assert not any(r in ("navigator", "distiller") for r, _ in seen)
    assert "## The strongest programs (any program can be a base)" in planner[1]
    assert planner[1].endswith(P4.PLAN_FORMAT.format(k=3, findings=""))
    assert not (tmp_path / "c" / "findings.jsonl").exists()


def test_ac2_feedback_is_v4s(tmp_path):
    """The same program, run by lean's sandbox and by helix4's evaluator: the same feedback lines (numbers aside)."""
    import numpy as np
    from helix4.evaluate import evaluate as v4_evaluate
    from lean.problems import load
    from lean.sandbox import evaluate as lean_evaluate
    prog = ("import numpy as np\nimport time\n\ndef construct(budget_seconds, start):\n"
            "    print('step 1')\n    return np.concatenate([start, start[::-1] * 0.5])\n")
    start = np.linspace(1, 2, 40)
    mine = lean_evaluate(load("ac2", max_n=200000), prog, start, 2)
    theirs = v4_evaluate(AC2_V4, prog, start, 2)
    assert mine["valid"] and theirs["valid"] and abs(mine["score"] - theirs["score"]) < 1e-15
    assert [norm(l) for l in mine["feedback"]] == [norm(l) for l in theirs["feedback"]]
    same = "def construct(budget_seconds, start):\n    return start\n"
    mine, theirs = lean_evaluate(load("ac2", max_n=200000), same, start, 2), v4_evaluate(AC2_V4, same, start, 2)
    assert [norm(l) for l in mine["feedback"]] == [norm(l) for l in theirs["feedback"]]
    bad = "def construct(budget_seconds, start):\n    print('oops')\n    return -start\n"
    mine, theirs = lean_evaluate(load("ac2", max_n=200000), bad, start, 2), v4_evaluate(AC2_V4, bad, start, 2)
    assert not mine["valid"] and not theirs["valid"]
    assert mine["feedback"][0] == theirs["feedback"][0]
