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
    h = np.abs(np.random.default_rng(0).standard_normal(3000)) ** 3
    r = V.verify(h)
    assert r["agree"] and "float heights themselves" in r["exact_how"]
    h = np.abs(np.random.default_rng(1).standard_normal(15000)) ** 3
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


# ---------------------------------------------------------------------------------------------- the portfolio
def test_portfolio_roles_and_their_enforcement(tmp_path):
    r = fake_run(tmp_path, "v45", gens=2)
    r.go()
    assert r.roles(1) == ["deepen", "explore", "explore"]
    best = r.archive.best()
    line = [q.id for q in r.archive.lineage(best.id, depth=100)]
    # history decides: flat -> one of each; a rise of >= 0.001 -> two deepen slots
    for g, v in ((3, best.score), (4, best.score + 0.002)):
        r._append("history.jsonl", {"gen": g, "best": v, "best_id": best.id})
    r._roles_cache = {}
    assert r.roles(4) == ["deepen", "branch", "explore"]
    assert r.roles(5) == ["deepen", "deepen", "explore"] and r.roles(6) == ["deepen", "deepen", "branch"]
    off = next(q for q in r.archive.ranked() if q.id not in line)
    plan = {"experiments": [{"role": "explore", "base": best.id, "hypothesis": "x", "change": "c"},
                            {"role": "deepen", "base": off.id, "hypothesis": "d", "change": "c"},     # not on the line
                            {"role": "branch", "base": best.id, "hypothesis": "b", "change": "c"}]}   # the best itself
    exps = r.experiments(plan, 4)
    by = {e["role"]: e for e in exps}
    assert [e["role"] for e in exps] == ["deepen", "branch", "explore"]
    assert by["deepen"]["base"] in line and not by["deepen"]["fresh"]
    assert by["branch"]["base"] != best.id and not by["branch"]["fresh"]
    assert by["explore"]["fresh"] and by["explore"]["hypothesis"] == "x"


def test_lines_and_branch_candidates_favour_young_lines(tmp_path):
    r = fake_run(tmp_path, "v45", gens=2)
    r.go()
    base = r.archive.best()
    code = "import numpy as np\ndef construct(b, start):\n    return np.ones(12)\n"
    young = r.child(3, "deep", base, code, "fresh line", {"fresh": True, "role": "explore"}, "", fresh=True)
    assert r.root_of(young) == young.id and len(r.lines()) >= 2
    cands = r.branch_candidates(4)
    assert cands[0][0].id == young.id and "line started by" in cands[0][1]


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
    js = {"thinking": "t", "gist": "g", "agenda": [{"op": "add", "ref": "n1", "question": "find X", "plan": "if a then b n1"}],
          "beliefs": [{"op": "add", "kind": "works", "statement": "X helps", "evidence": [pid, "p9999"]},
                      {"op": "add", "kind": "fails", "statement": "Y hurts", "evidence": [pid]}]}
    sid, applied, rejected, refmap = m.apply_step(2, "round", js, [])
    new_item = refmap["n1"]
    assert "n1" not in m.items[new_item]["plan"] and new_item in m.items[new_item]["plan"]   # refs become ids
    assert m.items[new_item]["stop"]                                                          # a default stop rule
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
    assert "if a then b" in it["versions"][0]["plan"]         # the old version stays reachable
    assert json.dumps(m.beliefs[b_y["id"]], sort_keys=True) == before_y   # untouched: word for word
    from helix5.v5 import Researcher
    m2 = Researcher(r)
    assert m2.items[new_item]["plan"] == "new plan" and m2.beliefs[b_x["id"]]["confidence"] == "high"
    hist = m.lookup(new_item)
    assert "if a then b" in hist and "new plan" in hist and "evidence" in hist


def test_v5_beliefs_are_falsifiable_and_limit_claims_are_conjectures(tmp_path):
    r, m = v5_with_steps(tmp_path)
    pid = r.archive.best().id
    js = {"thinking": "t", "gist": "g", "beliefs": [
        {"op": "add", "kind": "mechanism", "statement": "flat tops help"},                          # no refuted_if
        {"op": "add", "kind": "works", "statement": "observation without evidence"},               # no evidence
        {"op": "add", "kind": "mechanism", "statement": "flat tops help", "refuted_if": "a peaked f*f scoring higher"},
        {"op": "add", "kind": "works", "statement": "The true maximum of R is 0.8825", "confidence": "high",
         "evidence": [pid]}]}
    _, applied, rejected, _ = m.apply_step(2, "round", js, [])
    assert len(rejected) == 2 and any("refuted_if" in x for x in rejected) and any("cite" in x for x in rejected)
    conj = [b for b in m.beliefs.values() if "maximum" in b["statement"]][0]
    assert conj["kind"] == "conjecture" and m.effective_confidence(conj) == "low" and conj["refuted_if"]
    for g in (3, 4):                                           # it survives two challenges: confidence can rise
        m.apply_step(g, "round", {"thinking": "c", "gist": "c", "beliefs": [
            {"op": "revise", "id": conj["id"], "challenge_outcome": "held", "why": "held"}]}, [])
    assert m.effective_confidence(m.beliefs[conj["id"]]) == "high"
    assert "challenge" in m.adjust_roles(3, ["deepen", "branch", "explore"])


def test_v5_due_threads_are_parked_by_their_stop_rule(tmp_path):
    r, m = v5_with_steps(tmp_path)
    best = r.archive.best()
    sid, _, _, ref = m.apply_step(2, "round", {"thinking": "t", "gist": "g", "agenda": [
        {"op": "add", "ref": "a", "question": "does X help?", "plan": "try X"}]}, [])
    iid = ref["a"]
    from helix4.archive import Program
    for i in range(3):                                          # three experiments without a real gain
        r.add(Program(id="", gen=3 + i, role="deep", parent=best.id, intent="x", code=f"# {i}\n", valid=True,
                      score=best.score, delta=0.0, plan={"item": iid, "step": sid, "eid": f"g{3 + i}x0"}))
    assert m.thread_stats(m.items[iid])["due"]
    m._due_shown = []
    assert "DUE" in m.agenda_block() and iid in m._due_shown
    m.apply_step(6, "round", {"thinking": "ignored it", "gist": "ignored", "_due_shown": [iid]}, [])
    assert m.auto_park(7) == [iid] and m.items[iid]["status"] == "parked"
    assert m.items[iid]["versions"][-1]["step"] == "system"


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


def test_v5_step_kind_is_not_overwritten_by_belief_kinds(tmp_path):
    r, m = v5_with_steps(tmp_path)
    pid = r.archive.best().id
    sid, _, _, _ = m.apply_step(2, "round", {"thinking": "t", "gist": "g", "beliefs": [
        {"op": "add", "kind": "conjecture", "statement": "s", "refuted_if": "r"},
        {"op": "add", "kind": "works", "statement": "w", "evidence": [pid]}]}, [])
    assert m.steps[sid]["kind"] == "round"
    from helix5.v5 import Researcher
    assert Researcher(r).steps[sid]["kind"] == "round"


# ---------------------------------------------------------------------------------------------- lessons of the v4 job
def test_steady_climb_keeps_two_deepen_slots(tmp_path):
    r = fake_run(tmp_path, "v45", gens=2)
    r.go()
    best = r.archive.best()
    for g, v in ((3, best.score + 0.0002), (4, best.score + 0.0005)):     # two small real rises in a row
        r._append("history.jsonl", {"gen": g, "best": v, "best_id": best.id})
    r._roles_cache = {}
    assert r.roles(5)[:2] == ["deepen", "deepen"]
    r._append("history.jsonl", {"gen": 5, "best": best.score + 0.0005, "best_id": best.id})   # then flat
    assert r.roles(6) == ["deepen", "branch", "explore"]


def test_shared_gains_are_marked_and_not_counted_as_evidence(tmp_path):
    from helix5 import v45, v5
    r = fake_run(tmp_path, "v45", gens=1)
    r.go()
    zero = r.archive.programs["p0001"]
    code = "import numpy as np\ndef construct(b, start):\n    return (np.arange(50) + 0.5) ** -0.5\n"
    a = r.child(2, "deep", zero, code + "# change A\n", "change A", {"role": "deepen"}, "")
    b = r.child(2, "deep", zero, code + "# change B\n", "change B", {"role": "branch"}, "")
    assert a.valid and b.valid and a.delta > 1e-3 and a.score == b.score
    assert r.mark_shared([a, b]) == 2
    assert a.plan["shared_gain_with"] == [b.id] and "code they share" in a.feedback[-1]
    assert v45.outcome(a) == "shared" and v5.outcome(b) == "shared" and "shared code" in v45.result_text(a)
    again = [json.loads(l) for l in (r.dir / "programs.jsonl").read_text().splitlines()]
    assert next(x for x in again if x["id"] == a.id)["plan"]["shared_gain_with"] == [b.id]
    assert r.mark_shared([a]) == 0


def test_tried_since_the_last_rise_is_listed_when_stalled(tmp_path):
    r = fake_run(tmp_path, "v45", gens=2)
    r.go()
    best = r.archive.best()
    code = "import numpy as np\ndef construct(b, start):\n    return start\n"
    r.child(3, "deep", best, code, "a different surrogate for the max", {"role": "deepen"}, "")
    for g in (3, 4):
        r._append("history.jsonl", {"gen": g, "best": best.score, "best_id": best.id})
    text = r.progress_block(5)
    assert "since generation" in text and "a different surrogate for the max" in text and "kind of change" in text


def test_stage_lines_come_back_and_the_cpu_limit_keeps_the_best(tmp_path):
    from helix4.problems import ac2
    from helix5.evaluate import evaluate
    noisy = ("import numpy as np\ndef construct(b, start):\n    print('stage coarse: 0.66 -> 0.80, 1.0 s')\n"
             "    for i in range(200):\n        print('progress line', i, 'x' * 40)\n"
             "    print('stage polish: 0.80 -> 0.81, 2.0 s')\n    return np.array([1.0, 0.4, 0.4, 1.0])\n")
    res = evaluate(ac2, noisy, None, 2)
    assert res["valid"] and any("its stage lines: stage coarse" in l and "stage polish" in l for l in res["feedback"])
    forever = ("import numpy as np\ndef construct(b, start):\n    keep_best(np.array([1.0, 0.4, 0.4, 1.0]))\n"
               "    while True:\n        sum(range(1000))\n")
    res = evaluate(ac2, forever, None, 1)
    assert res["valid"] and res["stopped"] == "cpu" and any("stopped at the CPU limit" in l for l in res["feedback"])
    res = evaluate(ac2, forever.replace("    keep_best(np.array([1.0, 0.4, 0.4, 1.0]))\n", ""), None, 1)
    assert not res["valid"] and "nothing kept" in res["error"]
