"""Tests for Helix v10 (helix10/): the warm start in both modes (the field's decisions, findings and constructions),
a run end to end with a fake model, constructions kept by reference and removed when nothing needs them, the race's
copy rule, the field's programs, and the verification of the field's constructions.

    python -m pytest tests/test_helix10.py -q
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix10-slots-"))

from helix4.archive import Program                                  # noqa: E402
from helix4.llm import FakeLLM                                      # noqa: E402
from helix9.run import Config as Config9, Run as Run9, fake_answer as fake9   # noqa: E402
from helix10 import sota                                            # noqa: E402
from helix10.run import Archive10, Config, Run, fake_answer         # noqa: E402
from helix10.warm import prepare                                    # noqa: E402

QUIET = dict(log=lambda m: None)
ROOT = Path(__file__).resolve().parent.parent


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []


@pytest.fixture(scope="module")
def v9_source(tmp_path_factory):
    d = tmp_path_factory.mktemp("v9src")
    r = Run9(d, Config9(gens=4, budget=2.0), llm=FakeLLM(fake9), gens=4, **QUIET)
    r.go()
    return d


@pytest.fixture(scope="module")
def field_dir(tmp_path_factory):
    from helix10.field import get
    d = tmp_path_factory.mktemp("field")
    got = get(d, log=lambda m: None)
    assert len(got) == len(sota.IMPORTS)
    return d


# ---------------------------------------------------------------------------------------------- the warm start
def test_axes_mode_adds_the_fields_decisions_options_and_findings(tmp_path, v9_source):
    out = tmp_path / "axes"
    prepare(v9_source, out, mode="axes", budget=2.0, **QUIET)
    b = json.loads((out / "borrowed.json").read_text())
    assert len(b["axes"]) == len(sota.AXES)
    assert len(b["values"]) + len(b["matched"]) == sum(len(a["options"]) for a in sota.AXES)
    st = json.loads((out / "state.json").read_text())
    assert st["version"] == "v10" and st["config"]["mode"] == "axes" and st["config"]["max_n"] == 2_000_000
    field = [e for e in jl(out / "findings.jsonl") if e.get("kind") == "field"]
    assert len(field) == len(sota.FINDINGS) and all(e["source"] for e in field)
    assert not any(p["role"] == "import" for p in jl(out / "programs.jsonl"))      # concepts only


def test_warm_mode_imports_the_fields_constructions_verified(tmp_path, v9_source, field_dir):
    out = tmp_path / "warm"
    prepare(v9_source, out, mode="warm", budget=2.0, field=field_dir, run_programs=False, **QUIET)
    imps = [p for p in jl(out / "programs.jsonl") if p["role"] == "import"]
    assert len(imps) == len(sota.IMPORTS)
    best = max(imps, key=lambda p: p["score"])
    assert abs(best["score"] - sota.RECORD["score"]) < 1e-12 and best["n"] == sota.RECORD["n"]
    last = jl(out / "tracks.jsonl")[-1]
    assert last["main"] == best["plan"]["track"]
    kinds = {t["id"]: t["kind"] for t in last["tracks"]}
    assert sum(1 for p in imps if kinds[p["plan"]["track"]] == "import") == len(imps)
    r = Run(out, **QUIET)
    assert r.archive.best().id == best["id"] and r.problem.max_n == 2_000_000


def test_a_v10_run_explores_the_fields_options_and_shows_its_findings(tmp_path, v9_source):
    out = tmp_path / "run"
    prepare(v9_source, out, mode="axes", budget=2.0, **QUIET)
    seen = []

    def answer(role, system, user):
        seen.append((role, user))
        return fake_answer(role, system, user)
    r = Run(out, llm=FakeLLM(answer), gens=7, **QUIET)
    r.go()
    borrowed = set(json.loads((out / "borrowed.json").read_text())["values"])
    targets = [v for t in r.tracks.values() if t.get("target") for v in t["target"].values()]
    assert any(r.cb.resolve_value(v) in {r.cb.resolve_value(b) for b in borrowed} for v in targets)
    assert any("What the field knows" in u for _, u in seen)
    assert any("[from the field]" in u for _, u in seen)
    assert json.loads((out / "summary.json").read_text())["version"] == "v10"


# ---------------------------------------------------------------------------------------------- constructions
def test_an_unchanged_large_construction_is_kept_as_a_reference(tmp_path):
    a = Archive10(tmp_path)
    a.big_n = 1000
    big = np.random.default_rng(0).random(5000)
    p1 = Program(id=a.new_id(), gen=1, role="deep", parent=None, intent="", code="", valid=True, score=0.5, n=5000)
    a.add(p1, big)
    p2 = Program(id=a.new_id(), gen=2, role="deep", parent=p1.id, intent="", code="", valid=True, score=0.5, n=5000)
    a.add(p2, big * 3.0)                                        # the same function, scaled: R is scale-invariant
    assert (tmp_path / "constructions" / f"{p2.id}.ref").exists()
    assert not (tmp_path / "constructions" / f"{p2.id}.npy").exists()
    assert np.array_equal(a.construction(p2.id), big) and a.held(p2.id)
    assert jl(tmp_path / "refs.jsonl")[0] == {"id": p2.id, "of": p1.id, "gen": 2}
    p3 = Program(id=a.new_id(), gen=3, role="deep", parent=p2.id, intent="", code="", valid=True, score=0.6, n=5000)
    a.add(p3, big + 1.0)                                        # changed: stored
    assert (tmp_path / "constructions" / f"{p3.id}.npy").exists()
    a.truncate(1)
    assert not (tmp_path / "constructions" / f"{p2.id}.ref").exists() and jl(tmp_path / "refs.jsonl") == []


def test_large_constructions_nothing_needs_are_removed(tmp_path, v9_source):
    out = tmp_path / "gc"
    prepare(v9_source, out, mode="axes", budget=2.0, **QUIET)
    r = Run(out, llm=FakeLLM(fake_answer), **QUIET)
    r.cfg.big_n = 10                                            # every construction counts as large here
    gen = r.gen_done + 5
    before = {f.stem for f in (out / "constructions").glob("*.npy")}
    removed = set(r.gc_constructions(gen))
    after = {f.stem for f in (out / "constructions").glob("*.npy")}
    assert removed and after == before - removed
    keep = {p.id for p in r.archive.ranked()[: r.cfg.keep_top]} | {h.get("top") for h in r.hills.values()}
    keep |= {t.get("best_id") for t in r.tracks.values()} | {t.get("root") for t in r.tracks.values()}
    assert not (removed & keep)
    assert jl(out / "gc.jsonl")[-1]["removed"]


# ---------------------------------------------------------------------------------------------- the race
def test_a_copy_on_a_known_hill_stops_racing_only_after_its_first_rung(tmp_path, v9_source):
    out = tmp_path / "race"
    prepare(v9_source, out, mode="axes", budget=2.0, **QUIET)
    r = Run(out, llm=FakeLLM(fake_answer), **QUIET)
    main = r.main_track()
    t = next(t for t in r.tracks.values() if t["id"] != main)
    t["race"] = {"rung": 0, "budget": 3, "status": "running", "decisions": [], "bracket": 0}
    t["hill_status"], t["hill"], t["exps"] = "on", "H1", 1
    assert not r.is_copy(t)                                     # it climbs before it is judged
    r.race_pool(r.gen_done + 1)
    assert t["race"]["status"] == "running"
    t["exps"] = 3
    assert r.is_copy(t) and not r.live(t)
    r.race_pool(r.gen_done + 1)
    assert t["race"]["status"] == "paused"


# ---------------------------------------------------------------------------------------------- the field
def test_the_fields_programs_run_and_never_hand_back_worse(tmp_path):
    from helix4.problems.ac2 import score
    from helix47.evaluate import evaluate
    from helix47.run import ProblemView
    from helix4.problems import ac2
    from helix10.programs import NAMES, load
    start = np.load(ROOT / "results" / "v9warm" / "v9-s1" / "best.npy")[::8].copy()  # a small, tuned-ish start
    s0 = score(start / start.max())
    prob = ProblemView(ac2, 2_000_000)
    for name in NAMES:
        res = evaluate(prob, load(name), start, 8.0, 1500)
        assert res["valid"], (name, res["error"])
        assert res["score"] >= s0 - 1e-12, name
    res = evaluate(prob, load("resolution_transfer"), start, 8.0, 1500)
    assert res["n"] == 2_000_000                                 # repeated and padded to the cap


def test_the_fields_constructions_are_verified_on_reading(tmp_path, field_dir):
    from helix10.field import REPO_DIR, get
    src = tmp_path / "repo"
    shutil.copytree(REPO_DIR, src)
    raw = bytearray((src / "arena-3.npy.gz").read_bytes())
    raw[-20] ^= 0xFF                                            # one byte changed
    (src / "arena-3.npy.gz").write_bytes(bytes(raw))
    got = get(tmp_path / "out", src=src, log=lambda m: None)
    assert "arena-3" not in got and len(got) == len(sota.IMPORTS) - 1


def test_the_target_is_the_record_plus_the_arenas_gate():
    assert abs(sota.ARENA_TARGET - 0.963598110582029) < 1e-15
    assert all(len(c) <= 400 for c, _ in sota.FINDINGS)


def test_the_verifier_judges_two_million_steps_with_the_arenas_code(field_dir):
    from tools.verify_ac2 import verify
    r = verify(np.load(field_dir / "arena-2416.npy"), "record", max_n=2_000_000)
    assert r["valid"] and r["agree"] and r["N"] == 1_999_999
    assert abs(r["arena_code"] - sota.RECORD["score"]) < 1e-12
    assert not verify(np.load(field_dir / "arena-2416.npy"), "record")["valid"]      # the default limit still holds
