"""Tests for Helix v4.5 and v5, and the C2 verifier.

    python -m pytest tests/test_helix5.py -q
"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix5-slots-"))

from helix4.archive import Program                   # noqa: E402
from helix4.llm import FakeLLM                       # noqa: E402
from helix5 import report as R5                      # noqa: E402
from helix5.evaluate import gain_label               # noqa: E402
from helix5.run import Config, Run, fake_answer      # noqa: E402
from tools import verify_ac2 as V                    # noqa: E402


# ---------------------------------------------------------------------------------------------- the claim
def test_alphaevolve_may_2025_reproduced_three_ways():
    r = V.verify(V.ALPHAEVOLVE_MAY_2025, "ae")
    assert r["N"] == 50 and r["agree"]
    assert abs(r["helix"] - 0.896279944155) < 1e-11 and abs(r["deepmind_code"] - 0.896279944155) < 1e-11
    assert r["exact_str"].startswith("0.89627994415")


def test_exact_check_for_large_constructions():
    h = np.abs(np.random.default_rng(0).standard_normal(6000)) ** 3
    r = V.verify(h)
    assert r["agree"] and "2^30" in r["exact_how"]


def test_gain_labels():
    assert gain_label(0.002) == "big gain" and gain_label(2e-5) == "gain"
    assert gain_label(1e-9) == "no real change" and gain_label(-1e-3) == "loss" and gain_label(None) == ""


# ---------------------------------------------------------------------------------------------- end to end
def fake_run(tmp_path, condition, gens=2, name=None, **kw):
    cfg = Config(condition=condition, gens=gens, budget=2, **kw)
    return Run(tmp_path / (name or condition), cfg, llm=FakeLLM(fake_answer), log=lambda m: None)


@pytest.mark.parametrize("condition", ["v45", "v5"])
def test_fake_run_end_to_end(tmp_path, condition):
    s = fake_run(tmp_path, condition, gens=6).go()
    d = tmp_path / condition
    hist = [json.loads(l) for l in (d / "history.jsonl").read_text().splitlines()]
    assert [h["gen"] for h in hist] == list(range(7)) and s["programs"] == 1 + 6 * 6
    roles = {json.loads(l)["role"] for l in (d / "trace.jsonl").read_text().splitlines()}
    assert {"researcher", "coder", "mutator"} <= roles
    if condition == "v45":
        assert {"navigator", "distiller"} <= roles and s["memory"]["findings"] >= 1
    else:
        assert {"lookup", "review"} <= roles
        assert s["memory"]["reviews"] == 1 and s["memory"]["steps"] >= 7
        progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
        deep = [p for p in progs if p["role"] == "deep"]
        assert all(p["plan"].get("item", "").startswith("A") and p["plan"].get("step", "").startswith("S") for p in deep)


def test_resume_drops_unfinished_generation_v5(tmp_path):
    r = fake_run(tmp_path, "v5", gens=3)
    r.go()
    d = tmp_path / "v5"
    with (d / "agenda.jsonl").open("a") as f:
        f.write(json.dumps({"op": "add", "id": "A99", "gen": 4, "step": "S99", "purpose": "half-done", "plan": "", "why": ""}) + "\n")
    with (d / "notebook.jsonl").open("a") as f:
        f.write(json.dumps({"op": "step", "id": "S99", "gen": 4, "kind": "round", "focus": [], "follows": [], "gist": "x"}) + "\n")
    r2 = Run(d, llm=FakeLLM(fake_answer), gens=4, log=lambda m: None)
    assert "A99" not in r2.memory.items and "S99" not in r2.memory.steps
    assert r2.go()["gens_done"] == 4


# ---------------------------------------------------------------------------------------------- the escape rule
def test_stalled_run_forces_an_escape(tmp_path):
    r = fake_run(tmp_path, "v45", gens=1, stall_gens=3)
    r.go()
    best = r.archive.best()
    for g in range(2, 7):                                    # five generations without a rise of 1e-4
        r._append("history.jsonl", {"gen": g, "best": best.score + 1e-7 * g, "best_id": best.id})
    assert r.stall(7) >= 3
    plan = {"experiments": [{"base": best.id, "hypothesis": f"h{i}", "change": "polish"} for i in range(3)]}
    exps = r.experiments(plan, 7)
    assert sum(e["fresh"] for e in exps) == 1 and exps[-1]["forced_escape"]
    plan["experiments"][0]["fresh"] = True                    # the planner already escaped: nothing forced
    assert not any(e.get("forced_escape") for e in r.experiments(plan, 7))


def test_fresh_child_runs_without_a_start(tmp_path):
    r = fake_run(tmp_path, "v45", gens=1)
    r.go()
    base = r.archive.best()
    code = "import numpy as np\ndef construct(b, start):\n    assert start is None\n    return np.ones(10)\n"
    p = r.child(2, "deep", base, code, "fresh test", {"fresh": True}, "", fresh=True)
    assert p.valid and p.delta is None and "fresh start" in p.feedback[0]


# ---------------------------------------------------------------------------------------------- v5's memory
def v5_with_steps(tmp_path):
    r = fake_run(tmp_path, "v5", gens=1)
    r.go()
    return r, r.memory


def test_v5_operations_versioning_and_no_drift(tmp_path):
    r, m = v5_with_steps(tmp_path)
    pid = r.archive.best().id
    js = {"thinking": "t", "gist": "g", "agenda": [{"op": "add", "ref": "n1", "purpose": "find X", "plan": "if a then b"}],
          "beliefs": [{"op": "add", "kind": "works", "statement": "X helps", "evidence": [pid, "p9999"]},
                      {"op": "add", "kind": "fails", "statement": "Y hurts", "evidence": [pid]}]}
    sid, applied, rejected, refmap = m.apply_step(2, "round", js, [])
    new_item = refmap["n1"]
    b_x = [b for b in m.beliefs.values() if b["statement"] == "X helps"][0]
    b_y = [b for b in m.beliefs.values() if b["statement"] == "Y hurts"][0]
    assert b_x["evidence"] == [pid]                           # unknown program ids never become evidence
    before_y = json.dumps(b_y, sort_keys=True)
    js2 = {"thinking": "t2", "gist": "g2", "agenda": [{"op": "revise", "id": new_item, "plan": "new plan", "why": "evidence"},
                                                      {"op": "done", "id": "A777", "outcome": "?"}],
           "beliefs": [{"op": "revise", "id": b_x["id"], "confidence": "high", "why": "more data"}]}
    _, applied2, rejected2, _ = m.apply_step(3, "round", js2, [])
    assert any("A777" in x for x in rejected2)
    it = m.items[new_item]
    assert it["plan"] == "new plan" and [v["op"] for v in it["versions"]] == ["add", "revise"]
    assert it["versions"][0]["plan"] == "if a then b"        # the old version stays reachable
    assert json.dumps(m.beliefs[b_y["id"]], sort_keys=True) == before_y   # untouched: word for word
    # a fresh load replays the same state
    from helix5.v5 import Researcher
    m2 = Researcher(r)
    assert m2.items[new_item]["plan"] == "new plan" and m2.beliefs[b_x["id"]]["confidence"] == "high"
    hist = m.lookup(new_item)
    assert "if a then b" in hist and "new plan" in hist and "evidence" in hist


def test_v5_continuity_follows_links_not_a_window(tmp_path):
    r, m = v5_with_steps(tmp_path)
    best = r.archive.best().id
    # S_a sets up item A on gen 2; several unrelated steps follow; then a step schedules for A
    sa, _, _, ref = m.apply_step(2, "round", {"thinking": "set up A", "gist": "A is about the penalty route",
                                              "agenda": [{"op": "add", "ref": "a", "purpose": "penalty route", "plan": "p"}]}, [])
    item_a = ref["a"]
    for g in range(3, 8):
        m.apply_step(g, "round", {"thinking": f"unrelated {g}", "gist": f"unrelated {g}"}, [])
    sb, _, _, _ = m.apply_step(8, "round", {"thinking": "schedule for A", "gist": "testing A"}, [item_a])
    exps = [{"eid": f"g8x{i}", "item": item_a, "step": sb, "base": best, "hypothesis": "h", "change": "c"} for i in range(3)]
    m.scheduled(8, {"experiments": exps}, exps)
    full, gists, focus = m.continuity(9)
    assert focus == [item_a] and full[0] == sb
    assert sa in full + gists                                 # the step that created the item comes back
    assert len(full) <= 4 and len(gists) <= 12
    block, _, _ = m.continuity_block(9)
    assert "penalty route" in block and "schedule for A" in block


def test_v5_lookups_and_search(tmp_path):
    r, m = v5_with_steps(tmp_path)
    pid = r.archive.best().id
    m.apply_step(2, "round", {"thinking": "the resolution ladder is promising", "gist": "ladder promising",
                              "beliefs": [{"op": "add", "kind": "works", "statement": "resolution ladder helps", "evidence": [pid]}]}, [])
    assert "ladder" in m.search("resolution ladder")
    sid = sorted(m.steps, key=lambda s: int(s[1:]))[-1]
    assert "ladder promising" in m.lookup(sid)
    assert pid in m.lookup(pid) and "nothing with that id" in m.lookup("Z1")


# ---------------------------------------------------------------------------------------------- the report
def test_combined_report_builds(tmp_path):
    fake_run(tmp_path / "runs", "v45", gens=2).go()
    fake_run(tmp_path / "runs", "v5", gens=2).go()
    out = R5.build([tmp_path / "runs", tmp_path / "missing"], tmp_path / "out")
    html = Path(out).read_text()
    assert "v5 (the researcher)" in html and "0.896280" in html and "What the v5 researcher kept" in html


def test_planning_call_is_capped_and_falls_back(tmp_path):
    """A planner that thinks past its budget is asked once more without thinking, instead of thinking twice as long."""
    from helix3.llm import Reply

    class CutLLM:
        supports_grow, calls, on_call = True, 0, None

        def chat(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", meta=None, tries=5, grow=True):
            self.calls += 1
            assert grow is False or effort == "none"
            if effort != "none":
                return Reply("", "x", 0, 0, 0, 1.0, "length")
            return Reply('{"experiments": [{"base": "p0001", "hypothesis": "h", "change": "c"}]}', "", 0, 0, 0, 1.0, "stop")

    r = Run(tmp_path / "cut", Config(condition="v45", gens=1, budget=2), llm=CutLLM(), log=lambda m: None)
    plan, info = r.researcher("sys", "user", 1)
    assert plan is not None and info["retried"] and r.llm.calls == 2
