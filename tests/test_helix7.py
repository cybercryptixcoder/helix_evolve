"""Tests for Helix v7 (helix7/): exploration that follows progress, tracks that are never closed, revive and
backtrack, the planner's slots, resuming, warm starts, calibration of the noise floor, and the prompts.

    python -m pytest tests/test_helix7.py -q
"""
import json
import os
import re
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix7-slots-"))

from helix4.archive import Program                       # noqa: E402
from helix4.llm import FakeLLM                           # noqa: E402
from helix7 import prompts as P                          # noqa: E402
from helix7.run import Config, Run, fake_answer          # noqa: E402

QUIET = dict(log=lambda m: None)

FLAT_CODE = '''import numpy as np
# flat variant {tag}
def construct(budget_seconds, start):
    return np.ones(50) if start is None else np.asarray(start, dtype=float)
'''


def flat_answer(role, system, user):
    """Programs that never change their start: the record never moves."""
    if role in ("coder", "mutator"):
        import random
        return "```python\n" + FLAT_CODE.replace("{tag}", str(random.randint(1, 10 ** 9))) + "```\nSUMMARY: no change"
    return fake_answer(role, system, user)


def make(tmp, gens, answer=fake_answer, **kw):
    cfg = Config(gens=gens, budget=2.0, **kw)
    return Run(tmp, cfg, llm=FakeLLM(answer), gens=gens, **QUIET)


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def prog(r, gen, parent, score, track=None, role="deep", **kw):
    par = r.archive.programs[parent]
    p = Program(id="", gen=gen, role=role, parent=parent, intent=f"test {score}", code=f"# {gen} {score} {track}",
                plan={"track": track} if track else {}, valid=True, score=score, start_score=par.score,
                delta=score - par.score, feedback=[f"score {score}"], **kw)
    return r.add(p)


# ---------------------------------------------------------------------------------------------- progress and level
def write_history(r, bests, start=0):
    (r.dir / "history.jsonl").write_text("".join(json.dumps({"gen": start + i, "best": b}) + "\n"
                                                 for i, b in enumerate(bests)))


def test_the_level_follows_the_runs_own_typical_gap(tmp_path):
    r = make(tmp_path / "a", 1)
    #           gen 0    1    2    3    4    5    6    7    8   (records at 2, 4, 6, 8: gaps 2, 2, 2, 2)
    write_history(r, [.5, .5, .6, .6, .7, .7, .8, .8, .9])
    assert r.records() == (0, [2, 4, 6, 8]) and r.typical_gap() == 2
    assert [r.level(g)[0] for g in (9, 11, 12, 14, 15)] == [0, 0, 1, 1, 2]       # s = 0, 2, 3, 5, 6
    # a creep below the floor is not a record, but creeps add up against the last record
    write_history(r, [.5, .5 + 1e-8, .5 + 2e-8, .5 + 2e-6])
    assert r.records() == (0, [3])
    write_history(r, [.5])
    assert r.typical_gap() == r.cfg.typical_default                               # too few gaps yet


def test_a_warm_start_counts_as_a_record(tmp_path):
    r = make(tmp_path / "a", 1)
    write_history(r, [.9] * 41, start=150)
    r.warm_gen = 190
    assert r.stall(191) == 0 and r.level(191)[0] == 0
    assert r.stall(195) == 4


# ---------------------------------------------------------------------------------------------- whole runs
def test_a_climbing_run_is_v4_shaped_after_a_broad_start(tmp_path):
    r = make(tmp_path / "a", 8)
    r.go()
    hist = jl(tmp_path / "a" / "history.jsonl")[1:]
    for h in hist:
        if h["gen"] <= r.cfg.early_gens:
            assert h["slots"].count("main") == 1 and len(h["slots"]) == 3          # broad: two explorations
        elif h["stall"] <= h["typical_gap"]:
            assert h["slots"] == ["main"] * 3                                     # climbing: v4's three main
    assert hist[0]["slots"] == ["main", "bold", "bold"]
    assert all(e in r.archive.programs for e in [h["best_id"] for h in hist])


def test_a_stall_opens_exploration_and_the_main_track_always_keeps_a_slot(tmp_path):
    r = make(tmp_path / "a", 12, answer=flat_answer)
    r.go()
    hist = jl(tmp_path / "a" / "history.jsonl")[1:]
    assert not any(h["new_best"] for h in hist)
    assert [h["level"] for h in hist] == [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2]      # typical gap 3: s > 3, s > 7
    for h in hist:
        assert h["slots"].count("main") >= 1
        assert len(h["slots"]) == 3
        if h["gen"] > r.cfg.early_gens:
            assert len(h["slots"]) - h["slots"].count("main") == h["level"]
    kinds = {s.split(":")[0] for h in hist for s in h["slots"]}
    assert {"main", "bold", "track"} <= kinds
    rows = jl(tmp_path / "a" / "tracks.jsonl")
    assert len(rows[-1]["tracks"]) >= 4
    assert not any("closed" in json.dumps(t) for t in rows[-1]["tracks"])         # nothing is ever closed
    assert all(p.code for p in r.archive.programs.values() if p.valid)


def test_resume_keeps_the_tracks_and_the_main_track(tmp_path):
    out = tmp_path / "a"
    make(out, 6, answer=flat_answer).go()
    before = jl(out / "tracks.jsonl")[-1]
    r = Run(out, llm=FakeLLM(flat_answer), gens=7, **QUIET)
    assert r.gen_done == 6 and r.tracks == {t["id"]: t for t in before["tracks"]} and r.main == before["main"]
    r.go()
    assert jl(out / "history.jsonl")[-1]["gen"] == 7


# ---------------------------------------------------------------------------------------------- tracks
def test_a_side_track_gets_a_follow_up_pauses_wakes_on_a_gain_and_can_take_the_record(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    seed = r.archive.best()
    r.sync_tracks()
    assert r.main_track() == "T1"
    tid = r.open_track(1, "bold", seed.id)
    c1 = prog(r, 1, seed.id, 0.5, tid)                                  # it starts worse than its base
    ev = r.update_tracks(1, [c1], [{"track": tid}], seed)
    t = r.tracks[tid]
    assert t["best"] == 0.5 and t["misses"] == 0 and r.live(t) and any("opened" in e for e in ev)
    c2 = prog(r, 2, c1.id, 0.49, tid)                                   # its follow-up doesn't gain
    ev = r.update_tracks(2, [c2], [{"track": tid}], seed)
    assert not r.live(t) and any("paused" in e for e in ev)
    c3 = prog(r, 3, c1.id, 0.55, tid, role="wide")                      # a wide-loop gain wakes it
    r.update_tracks(3, [c3], [], seed)
    assert r.live(t) and t["closing"] == pytest.approx(0.05 / (seed.score - 0.5))
    c4 = prog(r, 4, c3.id, seed.score + 0.01, tid)                      # it beats the record: it becomes main
    ev = r.update_tracks(4, [c4], [{"track": tid}], seed)
    assert r.main_track() == tid and not r.live(t) and any("took the record" in e for e in ev)
    assert r.live(r.tracks["T1"]) is False                             # the old main: a side track, not closed
    assert "T1" in r.tracks


def test_a_polish_below_the_floor_does_not_move_the_main_track(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    seed = r.archive.best()
    r.sync_tracks()
    tid = r.open_track(1, "revive", seed.id)
    c = prog(r, 1, seed.id, seed.score * (1 + 1e-8), tid)
    r.update_tracks(1, [c], [{"track": tid}], seed)
    assert r.archive.best().id == c.id and r.main_track() == "T1"


def test_live_tracks_owed_a_follow_up_come_first_then_the_fastest_closing(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    r.sync_tracks()
    a, b, c = (r.open_track(1, "bold", "p0001") for _ in range(3))
    r.tracks[a].update(best=0.6, closing=0.05)
    r.tracks[b].update(best=0.5, closing=0.5)
    r.tracks[c].update(best=0.4, closing=None)
    order = [t["id"] for t in sorted((r.tracks[x] for x in (a, b, c)), key=r.priority)]
    assert order == [c, b, a]
    slots = r.make_slots(3, 2)                                          # odd generation: both continue tracks
    assert [s.get("track") for s in slots[1:]] == [c, b]
    slots = r.make_slots(4, 2)                                          # even: one new direction
    assert slots[1].get("track") == c and slots[2]["kind"] in ("revive", "backtrack", "bold")


# ---------------------------------------------------------------------------------------------- slots and candidates
def test_experiments_follow_the_slots_and_their_bases_are_enforced(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    r.sync_tracks()
    seed = r.archive.best()
    p2 = prog(r, 1, seed.id, 0.70, "T1")
    p3 = prog(r, 1, seed.id, 0.69, "T1")
    alt = prog(r, 1, p3.id, 0.68, "T1", role="alt")
    side = r.open_track(1, "bold", seed.id)
    s1 = prog(r, 1, seed.id, 0.60, side)
    r.memory._append({"op": "new", "id": "F1", "gen": 1, "kind": "fails", "claim": "an idea that failed on p0001",
                      "evidence": [s1.id], "links": []})
    r.memory.rebuild()
    slots = [{"kind": "main"}, {"kind": "revive"}, {"kind": "backtrack"}, {"kind": "bold"},
             {"kind": "track", "track": side}]
    for n, s in enumerate(slots, 1):
        s["n"] = n
    slots[1]["options"] = r.revive_candidates()
    slots[2]["options"] = [pid for pid, _ in r.backtrack_candidates()]
    slots[4]["options"] = [p.id for p in r.track_members(r.tracks[side])]
    assert slots[1]["options"] == ["F1"] and alt.id in slots[2]["options"]
    plan = {"experiments": [
        {"slot": 1, "base": p3.id, "hypothesis": "h1", "change": "c1"},
        {"slot": 2, "base": seed.id, "hypothesis": "h2", "change": "c2", "revives": "F1"},
        {"slot": 3, "base": "p9999", "hypothesis": "h3", "change": "c3"},
        {"slot": 5, "base": p2.id, "hypothesis": "h5", "change": "c5"},
    ]}
    exps = r.experiments(plan, slots, 2)
    assert [e["slot"] for e in exps] == [1, 2, 3, 4, 5]
    assert exps[0]["base"] == p3.id and exps[0]["track"] == "T1"                    # main: the planner's choice
    assert exps[1]["base"] == r.archive.best().id and exps[1]["revives"] == "F1"    # revive: on the best
    assert exps[2]["base"] == slots[2]["options"][0] and exps[2]["base_requested"] == "p9999"
    assert exps[3]["base"] == seed.id and exps[3].get("fallback")                   # bold, unplanned: Code Zero
    assert exps[4]["base"] == s1.id and exps[4]["track"] == side                    # a track's base: its own
    new = {exps[i]["track"] for i in (1, 2, 3)}
    assert len(new) == 3 and all(r.tracks[t]["opened"] == 2 for t in new)
    assert r.revived[-1][0] == "F1"
    assert r.revive_candidates() == []                                              # revived once per record


def test_revive_skips_findings_on_the_best_and_ideas_already_in_its_lineage(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    r.sync_tracks()
    seed = r.archive.best()
    a = prog(r, 1, seed.id, 0.70)
    b = prog(r, 2, a.id, 0.71)
    x = prog(r, 2, a.id, 0.69)
    y = prog(r, 3, b.id, 0.70)
    other = prog(r, 1, seed.id, 0.69)
    w = prog(r, 2, other.id, 0.695)
    ev = [("F1", "fails", [y.id]),             # tried on the best itself: not a revive
          ("F2", "fails", [x.id]),             # tried on an ancestor of the best (a): yes
          ("F3", "works", [b.id]),             # an idea already in the best's lineage: no
          ("F4", "works", [w.id])]             # worked on another branch: yes
    for fid, kind, e in ev:
        r.memory._append({"op": "new", "id": fid, "gen": 3, "kind": kind, "claim": fid, "evidence": e, "links": []})
    r.memory.rebuild()
    y.delta = -0.01
    assert r.archive.best().id == b.id
    assert sorted(r.revive_candidates()) == ["F2", "F4"]


def test_backtrack_offers_alternatives_fork_points_other_branches_and_paused_tracks(tmp_path):
    r = make(tmp_path / "a", 1)
    r.seed()
    r.sync_tracks()
    seed = r.archive.best()
    a = prog(r, 1, seed.id, 0.70)
    b = prog(r, 2, a.id, 0.80)                 # a big gain from a: a is a fork point
    alt = prog(r, 2, a.id, 0.75, role="alt")
    o = prog(r, 1, seed.id, 0.68)              # another branch (split at Code Zero, far below)
    side = r.open_track(1, "bold", seed.id)
    s = prog(r, 1, seed.id, 0.67, side)
    r.tracks[side].update(best=0.67, best_id=s.id, misses=r.cfg.track_patience)
    got = dict(r.backtrack_candidates())
    assert alt.id in got and a.id in got and o.id in got and s.id in got and b.id not in got
    assert "alternative" in got[alt.id] and "before a gain" in got[a.id] and "another branch" in got[o.id]
    assert "paused" in got[s.id]


def test_wide_parents_broaden_when_stalled(tmp_path):
    import random
    r = make(tmp_path / "a", 1)
    r.seed()
    r.sync_tracks()
    seed = r.archive.best()
    mains = [prog(r, 1, seed.id, 0.70 + i / 1000, "T1") for i in range(5)]
    side = r.open_track(1, "bold", seed.id)
    s = prog(r, 1, seed.id, 0.6, side)
    pool = r.archive.valid()
    rng = random.Random(1)
    lv2 = [r.wide_parents(rng, pool, 2)[-1].id for _ in range(20)]
    assert all(r.track_of(r.archive.programs[p]) != "T1" for p in lv2)
    assert s.id in lv2 and mains


# ---------------------------------------------------------------------------------------------- the planner's view
def test_the_planner_sees_the_tree_the_tracks_and_its_slots(tmp_path):
    r = make(tmp_path / "a", 5, answer=flat_answer)
    r.go()
    user = [c for c in (json.loads(l) for l in (tmp_path / "a" / "trace.jsonl").read_text().splitlines())
            if c["role"] == "researcher" and c.get("gen") == 5][-1]["user"]
    assert "Map 1: the tree of attempts" in user and "starts track" in user
    assert "## Side tracks" in user and "## This generation's experiments, slot by slot" in user
    assert re.search(r"Slot 1 \(main\)", user) and "of 5" not in user                # no countdown
    assert "noise floor" in user


# ---------------------------------------------------------------------------------------------- warm starts
def test_warm_continue_from_a_v47_run_makes_its_lines_paused_tracks(tmp_path):
    from helix47.run import Config as C47, Run as R47, fake_answer as fake47
    from helix7.warm import prepare
    src = tmp_path / "v47"
    R47(src, C47(gens=6, budget=2.0, line_patience=2, stall_gain=1.0), llm=FakeLLM(fake47), gens=6, **QUIET).go()
    lines = jl(src / "lines.jsonl")[-1]["lines"]
    assert len(lines) >= 2
    out = tmp_path / "v7"
    prepare(src, out, "continue", budget=2.0)
    r = Run(out, llm=FakeLLM(fake_answer), gens=8, **QUIET)
    best = r.archive.best()
    assert r.gen_done == 6 and r.warm_gen == 6 and r.main_track() == r.track_of(best)
    ids = {ln["id"] for ln in lines} & set(r.tracks)
    assert ids and all(not r.live(r.tracks[i]) for i in ids)
    assert any("v4.7 run" in r.tracks[i]["source"] for i in ids)
    r.go()
    hist = jl(out / "history.jsonl")
    assert [h["gen"] for h in hist][-2:] == [7, 8] and hist[-2]["stall"] == 0 and hist[-2]["slots"] == ["main"] * 3


def test_warm_best_mode_starts_from_code_zero_and_the_best(tmp_path):
    from helix7.warm import prepare
    src = tmp_path / "s"
    make(src, 2).go()
    out = tmp_path / "b"
    prepare(src, out, "best", budget=2.0)
    r = Run(out, llm=FakeLLM(fake_answer), gens=3, **QUIET)
    assert [p.role for p in r.archive.programs.values()] == ["seed", "warm"] and r.main_track() == "T1"
    r.go()
    assert jl(out / "history.jsonl")[-1]["gen"] == 3


# ---------------------------------------------------------------------------------------------- calibration
def test_calibration_raises_the_floor_to_the_measured_noise(tmp_path):
    class Noisy(Run):
        def score_again(self, p, i):
            return p.score * (1 + 0.002 * (i + 1))

    r = Noisy(tmp_path / "a", Config(gens=1, budget=2.0, calibrate=2), llm=FakeLLM(fake_answer), gens=1, **QUIET)
    r.seed()
    noise = json.loads((tmp_path / "a" / "noise.json").read_text())
    assert len(noise["scores"]) == 3 and noise["rel"] == pytest.approx(0.004, rel=0.01)
    assert r.floor(1.0) == pytest.approx(noise["rel"])
    again = Run(tmp_path / "a", llm=FakeLLM(fake_answer), gens=1, **QUIET)
    assert again.noise == pytest.approx(noise["rel"])


# ---------------------------------------------------------------------------------------------- prompts
def test_prompts_carry_no_problem_specific_hints():
    texts = [v for k, v in vars(P).items() if k.isupper() and isinstance(v, str)]
    texts += [v for v in P.SLOT_TEXT.values()]
    words = r"autoconv|convolution|spike|comb|plateau|softmax|L-BFGS|Dinkelbach|resolution|upsampl|heights? of|saturat"
    for t in texts:
        found = re.findall(words, t, re.I)
        assert not found or found == ["heights"], found
    assert "closed for good" in P.RESEARCHER_SYSTEM and "{k}" in P.RESEARCHER_SYSTEM


def test_earlier_versions_prompts_are_unchanged_by_importing_v7():
    from helix4 import prompts as P4
    from helix47 import prompts as P47
    assert "confirm or refute" in P4.RESEARCHER_SYSTEM and "alternative" not in P4.CODER_SYSTEM
    assert "organised in lines" in P47.RESEARCHER_SYSTEM
