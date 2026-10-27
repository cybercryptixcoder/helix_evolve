"""Tests for the Helix v9 run (helix9/run.py, warm.py, replay.py, planted.py): a run end to end with a fake model,
resuming, the warm start from a v8 run through a continuation pack, rebuilding a missing construction, the planted
problem (drops, read-back, the race and the model on real coordinates), the replay, and the prompts.

    python -m pytest tests/test_helix9_run.py -q
"""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix9-slots-"))

from helix4.llm import FakeLLM                                     # noqa: E402
from helix9 import prompts as P                                    # noqa: E402
from helix9.planted import PlantedProblem, make_answer             # noqa: E402
from helix9.run import Config, Run, fake_answer                    # noqa: E402
from helix9.sim import Spec                                        # noqa: E402

QUIET = dict(log=lambda m: None)


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []


def fake_run(tmp, gens=3, **kw):
    r = Run(tmp, Config(gens=gens, budget=2.0, **kw), llm=FakeLLM(fake_answer), gens=gens, **QUIET)
    r.go()
    return r


def planted_run(tmp, gens, seed=1, fidelity=0.8, **kw):
    prob = PlantedProblem(Spec(warm=False, seed=seed))
    cfg = Config(gens=gens, budget=2.0, problem="planted", seed=seed, **kw)
    r = Run(tmp, cfg, llm=FakeLLM(make_answer(prob, fidelity=fidelity, seed=seed)), gens=gens, problem=prob, **QUIET)
    r.go()
    return r, prob


# ---------------------------------------------------------------------------------------------- end to end
def test_a_fake_run_writes_the_map_and_its_history(tmp_path):
    r = fake_run(tmp_path, gens=4)
    hist = [h for h in jl(tmp_path / "history.jsonl") if h["gen"] > 0]
    assert len(hist) == 4 and all("map" in h for h in hist)
    assert (tmp_path / "codebook.json").exists() and jl(tmp_path / "codebook.jsonl")[-1]["gen"] == 4
    assert len(r.cb.active_axes()) >= 8                                 # the generic questions
    assert len(jl(tmp_path / "coords.jsonl")) > 10                       # programs were read
    s = json.loads((tmp_path / "summary.json").read_text())
    assert s["version"] == "v9" and s["design_map"]["coords"] > 10


def test_resume_after_an_interruption_truncates_the_maps_files(tmp_path):
    fake_run(tmp_path, gens=3)
    # an unfinished generation 4: rows written, no checkpoint
    for f in ("coords.jsonl", "codebook.jsonl", "annotations.jsonl"):
        with (tmp_path / f).open("a") as fh:
            fh.write(json.dumps({"id": "p9999", "gen": 4, "coord": {}, "codebook": {}, "first": {}, "second": {}}) + "\n")
    r = Run(tmp_path, llm=FakeLLM(fake_answer), gens=5, **QUIET)
    assert r.gen_done == 3 and "p9999" not in r.coords
    assert all(row["gen"] <= 3 for row in jl(tmp_path / "codebook.jsonl"))
    r.go()
    assert r.gen_done == 5 and [h["gen"] for h in jl(tmp_path / "history.jsonl")][-2:] == [4, 5]


def test_a_missing_construction_is_rebuilt_from_its_ancestor(tmp_path):
    r = fake_run(tmp_path, gens=2)
    p = max((q for q in r.archive.valid() if q.role != "seed" and q.role != "alt"), key=lambda q: q.score)
    (tmp_path / "constructions" / f"{p.id}.npy").unlink()
    assert r.archive.construction(p.id) is None
    assert r.ensure_construction(p, 3) and r.archive.construction(p.id) is not None
    row = jl(tmp_path / "rebuilt.jsonl")[-1]
    assert row["id"] == p.id and row["ok"] and row["rebuilt"] is not None


# ---------------------------------------------------------------------------------------------- the planted problem
def test_the_planted_problem_drives_drops_read_back_the_race_and_the_model(tmp_path):
    r, prob = planted_run(tmp_path, gens=16)
    hist = [h for h in jl(tmp_path / "history.jsonl") if h["gen"] > 0]
    kinds = {t["kind"] for t in r.tracks.values()}
    assert {"drop", "flip"} <= kinds
    drops = [t for t in r.tracks.values() if t["kind"] == "drop"]
    assert all(t.get("target") and 2 <= len(t["target"]) <= 4 for t in drops)
    assert any(t.get("landing") for t in drops)                         # read back
    landed = [t["landing"] for t in drops if t.get("landing")]
    assert sum(l["matched"] for l in landed) > 0
    assert any((t.get("race") or {}).get("decisions") for t in r.tracks.values())
    assert r.model is not None and r.model.ready
    assert any(h["map"]["model_rows"] > 0 for h in hist)
    # the planner saw the design map and the drop's blueprint
    trace = [json.loads(l) for l in (tmp_path / "trace.jsonl").read_text().splitlines()]
    plans = [c["user"] for c in trace if c["role"] == "researcher"]
    assert any("## The design map" in u for u in plans) and any("(explore: drop)" in u for u in plans)
    coders = [c["user"] for c in trace if c["role"] == "coder"]
    assert any("This experiment builds a specific design" in u for u in coders)
    # coordinates are read in the codebook's ids, with the planted option names
    vals = [r.cb.value_name(v) for a in r.cb.active_axes() for v in r.cb.values(a)]
    assert any(re.fullmatch(r"option \d", v) for v in vals)


def test_a_coder_that_ignores_blueprints_is_caught_by_the_read_back(tmp_path):
    r, prob = planted_run(tmp_path, gens=10, fidelity=0.0, seed=2)
    landed = [t["landing"] for t in r.tracks.values() if t.get("landing")]
    assert landed and all(l["matched"] == 0 for l in landed)
    assert any(t.get("mismatch") for t in r.tracks.values() if t.get("landing"))
    trace = [json.loads(l) for l in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert any("doesn't yet make the target decisions" in c["user"] for c in trace if c["role"] in ("researcher", "coder"))


# ---------------------------------------------------------------------------------------------- the warm start
def test_a_warm_start_from_a_v8_run_on_github_with_a_pack(tmp_path):
    from helix8.run import Config as Config8, Run as Run8, fake_answer as fake8
    from helix9 import pack
    from helix9.warm import prepare
    src = tmp_path / "v8"
    r8 = Run8(src, Config8(gens=4, budget=2.0), llm=FakeLLM(fake8), gens=4, **QUIET)
    r8.go()
    # what GitHub holds: the run's files, without constructions
    gh = tmp_path / "github"
    gh.mkdir()
    for f in ("programs.jsonl", "findings.jsonl", "history.jsonl", "plans.jsonl", "tracks.jsonl", "hills.jsonl",
              "state.json", "best.npy"):
        if (src / f).exists():
            shutil.copy(src / f, gh / f)
    man = pack.build(gh, [str(src / "constructions")], log=lambda m: None)
    assert man["verified"] == man["valid"] and man["packed"]
    out = tmp_path / "v9"
    prepare(gh, out, pack=gh / "pack", seed=1, budget=2.0, log=lambda m: None)
    state = json.loads((out / "state.json").read_text())
    assert state["version"] == "v9" and state["warm_gen"] == 4
    for pid in man["packed"]:
        assert np.array_equal(np.load(out / "constructions" / f"{pid}.npy"), np.load(src / "constructions" / f"{pid}.npy"))
    r9 = Run(out, llm=FakeLLM(fake_answer), gens=6, **QUIET)
    assert r9.gen_done == 4 and len(r9.archive.programs) == len(r8.archive.programs)
    r9.go()
    assert r9.gen_done == 6 and len(r9.hills) >= 1


def test_the_retroactive_race_revives_paused_explorations_that_were_still_rising(tmp_path):
    from helix9.warm import retro_race
    out = tmp_path
    rows = []
    for g, (e, b) in enumerate([(1, 0.6), (2, 0.65), (4, 0.7), (6, 0.74)], 1):
        rows.append({"gen": g, "main": "T1", "tracks": [
            {"id": "T1", "kind": "seed", "exps": g, "best": 0.9, "opened": 0},
            {"id": "T2", "kind": "restart", "exps": e, "best": b, "opened": 1},
            {"id": "T3", "kind": "restart", "exps": min(e, 4), "best": 0.5, "opened": 1}]})
    (out / "tracks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    retro_race(out, Config(), log=lambda m: None)
    last = jl(out / "tracks.jsonl")[-1]["tracks"]
    t2 = next(t for t in last if t["id"] == "T2")
    t3 = next(t for t in last if t["id"] == "T3")
    assert t2["race"]["status"] == "running" and t3["race"]["status"] == "paused"
    assert "race" not in next(t for t in last if t["id"] == "T1")


# ---------------------------------------------------------------------------------------------- the replay
def test_the_replay_runs_end_to_end_and_seeds_a_warm_start(tmp_path):
    from helix8.run import Config as Config8, Run as Run8, fake_answer as fake8
    from helix9.replay import replay
    from helix9.warm import prepare
    src = tmp_path / "v8"
    Run8(src, Config8(gens=6, budget=2.0), llm=FakeLLM(fake8), gens=6, **QUIET).go()
    llm = FakeLLM(fake_answer)
    res = replay(src, tmp_path / "replay", lambda role, s, u, t, m: llm.chat(role, s, u).text, sample=10,
                 log=lambda m: None)
    assert (tmp_path / "replay" / "REPLAY.md").exists() and res["coords"] > 0
    out = tmp_path / "v9"
    prepare(src, out, replay=tmp_path / "replay", budget=2.0, log=lambda m: None)
    r9 = Run(out, llm=FakeLLM(fake_answer), gens=7, **QUIET)
    assert len(r9.coords) == res["coords"] and r9.cb.active_axes()


# ---------------------------------------------------------------------------------------------- the prompts
def test_prompts_carry_no_problem_specific_hints():
    from helix9 import annotate as A
    from helix9.run import SEED_AXES
    texts = [P.RESEARCHER_SYSTEM, P.DROP_CODER_NOTE, P.FLIP_CODER_NOTE, P.ABLATE_CODER_NOTE, P.MISS_NOTE, P.MAP_HEADER,
             P.DISCOVER_ASK, P.MATCH_ASK, P.CONSOLIDATE_ASK, P.MOVE_HINT, A.SYSTEM, A.DIFF_ASK, A.FULL_ASK,
             *P.SLOT_TEXT.values(), *SEED_AXES]
    banned = r"autocorrel|convol|f\*f|step function|route|vehicle|truck|village|depot|softmax|soft-max|l-bfgs|" \
             r"lbfgs|comb|spiky|resolution|zeros|support|plateau|peak|greedy|annealing|tabu|2-opt|insertion"
    for t in texts:
        assert not re.search(banned, t, re.I), (t[:80], re.search(banned, t, re.I).group(0))


def test_earlier_versions_are_unchanged_by_importing_v9():
    import helix8.run as r8
    import helix7.run as r7
    assert r8.Run.VERSION == "v8" and r7.Run.VERSION == "v7"
    assert r8.Run.make_slots is not Run.make_slots and r8.Config is not Config
