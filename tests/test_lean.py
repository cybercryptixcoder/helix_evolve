"""Crash tests for the lean Helix (fake model; results come only from live runs). python -m pytest tests/test_lean.py"""
import json
import os

import numpy as np

from lean.llm import FakeLLM
from lean.loop import Config, Run
from lean.problems import load
from lean.run import fake_answer

os.environ.setdefault("HELIX_SLOTS_DIR", "/tmp/helix_test_slots")


def test_circles_check_is_exact():
    p = load("circles", n=2)
    ok = np.array([[0.25, 0.5, 0.25], [0.75, 0.5, 0.25]])
    assert p.check(ok)[0] is not None and abs(p.score(ok) - 0.5) < 1e-12
    bad = ok.copy()
    bad[1, 2] = 0.25 + 1e-15                     # overlaps (and sticks out) by a hair: invalid
    assert p.check(bad)[0] is None
    assert p.check(np.ones((3, 3)))[0] is None


def test_ac2_limit_is_exact():
    p = load("ac2", max_n=100)
    assert p.check(np.ones(100))[0] is not None and p.check(np.ones(101))[0] is None
    assert abs(p.score(np.ones(50)) - 2 / 3) < 1e-12


def test_run_resume(tmp_path):
    for kw in ({}, {"planned": 0, "mutations": 4}, {"planned": 4, "mutations": 0}):
        d = tmp_path / str(len(kw)) / str(kw.get("planned"))
        Run(d, Config(rounds=2, budget=2, **kw), llm=FakeLLM(fake_answer), log=lambda m: None).go()
        Run(d, Config(rounds=3, budget=2, **kw), llm=FakeLLM(fake_answer), log=lambda m: None).go()
        rows = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
        assert [r["round"] for r in rows] == [0, 1, 2, 3]
        progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
        assert len(progs) == 1 + 3 * (kw.get("planned", 3) + kw.get("mutations", 3))


def test_what_the_agents_see_is_v4s(tmp_path):
    """The planner's view, the planner's retry, and the coder's and mutator's requests, as v4 wrote them."""
    import helix4.prompts as V4
    seen, bad = {"planner": [], "coder": [], "mutator": []}, {"n": 0}

    def answer(role, system, user):
        seen[role].append((system, user))
        if role == "planner" and bad["n"] == 0:            # the first plan is unreadable: v4 asks once more
            bad["n"] += 1
            return "I think we should try something"
        return fake_answer(role, system, user)
    d = tmp_path / "v"
    Run(d, Config(problem="ac2", params={"max_n": 200000}, rounds=2, budget=2, memory="none"), llm=FakeLLM(answer),
        log=lambda m: None).go()                      # the Control view here; the Atlas's view: test_lean_v4.py
    system, user = seen["planner"][0]
    assert system == V4.RESEARCHER_SYSTEM.format(k=3, budget=2)
    assert "# Generation 1 of 2\nEach program gets 2 s of CPU and starts from its base's construction." in user
    assert "## The best program so far: p0001" in user and "\nIts lineage: p0001 " in user
    assert "## The strongest programs (any program can be a base)" in user
    assert user.endswith(V4.PLAN_FORMAT.format(k=3, findings=""))
    assert seen["planner"][1][1].endswith("(Your previous reply could not be read. Reply with the JSON object only.)")
    rows = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
    assert rows[1]["fallback_experiments"] == 0
    s, u = seen["coder"][0]
    assert s == V4.CODER_SYSTEM and "Keep what the base does well unless the experiment says otherwise. " \
        "budget_seconds will be 2; `start` will be the base's construction." in u
    s, u = seen["mutator"][0]
    assert s == V4.MUTATOR_SYSTEM
    assert any("## Another strong program, for ideas: " in u for _, u in seen["mutator"][3:])   # generation 2
    assert "Write an improved version of the program to improve. budget_seconds will be 2; `start` will be its " \
        "construction." in u
    progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
    second = [p for p in progs if p["round"] == 2 and p["valid"]]
    assert second and all("Its lineage" not in "".join(p["feedback"]) for p in second)


def test_feedback_says_when_the_start_is_unchanged(tmp_path):
    from lean.sandbox import evaluate
    p = load("ac2", max_n=1000)
    keep = "def construct(budget_seconds, start):\n    return start\n"
    r = evaluate(p, keep, np.ones(50), 2)
    assert r["valid"] and "the result is the start unchanged" in r["feedback"][0] and r["delta"] == 0
    assert any(l.startswith("CPU ") and "wall" in l for l in r["feedback"])
    r = evaluate(p, "def construct(budget_seconds, start):\n    print('hello')\n    return -start\n", np.ones(5), 2)
    assert not r["valid"] and any("hello" in l for l in r["feedback"])       # failures show the printed lines too


class ScoreOnly:
    """An adapter with its own evaluator and no constructions (like the VRP): the score is the program's length."""
    name, references, entry = "toy", [], "solve"
    description = "Write solve(). Longer is better."
    code_zero = "def solve():\n    return 1\n"
    task_note = "solve() is called once."
    generation_note = "Every program is run once; a change is measured against its base's score."

    def evaluate(self, code, start, budget, mem_mb):
        assert start is None
        return {"valid": True, "score": float(len(code)), "feedback": [f"score {len(code)}"], "error": "", "cpu": 0.0}


def test_an_adapter_with_its_own_evaluator(tmp_path, monkeypatch):
    import lean.loop as L

    def answer(role, system, user):
        if role == "planner":
            return fake_answer(role, system, user)
        return f"```python\ndef solve():\n    return {np.random.randint(10 ** 9)}\n```\nSUMMARY: longer"
    monkeypatch.setattr(L, "load", lambda name, **kw: ScoreOnly())
    seen = []
    llm = FakeLLM(lambda r, s, u: (seen.append((r, u)), answer(r, s, u))[1])
    d = tmp_path / "toy"
    Run(d, Config(problem="toy", rounds=1, budget=2), llm=llm, log=lambda m: None).go()
    progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
    kids = [p for p in progs if p["parent"]]
    assert len(kids) == 6 and all(p["valid"] and p["delta"] == p["score"] - progs[0]["score"] for p in kids)
    assert all(f"its base p0001 scored" in p["feedback"][0] for p in kids)
    assert any("Every program is run once" in u for r, u in seen if r == "planner")
    assert any(u.rstrip().endswith("SUMMARY: <what you changed and why, at most 30 words>") and "solve() is called once."
               in u for r, u in seen if r == "coder")


def test_extra_starting_programs(tmp_path, monkeypatch):
    """A problem's extra_seeds join generation 0 beside Code Zero; parents and inspirations come from all of them."""
    import lean.loop as L

    class TwoStarts(ScoreOnly):
        extra_seeds = [("the second start", "def solve():\n    return 22222222222222\n")]

    def answer(role, system, user):
        if role == "planner":
            return fake_answer(role, system, user)
        return f"```python\ndef solve():\n    return {np.random.randint(10 ** 9)}\n```\nSUMMARY: x"
    monkeypatch.setattr(L, "load", lambda name, **kw: TwoStarts())
    d = tmp_path / "two"
    Run(d, Config(problem="toy", rounds=1, budget=2), llm=FakeLLM(answer), log=lambda m: None).go()
    progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
    seeds = [p for p in progs if p["role"] == "seed"]
    assert [p["id"] for p in seeds] == ["p0001", "p0002"] and seeds[1]["idea"] == "the second start"
    rounds = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
    assert rounds[0]["best_id"] == "p0002"                       # the better start is generation 0's best
    assert len([p for p in progs if p["parent"]]) == 6
    # no extra_seeds: generation 0 is Code Zero alone, as before
    monkeypatch.setattr(L, "load", lambda name, **kw: ScoreOnly())
    d = tmp_path / "one"
    Run(d, Config(problem="toy", rounds=1, budget=2), llm=FakeLLM(answer), log=lambda m: None).go()
    progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
    assert [p["id"] for p in progs if p["role"] == "seed"] == ["p0001"]


def test_erdos_and_ac3_values():
    """Code Zero gives the trivial bounds; splitting every step into equal sub-steps is the same function, so the
    value can't change (the knot formulas are exact); the FFT path agrees with the direct one."""
    from lean.problems import load
    e, a = load("erdos"), load("ac3")
    assert abs(e.value(e.check(np.full(50, 0.5))[0]) - 0.5) < 1e-12
    assert abs(a.value(a.check(np.ones(50))[0]) - 2) < 1e-12
    rng = np.random.default_rng(0)
    h = np.clip(rng.random(40), 0.05, 0.95)
    h = h - h.mean() + 0.5
    assert e.check(h)[0] is not None and e.check(h + 1e-6)[0] is None
    assert abs(e.value(h) - e.value(np.repeat(h, 50))) < 1e-12        # 2,000 steps: direct
    assert abs(e.value(h) - e.value(np.repeat(h, 200))) < 1e-12       # 8,000 steps: FFT
    v = a.check(rng.normal(size=60) + 0.3)[0]
    assert abs(a.value(v) - a.value(np.repeat(v, 20))) < 1e-9
    assert a.value(v) >= 2 * 60 * np.convolve(v, v).max() / v.sum() ** 2 - 1e-12   # |f*f| >= f*f




def test_many_takes_on_runs_added_later(tmp_path, monkeypatch):
    """lean.many starts the runs in its file, and a run added to the file while it works."""
    import threading
    import time as T
    import lean.many as M
    import lean.loop as L
    real_sleep = T.sleep                     # (time.sleep itself is patched below: lean.many's waits are shortened)
    monkeypatch.setattr(L, "Run", lambda out, cfg, log: type("R", (), {"go": lambda self: real_sleep(2)})())
    monkeypatch.setattr(M, "Run", L.Run)
    sleeps = []
    monkeypatch.setattr(M.time, "sleep", lambda s: (sleeps.append(s), real_sleep(min(s, 0.2)))[1])
    f = tmp_path / "runs.json"
    f.write_text(json.dumps({"runs": [{"name": "a", "out": str(tmp_path / "a")}]}))
    started = []
    orig = M.one
    monkeypatch.setattr(M, "one", lambda s, log: (started.append(s["name"]), orig(s, log)))
    th = threading.Thread(target=M.main, args=([str(f)],))
    th.start()
    real_sleep(0.5)
    f.write_text(json.dumps({"runs": [{"name": "a", "out": str(tmp_path / "a")}, {"name": "b", "out": str(tmp_path / "b")}]}))
    th.join(timeout=20)
    assert not th.is_alive() and started == ["a", "b"]
