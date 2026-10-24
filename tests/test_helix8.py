"""Tests for Helix v8 (helix8/): the shape signature and distance, moved-only track bests, the register of hills
(landing, founding, carrying, the fixed starting hill), the warm start's map, the map in the planner's view, flips
and restarts, resuming, and the prompts.

    python -m pytest tests/test_helix8.py -q
"""
import json
import os
import random
import re
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix8-slots-"))

from helix4.archive import Program                       # noqa: E402
from helix4.llm import FakeLLM                           # noqa: E402
from helix8 import prompts as P                          # noqa: E402
from helix8.hills import shape_distance, shape_signature  # noqa: E402
from helix8.run import Config, Run, fake_answer          # noqa: E402

QUIET = dict(log=lambda m: None)


def make(tmp, gens=1, answer=fake_answer, **kw):
    return Run(tmp, Config(gens=gens, budget=2.0, **kw), llm=FakeLLM(answer), gens=gens, **QUIET)


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def shape(kind, n=400):
    x = (np.arange(n) + 0.5) / n
    if kind == "decay":          # the textbook-like shape
        return 1 / np.sqrt(x)
    if kind == "bump":
        return np.exp(-((x - 0.5) / 0.12) ** 2)
    if kind == "steps":
        return np.where(x < 0.3, 2.0, np.where(x < 0.7, 0.4, 1.5))
    if kind == "ramp":
        return 0.2 + x
    raise ValueError(kind)


def prog(r, gen, parent, score, track=None, construction=None, role="deep", **plan):
    par = r.archive.programs[parent]
    p = Program(id="", gen=gen, role=role, parent=parent, intent=f"test {score}", code=f"# {gen} {score} {random.random()}",
                plan={"track": track, **plan} if track else dict(plan), valid=True, score=score,
                start_score=par.score, delta=score - par.score, feedback=[f"score {score}"])
    return r.add(p, construction)


def seeded(tmp):
    r = make(tmp)
    r.seed()
    r.sync_tracks()
    return r


# ---------------------------------------------------------------------------------------------- the shape distance
def test_the_shape_distance_ignores_what_the_score_ignores():
    a = shape("decay")
    sa = shape_signature(a)
    assert abs(sa.sum() - 1) < 1e-12
    assert shape_distance(sa, shape_signature(3.7 * a)) < 1e-12                          # scale
    assert shape_distance(sa, shape_signature(a[::-1])) < 1e-12                          # mirror
    assert shape_distance(sa, shape_signature(np.concatenate([np.zeros(77), a, np.zeros(5)]))) < 1e-12  # padding
    assert shape_distance(sa, shape_signature(np.repeat(a, 4))) < 0.01                   # a 4x staircase
    for other in ("bump", "steps", "ramp"):
        assert shape_distance(sa, shape_signature(shape(other))) > 0.1
    assert shape_signature(np.zeros(10)) is None and shape_distance(None, sa) is None


def test_the_default_radius_separates_the_earlier_runs_bests():
    """On the bests of earlier runs (results/): the textbook constructions of different runs are within the radius
    of each other; v4.7's record and v7's polish of it are too; different families are not."""
    root = Path(__file__).resolve().parent.parent / "results"
    need = {k: root / k / "best.npy" for k in ("v4/control-s1", "v4/atlas-s3", "v5/v45-s1", "v47warm/v47-s2",
                                               "v7warm/v7-s1", "v4/atlas-s1", "v4/journal-s1")}
    if not all(f.exists() for f in need.values()):
        pytest.skip("earlier results not present")
    s = {k: shape_signature(np.load(f)) for k, f in need.items()}
    r = Config().hill_radius
    assert shape_distance(s["v4/control-s1"], s["v4/atlas-s3"]) < r and shape_distance(s["v4/control-s1"], s["v5/v45-s1"]) < r
    assert shape_distance(s["v47warm/v47-s2"], s["v7warm/v7-s1"]) < r
    assert shape_distance(s["v7warm/v7-s1"], s["v4/atlas-s1"]) > r and shape_distance(s["v7warm/v7-s1"], s["v4/control-s1"]) > r
    assert shape_distance(s["v4/journal-s1"], s["v4/atlas-s1"]) > r


# ---------------------------------------------------------------------------------------------- moved-only bests
def test_an_unchanged_copy_of_the_start_is_not_a_tracks_best(tmp_path):
    r = seeded(tmp_path / "a")
    seed = r.archive.best()
    rec = prog(r, 1, seed.id, 0.80, "T1", shape("decay"))
    tid = r.open_track(2, "flip", rec.id, flips="D1: how it starts")
    copy = prog(r, 2, rec.id, 0.80, tid, shape("decay"))              # the change failed: the start handed back
    assert not r.moved(copy) and r.moved(rec)
    r.update_tracks(2, [copy], [{"track": tid}], rec)
    t = r.tracks[tid]
    assert t["best"] is None and t["closing"] is None and r.live(t)   # still owed its follow-up
    low = prog(r, 3, rec.id, 0.70, tid, shape("bump"))                 # the flipped design, below the record
    r.update_tracks(3, [low], [{"track": tid}], rec)
    assert t["best"] == 0.70 and t["misses"] == 0
    up = prog(r, 4, low.id, 0.72, tid, shape("bump") * 1.01 + 0.001)
    r.update_tracks(4, [up], [{"track": tid}], rec)
    assert t["best"] == 0.72                                          # it climbs against its own best, not the record


def test_flips_and_restarts_get_two_follow_ups(tmp_path):
    r = seeded(tmp_path / "a")
    seed = r.archive.best()
    tid = r.open_track(1, "restart", seed.id)
    a = prog(r, 1, seed.id, 0.70, tid, shape("bump"))
    r.update_tracks(1, [a], [{"track": tid}], seed)
    for g in (2, 3):
        b = prog(r, g, a.id, 0.69, tid, shape("bump") + 0.01 * g)
        r.update_tracks(g, [b], [{"track": tid}], seed)
    assert r.tracks[tid]["misses"] == 2 and not r.live(r.tracks[tid])
    old = r.open_track(1, "backtrack", seed.id)
    assert r.patience(r.tracks[old]) == 1


# ---------------------------------------------------------------------------------------------- the register
def place_all(r, gen):
    ev = []
    r.update_hills(gen, ev)
    return ev


def test_hills_are_founded_landed_on_and_carried(tmp_path):
    r = seeded(tmp_path / "a")
    seed = r.archive.best()
    rec = prog(r, 1, seed.id, 0.85, "T1", shape("decay"))
    r.tracks["T1"].update(best=0.85, best_id=rec.id)
    ev = place_all(r, 1)
    start = next(h for h in r.hills.values() if h.get("fixed"))
    main = r.hills[r.tracks["T1"]["hill"]]
    assert start["top"] == seed.id and main["top"] == rec.id and len(r.hills) == 2 and "map begins" in ev[-1]
    # a restart lands on the record's hill, below its top: a rediscovery, and it stops
    t1 = r.open_track(2, "restart", seed.id)
    x = prog(r, 2, seed.id, 0.80, t1, shape("decay") * 2 + 1e-3)
    r.update_tracks(2, [x], [{"track": t1}], rec)
    ev = place_all(r, 2)
    assert r.tracks[t1]["hill_status"] == "on" and r.tracks[t1]["hill"] == main["id"] and main["reached"] == 1
    assert not r.live(r.tracks[t1]) and any("landed on" in e for e in ev)
    # a restart far from every hill is a candidate after its opening, and founds a hill after a follow-up
    t2 = r.open_track(3, "restart", seed.id)
    y = prog(r, 3, seed.id, 0.70, t2, shape("steps"))
    r.update_tracks(3, [y], [{"track": t2}], rec)
    place_all(r, 3)
    assert r.tracks[t2]["hill_status"] == "candidate" and len(r.hills) == 2
    y2 = prog(r, 4, y.id, 0.72, t2, shape("steps") + 0.005)
    r.update_tracks(4, [y2], [{"track": t2}], rec)
    ev = place_all(r, 4)
    new = r.hills[r.tracks[t2]["hill"]]
    assert r.tracks[t2]["hill_status"] == "founder" and new["top"] == y2.id and any("new hill" in e for e in ev)
    # it carries its hill as it climbs, even far: no new hill per step
    y3 = prog(r, 5, y2.id, 0.75, t2, shape("steps") ** 2)
    r.update_tracks(5, [y3], [{"track": t2}], rec)
    place_all(r, 5)
    assert new["top"] == y3.id and len(r.hills) == 3
    # the starting program's hill never moves
    t3 = r.open_track(6, "restart", rec.id)
    z = prog(r, 6, rec.id, 0.70, t3, np.ones(50) * 1.0001)                 # back to the start's shape
    r.update_tracks(6, [z], [{"track": t3}], rec)
    place_all(r, 6)
    assert start["top"] == seed.id and r.tracks[t3]["hill"] == start["id"] and r.tracks[t3]["hill_status"] == "on"


def test_a_track_that_beats_a_hills_top_holds_it(tmp_path):
    r = seeded(tmp_path / "a")
    seed = r.archive.best()
    rec = prog(r, 1, seed.id, 0.85, "T1", shape("decay"))
    r.tracks["T1"].update(best=0.85, best_id=rec.id)
    place_all(r, 1)
    t = r.open_track(2, "flip", rec.id, flips="D1")
    x = prog(r, 2, rec.id, 0.86, t, shape("decay") + 1e-4)
    r.update_tracks(2, [x], [{"track": t}], rec)
    place_all(r, 2)
    h = r.hills[r.tracks[t]["hill"]]
    assert r.tracks[t]["hill_status"] == "top" and h["top"] == x.id


# ---------------------------------------------------------------------------------------------- warm starts
def test_a_warm_start_from_a_v7_run_maps_its_tracks(tmp_path):
    from helix7.run import Config as C7, Run as R7, fake_answer as fake7
    from helix8.warm import prepare
    src = tmp_path / "v7"
    R7(src, C7(gens=5, budget=2.0), llm=FakeLLM(fake7), gens=5, **QUIET).go()
    out = tmp_path / "v8"
    prepare(src, out, "continue", budget=2.0)
    assert (out / "tracks.jsonl").exists()
    r = Run(out, llm=FakeLLM(fake_answer), gens=6, **QUIET)
    assert r.gen_done == 5 and r.warm_gen == 5 and r.cfg.hill_radius == Config().hill_radius and not r.hills
    r.go()
    rows = jl(out / "hills.jsonl")
    assert rows and len(rows[0]["hills"]) >= 2
    hist = jl(out / "history.jsonl")
    assert hist[-1]["gen"] == 6 and "map begins" in " ".join(hist[-1]["track_events"])
    assert hist[-1]["slots"] == ["main"] * 3                                   # a warm start: no exploration yet


# ---------------------------------------------------------------------------------------------- whole runs
TEXTBOOK = '''import numpy as np
# fixed {tag}
def construct(budget_seconds, start):
    x = (np.arange(400) + 0.5) / 400
    return 1 / np.sqrt(x)
'''
FLAT = '''import numpy as np
# flat {tag}
def construct(budget_seconds, start):
    return np.ones(50) if start is None else np.asarray(start, dtype=float)
'''


def textbook_answer(role, system, user):
    """Restarts always write the same 'textbook' construction; everything else hands back its start."""
    if role in ("coder", "mutator"):
        code = TEXTBOOK if "towards a new design" in user else FLAT
        return "```python\n" + code.replace("{tag}", str(random.randint(1, 10 ** 9))) + "```\nSUMMARY: x"
    return fake_answer(role, system, user)


def test_restarts_that_land_on_a_known_hill_are_caught(tmp_path):
    out = tmp_path / "a"
    r = make(out, 14, answer=textbook_answer)
    r.go()
    tracks = {t["id"]: t for t in jl(out / "tracks.jsonl")[-1]["tracks"]}
    restarts = [t for t in tracks.values() if t["kind"] == "restart" and t.get("best_id")]
    assert len(restarts) >= 3
    hills = {h["id"]: h for h in jl(out / "hills.jsonl")[-1]["hills"]}
    home = [h for h in hills.values() if h["founder"] in {t["id"] for t in restarts}]
    assert len(home) == 1                                                   # one textbook hill, found once
    landed = [t for t in restarts if t["hill"] == home[0]["id"] and t["hill_status"] == "on"]
    assert len(landed) >= 2 and home[0]["reached"] >= 2 and not any(r.live(t) for t in landed)
    user = [c for c in (json.loads(l) for l in (out / "trace.jsonl").read_text().splitlines())
            if c["role"] == "researcher"][-1]["user"]
    assert "## The map: hills found so far" in user and "other tracks landed on it" in user


def test_the_planner_sees_the_map_flips_and_restarts(tmp_path):
    out = tmp_path / "a"
    make(out, 3).go()
    calls = [json.loads(l) for l in (out / "trace.jsonl").read_text().splitlines()]
    first = [c for c in calls if c["role"] == "researcher" and c.get("gen") == 1][-1]
    assert "explore: flip a shared decision" in first["user"] and "explore: a new hill" in first["user"]
    assert '"flips"' in first["user"] and "hills found so far" in first["system"] + first["user"]
    assert any(c["role"] == "cartographer" for c in calls)
    plans = jl(out / "plans.jsonl")
    flip = next(e for e in plans[0]["experiments"] if e["kind"] == "flip")
    assert flip["flips"] == "D1"
    coder = [c for c in calls if c["role"] == "coder" and "every known solution shares" in c["user"]]
    assert coder and "how the first construction is built" in coder[0]["user"]
    restart = [c for c in calls if c["role"] == "coder" and "towards a new design" in c["user"]]
    assert restart and "rather than rediscovering them" in restart[0]["user"]
    hills = jl(out / "hills.jsonl")[-1]
    assert hills["shared"] and hills["flipped"][0][0] == "D1"


def test_resume_keeps_the_map_and_drops_stale_signatures(tmp_path):
    out = tmp_path / "a"
    make(out, 3).go()
    before = jl(out / "hills.jsonl")[-1]
    (out / "signatures.jsonl").write_text(json.dumps({"id": "p9999", "sig": [1.0]}) + "\n")
    r = Run(out, llm=FakeLLM(fake_answer), gens=4, **QUIET)
    assert {h["id"] for h in r.hills.values()} == {h["id"] for h in before["hills"]} and r.shared == before["shared"]
    assert "p9999" not in r.signatures and not jl(out / "signatures.jsonl")
    r.go()
    assert jl(out / "history.jsonl")[-1]["gen"] == 4


# ---------------------------------------------------------------------------------------------- prompts
def test_prompts_carry_no_problem_specific_hints():
    texts = [v for k, v in vars(P).items() if k.isupper() and isinstance(v, str)] + list(P.SLOT_TEXT.values())
    words = r"autoconv|convolution|spike|comb|plateau|softmax|L-BFGS|Dinkelbach|resolution|upsampl|heights? of|saturat"
    for t in texts:
        found = re.findall(words, t, re.I)
        assert not found or found == ["heights"], found


def test_earlier_versions_are_unchanged_by_importing_v8():
    from helix4 import prompts as P4
    from helix7 import prompts as P7
    from helix7.run import Run as R7
    assert "confirm or refute" in P4.RESEARCHER_SYSTEM and "hills" not in P7.RESEARCHER_SYSTEM
    assert R7.VERSION == "v7" and Run.VERSION == "v8"
