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


def test_a_missing_construction_is_copied_from_a_local_folder_only_if_it_verifies(tmp_path, monkeypatch):
    r = fake_run(tmp_path / "run", gens=2)
    p = max((q for q in r.archive.valid() if q.role not in ("seed", "alt")), key=lambda q: q.score)
    local = tmp_path / "local"
    local.mkdir()
    good = np.load(tmp_path / "run" / "constructions" / f"{p.id}.npy")
    (tmp_path / "run" / "constructions" / f"{p.id}.npy").unlink()
    np.save(local / f"{p.id}.npy", good * 1.5 + 0.1)                   # a wrong one: must not be used
    monkeypatch.setenv("HELIX9_LOCAL_CONSTRUCTIONS", str(local))
    r2 = Run(tmp_path / "run", llm=FakeLLM(fake_answer), gens=3, **QUIET)
    assert r2.has_construction(p) and r2.from_local(p) is None
    np.save(local / f"{p.id}.npy", good)                               # the right one: copied, verified
    assert r2.ensure_construction(p, 3)
    assert np.array_equal(r2.archive.construction(p.id), good)
    row = jl(tmp_path / "run" / "rebuilt.jsonl")[-1]
    assert row["how"] == "local" and row["faithful"]


def test_a_rebuild_starts_from_the_closest_output_when_the_ancestors_are_far(tmp_path):
    r = fake_run(tmp_path, gens=5)
    for q in r.archive.valid():                       # every program's signature, as a pack provides them
        if q.id not in r.signatures and r.output_signature(q) is not None:
            r.signatures[q.id] = r.output_signature(q)
    deep = []
    for q in r.archive.valid():
        chain, a = [], q
        while a is not None and a.parent:
            a = r.archive.programs.get(a.parent)
            if a is not None:
                chain.append(a)
        if len(chain) >= 4 and q.id in r.signatures:
            deep.append((q, chain))
    assert deep
    q, chain = deep[-1]
    for a in [q] + chain[:3]:
        f = tmp_path / "constructions" / f"{a.id}.npy"
        if f.exists() and a.role != "seed":
            f.unlink()
    start, why = r.rebuild_start(q)
    assert start is not None and r.archive.construction(start.id) is not None
    assert "most like" in why or "steps up" in why
    assert r.ensure_construction(q, 6)
    row = jl(tmp_path / "rebuilt.jsonl")[-1]
    assert row["id"] == q.id and row["how"] == "rebuilt" and "faithful" in row


def test_the_wide_loop_samples_programs_whose_construction_is_at_hand(tmp_path):
    import random as _r
    r = fake_run(tmp_path, gens=3)
    pool = [q for q in r.archive.valid()]
    gone = {q.id for q in pool[1::2] if q.role != "seed"}
    for pid in gone:
        (tmp_path / "constructions" / f"{pid}.npy").unlink()
    rng = _r.Random(1)
    picks = [p.id for _ in range(40) for p in r.wide_parents(rng, pool, 0)]
    assert picks and not (set(picks) & gone)


def test_the_retroactive_race_caps_how_many_earlier_explorations_race_again(tmp_path):
    from helix9.warm import retro_race
    rows = []
    for g in range(1, 4):
        ts = [{"id": "T1", "kind": "seed", "exps": g, "best": 0.9, "opened": 0}]
        for k in range(8):                       # eight restarts, all still rising at their pause
            ts.append({"id": f"T{k + 2}", "kind": "restart", "exps": g, "best": 0.5 + 0.01 * k + 0.02 * g, "opened": 1})
        rows.append({"gen": g, "main": "T1", "tracks": ts})
    (tmp_path / "tracks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    status = retro_race(tmp_path, Config(running_cap=3), log=lambda m: None)
    last = jl(tmp_path / "tracks.jsonl")[-1]["tracks"]
    running = [t["id"] for t in last if (t.get("race") or {}).get("status") == "running"]
    assert len(running) == 2 and status.get("waiting", 0) == 6
    assert set(running) == {"T9", "T8"}                                 # the strongest at equal effort
    waiting = [t for t in last if t["id"] == "T2"][0]
    assert waiting["race"]["status"] == "waiting" and waiting["race"]["decisions"][-1]["cap"]
    # the queue: the strongest waiting goes first
    from helix9.race import take_waiting
    assert take_waiting(last, 4)["id"] == "T7" and take_waiting(last, 4)["id"] == "T6"


def test_a_waiting_exploration_is_taken_as_a_new_direction(tmp_path):
    r, prob = planted_run(tmp_path, gens=6)
    paused = [t for t in r.tracks.values() if t.get("race") and t["id"] != r.main_track()]
    assert paused
    queued = set()
    for t in r.tracks.values():                    # every race track waits its turn; nothing else is live
        if t.get("race") and t["id"] != r.main_track():
            t["race"]["status"] = "waiting"
            queued.add(t["id"])
        elif t["id"] != r.main_track():
            t["misses"] = 99
    slots = r.make_slots(7, 2)
    taken = [s["track"] for s in slots if s["kind"] == "track" and s.get("track") in queued]
    assert taken and r.tracks[taken[0]]["race"]["status"] == "running"
    assert any("races again" in e for e in r.map_events)


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


def test_a_continuation_from_a_published_folder_in_chunks_with_chained_packs(tmp_path):
    """GitHub as the only source: a v8 run published in chunks (helix9/publish.py) with its pack; a v9 run continued
    from it, published and packed in turn (its pack holding only what is new); a second continuation from that."""
    from helix8.run import Config as Config8, Run as Run8, fake_answer as fake8
    from helix9 import pack, publish
    from helix9.warm import prepare
    src = tmp_path / "v8"
    Run8(src, Config8(gens=4, budget=2.0), llm=FakeLLM(fake8), gens=4, **QUIET).go()
    gh = tmp_path / "github" / "v8"
    publish.publish(src, gh, full=True, say=lambda m: None)
    assert (gh / "programs" / "index.json").exists() and not (gh / "programs.jsonl").exists()
    assert pack.jl(gh / "programs.jsonl") == jl(src / "programs.jsonl")
    m1 = pack.build(gh, [str(src / "constructions")], log=lambda m: None)
    out = tmp_path / "v9"
    prepare(gh, out, pack=gh / "pack", budget=2.0, log=lambda m: None)
    assert jl(out / "programs.jsonl") == jl(src / "programs.jsonl")
    r9 = Run(out, llm=FakeLLM(fake_answer), gens=6, **QUIET)
    r9.go()
    gh9 = tmp_path / "github" / "v9"
    first = publish.publish(out, gh9, full=True, say=lambda m: None)
    again = publish.publish(out, gh9, full=True, say=lambda m: None)
    assert first["chunks_written"] > 0 and again["chunks_written"] == 0      # each push adds only what is new
    assert (gh9 / "mapview.json").exists() and json.loads((gh9 / "mapview.json").read_text())["programs"]
    m2 = pack.build(gh9, [str(out / "constructions")], base=gh / "pack", log=lambda m: None)
    assert m2["base"] and m2["in_base"] and not set(m2["packed"]) & set(m1["packed"])
    out2 = tmp_path / "v9b"
    prepare(gh9, out2, pack=gh9 / "pack", budget=2.0, log=lambda m: None)
    for pid in m1["packed"] + m2["packed"]:
        assert (out2 / "constructions" / f"{pid}.npy").exists()
    r10 = Run(out2, llm=FakeLLM(fake_answer), gens=7, **QUIET)
    assert r10.gen_done == 6
    r10.go()
    assert r10.gen_done == 7
    # a resume that trims lines already pushed rewrites only the chunks that changed
    joined = tmp_path / "joined"
    publish.join(gh9, joined)
    assert jl(joined / "programs.jsonl") == jl(out / "programs.jsonl")


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


# ---------------------------------------------------------------------------------------------- the job's helpers
def test_publishing_rewrites_only_chunks_whose_lines_changed(tmp_path, monkeypatch):
    from helix9 import publish
    from helix9.pack import jl as read
    monkeypatch.setattr(publish, "CHUNK_MB", 0.0005)          # tiny chunks: 20 lines each
    run, out = tmp_path / "run", tmp_path / "out"
    run.mkdir()
    rows = [{"id": f"p{i:04d}", "gen": i // 5, "x": "y" * 30} for i in range(95)]
    (run / "programs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows) + '{"id": "torn')
    s1 = publish.publish(run, out, say=lambda m: None)
    idx = json.loads((out / "programs" / "index.json").read_text())
    assert idx["lines_per_chunk"] == 20 and s1["chunks"] == 5 and idx["lines"] == 95      # the torn line left out
    assert read(out / "programs.jsonl") == rows
    first = (out / "programs" / "part-0001.jsonl.gz").read_bytes()
    # a resume trims the unfinished generation's lines (88-94), then the run appends new ones
    rows2 = rows[:88] + [{"id": f"q{i}", "gen": 18, "x": "z"} for i in range(30)]
    (run / "programs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows2))
    s2 = publish.publish(run, out, say=lambda m: None)
    assert read(out / "programs.jsonl") == rows2
    assert s2["chunks_written"] == 2 and s2["chunks"] == 6                # part 5 rewritten, part 6 new
    assert (out / "programs" / "part-0001.jsonl.gz").read_bytes() == first
    # trimmed below a chunk: the extra part is removed
    (run / "programs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[:30]))
    publish.publish(run, out, say=lambda m: None)
    assert read(out / "programs.jsonl") == rows[:30] and not (out / "programs" / "part-0003.jsonl.gz").exists()


def test_the_job_repairs_lines_cut_off_by_a_hard_stop(tmp_path):
    from helix9.job import repair_jsonl
    (tmp_path / "a.jsonl").write_text('{"x": 1}\n{"x": 2}\n{"x": 3')
    (tmp_path / "b.jsonl").write_text('{"x": 1}\n')
    (tmp_path / "c.jsonl").write_text('{"x": 1}\n{"x"\n\n')
    assert sorted(repair_jsonl(tmp_path)) == ["a.jsonl", "c.jsonl"]
    assert (tmp_path / "a.jsonl").read_text() == '{"x": 1}\n{"x": 2}\n'
    assert (tmp_path / "b.jsonl").read_text() == '{"x": 1}\n' and (tmp_path / "c.jsonl").read_text() == '{"x": 1}\n'


def test_the_vault_uploads_every_verified_construction_and_restores_them(tmp_path, monkeypatch):
    """helix9/vault.py's logic, against a stand-in for GitHub's releases (the real API is exercised on the VM)."""
    import shutil as _sh
    from helix9 import vault
    r = fake_run(tmp_path / "run", gens=2)

    class FakeGitHub:
        def __init__(self):
            self.rel, self.store, self.uploads = None, tmp_path / "release", 0
            self.store.mkdir()

        def release(self, tag, create=False, note=""):
            if self.rel is None and create:
                self.rel = {"tag": tag, "upload_url": "x{?name}", "assets": []}
            if self.rel is not None:
                self.rel["assets"] = [{"name": f.name, "id": f.name, "url": str(f)} for f in self.store.iterdir()]
            return self.rel

        def upload(self, rel, path, name):
            self.uploads += 1
            _sh.copy(path, self.store / name)

        def download(self, asset, dest):
            _sh.copy(asset["url"], dest)
    gh = FakeGitHub()
    monkeypatch.setattr(vault, "CHUNK_MB", 0.0001)               # one construction per file
    cons = tmp_path / "run" / "constructions"
    wrong = next(q.id for q in r.archive.valid() if (cons / f"{q.id}.npy").exists() and q.role != "seed")
    np.save(cons / f"{wrong}.npy", np.load(cons / f"{wrong}.npy") * 2 + 1)   # a wrong one: left out
    man = vault.upload(tmp_path / "run", [str(cons)], "t", log=lambda m: None, gh=gh)
    assert man["rejected"] >= 1 and wrong not in man["sha256"] and man["verified"] > 3
    assert len(man["files"]) == man["verified"]
    assert vault.upload(tmp_path / "run", [str(cons)], "t", log=lambda m: None, gh=gh) is None   # complete already
    n = vault.download("t", tmp_path / "restored", log=lambda m: None, gh=gh)
    assert n == man["verified"]
    for pid in man["sha256"]:
        assert np.array_equal(np.load(tmp_path / "restored" / f"{pid}.npy"), np.load(cons / f"{pid}.npy"))
