"""Tests for Helix v4.6 and v6 (helix6/).

    python -m pytest tests/test_helix6.py -q
"""
import json
import os
import random
import tempfile
import types

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix6-slots-"))

from helix4.archive import Program                  # noqa: E402
from helix4.llm import FakeLLM                      # noqa: E402
from helix4.problems import ac2                     # noqa: E402
from helix6 import run as R6                        # noqa: E402
from helix6.evaluate import evaluate, is_inconclusive   # noqa: E402
from helix6.toolkits import AC2                     # noqa: E402

GOOD = "import numpy as np\ndef construct(b, start):\n    return (np.arange(50) + 0.5) ** -0.5\n"
KEEP = "import numpy as np\ndef construct(b, start):\n    return np.asarray(start, dtype=float)\n"


def fake_run(tmp_path, condition, gens=2, name=None, **kw):
    cfg = R6.Config(condition=condition, gens=gens, budget=2, deep_seconds=6, min_seconds=1, max_seconds=6, **kw)
    return R6.Run(tmp_path / (name or condition), cfg, llm=FakeLLM(R6.fake_answer), log=lambda m: None)


# ---------------------------------------------------------------------------------------------- evaluator
def test_toolkit_is_the_evaluators_own_score():
    m = types.ModuleType("hp")
    exec(AC2, m.__dict__)
    rng = np.random.default_rng(3)
    for n in (1, 2, 50, 4096, 4097, 30000):
        h = np.abs(rng.standard_normal(n)) ** 3
        a, _ = ac2.check(h)
        assert abs(m.score(h) - ac2.score(a)) < 1e-12
    assert m.score(np.array([1.0, -1.0])) == 0.0 and m.score(np.zeros(5)) == 0.0


def test_programs_can_import_the_toolkit_and_inconclusive_is_labelled():
    code = ("import numpy as np\nfrom helix_problem import score\ndef construct(b, start):\n"
            "    h = (np.arange(50) + 0.5) ** -0.5\n    print('stage check: score', round(score(h), 6))\n    return h\n")
    r = evaluate(ac2, code, None, 2)
    assert r["valid"] and "0.844679" in " ".join(r["feedback"])
    busy = ("import time\ndef construct(b, start):\n    t = time.process_time()\n"
            "    while time.process_time() - t < 0.95 * b:\n        sum(range(1000))\n    return start\n")
    r = evaluate(ac2, busy, np.ones(10), 2)
    assert r["valid"] and r["inconclusive"] and "INCONCLUSIVE" in r["feedback"][0]
    assert not is_inconclusive(0.0, 0.5, 2) and not is_inconclusive(1e-3, 2.0, 2) and is_inconclusive(0.0, 1.9, 2)


def test_split_seconds():
    assert sum(R6.split_seconds([45, 30, 15], 90, 15, 90)) == pytest.approx(90)
    s = R6.split_seconds([500, 1, 1], 90, 15, 90)
    assert sum(s) == pytest.approx(90) and min(s) >= 15 - 1e-9 and max(s) <= 90
    assert R6.split_seconds([10], 90, 15, 90) == [90.0]
    s = R6.split_seconds([30, 30, 30, 30], 90, 30, 90)            # more than fits at the minimum: lowered
    assert sum(s) == pytest.approx(90)


# ---------------------------------------------------------------------------------------------- the engine
def test_method_on_another_state(tmp_path):
    r = fake_run(tmp_path, "v46", gens=1)
    r.go()
    zero = r.archive.programs["p0001"]
    good = r.child6(2, "deep", zero, GOOD, "good", {"hypothesis": "h"}, "", seconds=2)
    keep = r.child6(3, "deep", zero, KEEP, "keep on good", {"hypothesis": "h"}, "", state=good, seconds=2)
    assert keep.valid and abs(keep.score - good.score) < 1e-12 and abs(keep.delta) < 1e-12
    assert keep.parent == zero.id and r.meta[keep.id]["state"] == good.id and "ran on" in keep.feedback[0]
    assert "ran on" in r.state_note(keep)
    again = r.child6(4, "continue", good, good.code, "continue", {}, "", state=good, seconds=2, allow_same=True)
    assert again.valid and not again.duplicate_of
    fresh = r.child6(4, "deep", good, GOOD, "fresh", {"hypothesis": "h", "fresh": True}, "", fresh=True, seconds=2)
    assert fresh.valid and fresh.delta is None and r.meta[fresh.id]["fresh"]


def test_experiments_parse_state_seconds_and_kind(tmp_path):
    r = fake_run(tmp_path, "v46", gens=2)
    r.go()
    best = r.archive.best()
    other = next(p for p in r.archive.ranked() if p.id != best.id)
    plan = {"experiments": [{"base": other.id, "state": "best", "seconds": 60, "kind": "  A  New Idea ", "change": "c"},
                            {"base": "p9999", "state": other.id, "seconds": 20, "change": "c"},
                            {"base": best.id, "state": "none", "seconds": 10, "change": "c"},
                            {"base": best.id, "change": "ignored: a fourth experiment"}]}
    exps = r.experiments6(plan, 3)
    assert len(exps) == 3
    assert exps[0]["base"] == other.id and exps[0]["state"] == best.id and exps[0]["kind"] == "A New Idea"
    assert exps[1]["base"] == best.id and exps[1]["base_requested"] == "p9999" and exps[1]["state"] == other.id
    assert exps[2]["fresh"] and exps[2]["state"] is None
    assert sum(e["seconds"] for e in exps) == pytest.approx(r.cfg.deep_seconds)
    assert exps[0]["seconds"] > exps[1]["seconds"] >= r.cfg.min_seconds
    fb = r.experiments6(None, 3)
    assert len(fb) == r.cfg.deep and all(e.get("fallback") for e in fb)
    # a wide child of this generation that finished before the plan arrived is not what "best" meant
    late = r.child6(3, "wide", best, GOOD + "# late\n", "late", {}, "", seconds=2)
    assert late.valid
    exps = r.experiments6({"experiments": [{"base": late.id, "state": "best", "change": "c"}]}, 3)
    assert exps[0]["state"] == best.id and exps[0]["base"] == best.id and exps[0]["base_requested"] == late.id


def test_the_wide_loop_works_on_the_frontier(tmp_path):
    r = fake_run(tmp_path, "v46", gens=1)
    r.go()
    zero = r.archive.programs["p0001"]
    good = r.child6(2, "deep", zero, GOOD, "good", {"hypothesis": "h"}, "", seconds=2)
    near = r.child6(2, "deep", good, KEEP + "# near\n", "near", {"hypothesis": "h"}, "", seconds=2)
    for i in range(6):              # a stale tail of weak programs, like v4's population
        r.child6(2, "wide", zero, f"import numpy as np\ndef construct(b, s):\n    return np.ones({5 + i})\n", "weak",
                 {}, "", seconds=2)
    rng = random.Random(1)
    for _ in range(20):
        plan = r.wide_plan(3, rng)
        assert len(plan) == 3
        for parent, state, tr, insp in plan[:2]:
            assert parent.score >= good.score - R6.FRONTIER_EPS and not tr and state is parent
        donor, state, tr, insp = plan[2]
        assert tr and state.id == r.archive.best().id and donor.score < good.score - R6.FRONTIER_EPS
        assert near.id in {p.id for p, *_ in plan[:2]} or good.id in {p.id for p, *_ in plan[:2]}


def test_polishing_tail_and_progress_block(tmp_path):
    r = fake_run(tmp_path, "v46", gens=2)
    r.go()
    best = r.archive.best()
    r.set_meta(r.child6(3, "deep", best, KEEP + "#k\n", "x", {"hypothesis": "h"}, "", seconds=2), kind="tune the tail")
    b = best.score
    for g, v in ((3, b + 2e-5), (4, b + 3e-5), (5, b + 4e-5)):
        r._append("history.jsonl", {"gen": g, "best": v, "best_id": best.id})
    t = r.tail_status(6)
    assert t["in_tail"] and t["tail_gens"] >= 2
    text = r.progress_block(6)
    assert "polishing tail" in text and "tune the tail" in text and "not on this list" in text
    r._append("history.jsonl", {"gen": 6, "best": b + 2e-3, "best_id": best.id})
    assert not r.tail_status(7)["in_tail"]


# ---------------------------------------------------------------------------------------------- Atlas (v4.6)
def test_atlas_ideas_kinds_scopes_and_inconclusive(tmp_path):
    r = fake_run(tmp_path, "v46", gens=2)
    r.go()
    a = r.memory
    zero = r.archive.programs["p0001"]
    good = r.child6(3, "deep", zero, GOOD, "good", {"hypothesis": "h"}, "", seconds=2, meta={"kind": "power law"})
    busy = ("import time\ndef construct(b, start):\n    t = time.process_time()\n"
            "    while time.process_time() - t < 0.95 * b:\n        sum(range(1000))\n    return start\n")
    inc = r.child6(3, "deep", good, busy, "slow idea", {"hypothesis": "h"}, "", seconds=2, meta={"kind": "slow idea"})
    assert r.meta[inc.id]["inconclusive"] and a.outcome(inc) == "inconclusive" and a.outcome(good) == "gain"
    # the same program continued from its own output and finding nothing has converged: conclusive, not inconclusive
    conv = r.child6(3, "continue", inc, busy, "continue", {}, "", state=inc, seconds=2, allow_same=True)
    assert not r.meta[conv.id]["inconclusive"] and r.meta[conv.id]["converged"] and a.outcome(conv) == "no gain"
    assert "converged" in conv.feedback[0] and not any(f.startswith("INCONCLUSIVE") for f in conv.feedback)
    ks = a.kinds()
    assert ks["power law"]["gains"] == 1 and ks["slow idea"]["inconclusive"] == 1
    assert "slow idea" in a.kinds_table(4)
    # a "fails" finding whose only evidence is inconclusive becomes a question; tags are kept
    reply = json.dumps({"new": [{"kind": "fails", "tag": "Slow Idea", "claim": "the slow idea fails", "evidence": [inc.id]},
                                {"kind": "works", "tag": "power law", "claim": "power law works", "evidence": [good.id]}]})
    r.llm = FakeLLM(lambda role, s, u: reply if role == "distiller" else R6.fake_answer(role, s, u))
    a.update(3, {"analysis": "x"}, [good, inc])
    fs = [f for f in a.findings.values() if f["gen"] == 3]
    assert {f["kind"] for f in fs} == {"question", "works"} and {f["tag"] for f in fs} == {"slow idea", "power law"}
    line = a.finding_line(next(f["id"] for f in fs if f["kind"] == "works"))
    assert "«power law»" in line and "on p0001" in line
    q = next(f for f in fs if f["kind"] == "question")
    assert "1 inconclusive" in a.status(q)
    m = a.map(4)
    assert "kinds of change tried" in m and "Key findings" in m and "Latest findings" in m
    best = r.archive.best()
    assert "shown above" in a.open_program(best.id)
    others = [p.id for p in r.archive.ranked() if p.id != best.id][:5]
    opened = a.open_items([best.id] + others + ["F1", "nonsense"])
    assert len(opened) == 7 and sum("```python" in t for t in opened) == a.OPEN_CODE
    assert sum("not shown: only the first" in t for t in opened) == len(others) - a.OPEN_CODE


def test_plan_prompt_has_the_new_structure(tmp_path):
    r = fake_run(tmp_path, "v46", gens=3)
    r.go()
    tr = [json.loads(l) for l in (r.dir / "trace.jsonl").read_text().splitlines()]
    plans = [t for t in tr if t["role"] == "researcher"]
    u = plans[-1]["user"]
    assert "kinds of change tried" in u and "their seconds add up to" in u and "Progress check" in u
    assert "METHOD" in plans[-1]["system"] and "INCONCLUSIVE" in plans[-1]["system"]
    muts = [t for t in tr if t["role"] == "mutator"]
    assert any("helix_problem" in t["system"] for t in muts)
    hist = [json.loads(l) for l in (r.dir / "history.jsonl").read_text().splitlines()][1:]
    assert all(len(h["exp_seconds"]) == 3 and abs(sum(h["exp_seconds"]) - 6) < 1e-6 for h in hist)
    assert all(max(h["wide_parent_gaps"] or [0]) <= R6.FRONTIER_EPS + 1e-9 or h["transplants"] for h in hist)


@pytest.mark.parametrize("condition", ["v46", "v6"])
def test_end_to_end_and_resume(tmp_path, condition):
    r = fake_run(tmp_path, condition, gens=3)
    s = r.go()
    assert s["gens_done"] == 3 and s["best"] > 0.7
    hist = [json.loads(l) for l in (r.dir / "history.jsonl").read_text().splitlines()]
    assert [h["gen"] for h in hist] == [0, 1, 2, 3]
    # a crash mid-generation: the unfinished generation's programs and meta are dropped on resume
    r.child6(4, "deep", r.archive.best(), KEEP + "#half\n", "half-done", {"hypothesis": "h"}, "", seconds=2)
    r2 = R6.Run(r.dir, gens=4, llm=FakeLLM(R6.fake_answer), log=lambda m: None)
    assert all(p.gen <= 3 for p in r2.archive.programs.values()) and all(m["gen"] <= 3 for m in r2.meta.values())
    s2 = r2.go()
    assert s2["gens_done"] == 4


# ---------------------------------------------------------------------------------------------- the agent (v6)
def test_agent_validates_units_and_fills_the_halo(tmp_path):
    r = fake_run(tmp_path, "v6", gens=1)
    r.go()
    ag = r.memory
    best = r.archive.best()
    d = {"actions": [{"do": "experiment", "base": best.id, "state": "none", "units": 5, "change": "c"},
                     {"do": "mutate", "state": best.id, "count": 9},
                     {"do": "continue", "program": "p9999", "units": 1},
                     {"do": "dance"}]}
    jobs = ag.validate(2, d, {})
    assert jobs[0]["units"] == 3 and jobs[0]["fresh"] and jobs[0]["seconds"] == 3 * r.cfg.budget
    assert jobs[1]["do"] == "mutate" and jobs[1]["count"] == 3
    assert sum(j["units"] for j in jobs) == r.cfg.units and not any(j["do"] == "continue" for j in jobs)
    jobs = ag.validate(2, {"actions": []}, {})
    assert len(jobs) == 1 and jobs[0]["auto"] and jobs[0]["count"] == r.cfg.units


def test_agent_theory_threads_due_and_park(tmp_path):
    r = fake_run(tmp_path, "v6", gens=1)
    r.go()
    ag = r.memory
    refs, _ = ag.apply_ops(2, {"threads": [{"op": "open", "ref": "t1", "question": "q", "stop": "s"}],
                               "theory": [{"op": "add", "kind": "mechanism", "statement": "this is the true maximum",
                                           "confidence": "high", "refuted_if": "a higher score"}]})
    tid = refs["t1"]
    h = next(h for h in ag.theory.values() if h["statement"] == "this is the true maximum")
    assert h["kind"] == "conjecture" and h["confidence"] == "low"
    best = r.archive.best()
    for g in (2, 3):                            # 3 actions over 2 rounds, none raising the record
        for i in range(2 if g == 2 else 1):
            p = r.child6(g, "deep", best, KEEP + f"#{g}{i}\n", "x", {"hypothesis": "h"}, "", seconds=2)
            r.set_meta(p, action_id=f"g{g}a{i}", thread=tid, record_before=best.score)
    assert ag.thread_stats(tid)["due"] and "DUE" in ag.threads_block(4)
    ag.auto_park(4)
    assert ag.threads[tid]["status"] == "open" and ag.threads[tid]["due_since"] == 4
    ag.auto_park(6)
    assert ag.threads[tid]["status"] == "parked"


def test_agent_thread_count_survives_rewording_and_round_ten(tmp_path):
    from helix6.agent import action_order
    assert sorted(["g10a0", "g9auto", "g9a1", "g2a0"], key=action_order) == ["g2a0", "g9a1", "g9auto", "g10a0"]
    r = fake_run(tmp_path, "v6", gens=1)
    r.go()
    ag = r.memory
    refs, _ = ag.apply_ops(2, {"threads": [{"op": "open", "ref": "t1", "question": "q", "stop": "s"}]})
    tid = refs["t1"]
    best = r.archive.best()
    for g, i in ((8, 0), (9, 0), (10, 0)):     # three flat actions over three rounds, crossing round 10
        p = r.child6(g, "deep", best, KEEP + f"#{g}{i}\n", "x", {"hypothesis": "h"}, "", seconds=2)
        r.set_meta(p, action_id=f"g{g}a{i}", thread=tid, record_before=best.score)
    assert ag.thread_stats(tid)["due"]
    ag.apply_ops(10, {"threads": [{"op": "revise", "id": tid, "question": "q, reworded", "why": "w"}]})
    assert ag.thread_stats(tid)["due"], "rewording a thread that was not marked due must not reset its count"
    ag.auto_park(11)                                  # now it is marked due; a revision answers it
    assert ag.threads[tid]["due_since"] == 11
    ag.apply_ops(11, {"threads": [{"op": "revise", "id": tid, "question": "a different approach", "why": "w"}]})
    assert not ag.thread_stats(tid)["due"] and ag.threads[tid]["revised"] == 11


def test_agent_round_runs_every_action_kind(tmp_path):
    r = fake_run(tmp_path, "v6", gens=2)
    r.go()
    progs = list(r.archive.programs.values())
    assert {p.role for p in progs} >= {"deep", "wide", "continue"}
    cont = [p for p in progs if p.role == "continue"]
    assert all(p.code == r.archive.programs[p.parent].code and r.meta[p.id]["state"] == p.parent for p in cont)
    hist = [json.loads(l) for l in (r.dir / "history.jsonl").read_text().splitlines()][1:]
    assert all(sum(h["units"]) == r.cfg.units for h in hist)
    tr = [json.loads(l) for l in (r.dir / "trace.jsonl").read_text().splitlines()]
    agent = [t for t in tr if t["role"] == "agent"]
    assert agent and "States you can build on" in agent[-1]["user"] and "Your threads" in agent[-1]["user"]
    assert (r.dir / "threads.jsonl").exists() and (r.dir / "theory.jsonl").exists()
