"""Tests for Helix v4: the AC2 verifier, the sandbox, the archive, the memories, and fake-model runs end to end.

    python -m pytest tests/test_helix4.py -q
"""
import json
import os
import random
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("HELIX4_SLOTS_DIR", tempfile.mkdtemp(prefix="helix4-slots-"))

from helix4 import prompts as P                       # noqa: E402
from helix4.archive import Archive, Program          # noqa: E402
from helix4.evaluate import evaluate                 # noqa: E402
from helix4.llm import FakeLLM                       # noqa: E402
from helix4.problems import ac2                      # noqa: E402
from helix4.run import Config, Run, fake_answer      # noqa: E402
from helix4.sandbox import run_program               # noqa: E402


# ---------------------------------------------------------------------------------------------- the verifier
def brute_ratio(h, m=64):
    """R for the step function with heights h, by sampling f finely and integrating numerically."""
    f = np.repeat(np.asarray(h, float), m)
    dx = 1.0 / len(f)
    ff = np.convolve(f, f) * dx
    return float(np.sum(ff ** 2) * dx / (np.sum(ff) * dx * ff.max()))


def test_constant_is_two_thirds():
    assert abs(ac2.score(np.ones(50)) - 2 / 3) < 1e-12
    assert abs(ac2.score(np.ones(1)) - 2 / 3) < 1e-12


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_exact_formula_matches_brute_force(seed):
    h = np.random.default_rng(seed).random(12)
    assert abs(ac2.score(h) - brute_ratio(h)) < 2e-3


def test_fft_path_matches_direct():
    h = np.random.default_rng(3).random(5000)
    assert np.allclose(ac2.autoconv(h), np.convolve(h, h), rtol=1e-9, atol=1e-6)


def test_scale_invariant_and_bounded():
    h = np.random.default_rng(4).random(300)
    assert abs(ac2.score(h) - ac2.score(7.5 * h)) < 1e-12
    for s in range(5):
        assert 0 < ac2.score(np.random.default_rng(s).random(200) ** 3) <= 1


def test_check_rejects_bad_results():
    assert ac2.check(None)[0] is None
    assert ac2.check([])[0] is None
    assert ac2.check([1.0, -0.1])[0] is None
    assert ac2.check([1.0, np.nan])[0] is None
    assert ac2.check([0.0, 0.0])[0] is None
    assert ac2.check(np.ones(ac2.MAX_N + 1))[0] is None
    assert ac2.check(np.ones(3))[0] is not None


def test_feedback_is_scale_free():
    h = np.random.default_rng(5).random(100)
    s, lines = ac2.feedback(h, h * 3, {"cpu": 1, "wall": 1}, 20)
    assert abs(s - ac2.score(h)) < 1e-12
    assert "unchanged" in lines[0]
    assert not any("record" in l.lower() or "0.96" in l for l in lines)   # never a hint about the frontier


# ---------------------------------------------------------------------------------------------- the sandbox
def test_sandbox_returns_result_and_uses_start():
    arr, info = run_program("import numpy as np\ndef construct(b, start):\n    return start * 2\n", 5, start=np.ones(4))
    assert info["ok"] and np.allclose(arr, 2)


def test_sandbox_catches_exceptions():
    arr, info = run_program("def construct(b, start):\n    raise ValueError('boom')\n", 5)
    assert arr is None and "boom" in info["error"]


def test_sandbox_kills_runaway_programs():
    arr, info = run_program("def construct(b, start):\n    while True:\n        pass\n", 1)
    assert arr is None and not info.get("ok")


def test_evaluate_reports_delta_and_failures():
    prob = ac2
    good = "import numpy as np\ndef construct(b, start):\n    h = np.ones(30); h[0] = 0.5\n    return h\n"
    r = evaluate(prob, good, np.ones(30), 5)
    assert r["valid"] and r["delta"] is not None and abs(r["start_score"] - 2 / 3) < 1e-12
    bad = "import numpy as np\ndef construct(b, start):\n    return -np.ones(3)\n"
    r = evaluate(prob, bad, None, 5)
    assert not r["valid"] and "negative" in r["error"]


# ---------------------------------------------------------------------------------------------- the archive
def prog(i, gen, parent, score, code=None):
    return Program(id=f"p{i:04d}", gen=gen, role="deep", parent=parent, intent=f"i{i}", code=code or f"# {i}\n",
                   valid=score is not None, score=score, delta=0.01 if parent else None)


def test_archive_reload_truncate_duplicates(tmp_path):
    a = Archive(tmp_path)
    a.add(prog(1, 0, None, 0.6), np.ones(3))
    a.add(prog(2, 1, "p0001", 0.7, code="same\n"), np.ones(3))
    a.add(prog(3, 2, "p0002", 0.8), np.ones(3))
    assert a.duplicate("same\n", "p0001") == "p0002" and a.duplicate("same\n", "p0003") is None
    b = Archive(tmp_path)
    assert b.best().id == "p0003" and b.lineage_line("p0003").startswith("p0001")
    assert b.truncate(1) == 1 and "p0003" not in Archive(tmp_path).programs
    assert not (tmp_path / "constructions" / "p0003.npy").exists()


def test_parent_sampling_favours_strong_but_spreads(tmp_path):
    a = Archive(tmp_path)
    for i in range(1, 9):
        a.add(prog(i, 1, None, 0.5 + i / 100))
    picks = [a.sample_parent(random.Random(s)).id for s in range(400)]
    assert picks.count("p0008") > picks.count("p0001") and len(set(picks)) >= 5


# ---------------------------------------------------------------------------------------------- parsing
def test_parsers():
    assert P.extract_json('x ```json\n{"a": 1}\n``` y') == {"a": 1}
    assert P.extract_json('noise {"a": [1, 2]} more') == {"a": [1, 2]}
    code = "```python\nimport numpy as np\ndef construct(b, s):\n    return np.ones(2)\n```\nSUMMARY: did a thing"
    assert "def construct" in P.extract_code(code) and P.extract_summary(code) == "did a thing"
    assert P.extract_code("```python\nprint(1)\n```") is None


# ---------------------------------------------------------------------------------------------- end to end
def fake_run(tmp_path, condition, gens=2):
    return Run(tmp_path / condition, Config(condition=condition, gens=gens, budget=2), llm=FakeLLM(fake_answer),
               log=lambda m: None)


@pytest.mark.parametrize("condition", ["control", "journal", "atlas"])
def test_fake_run_end_to_end(tmp_path, condition):
    s = fake_run(tmp_path, condition).go()
    d = tmp_path / condition
    hist = [json.loads(l) for l in (d / "history.jsonl").read_text().splitlines()]
    assert [h["gen"] for h in hist] == [0, 1, 2]
    assert s["best"] > 2 / 3 and s["programs"] == 1 + 2 * 6
    assert (d / "best.py").exists() and (d / "summary.json").exists()
    roles = {json.loads(l)["role"] for l in (d / "trace.jsonl").read_text().splitlines()}
    assert {"researcher", "coder", "mutator"} <= roles
    if condition == "atlas":
        assert "distiller" in roles and "navigator" in roles and s["memory"]["findings"] >= 1
    if condition == "journal":
        assert (d / "journal.jsonl").exists()


def test_resume_drops_the_unfinished_generation(tmp_path):
    fake_run(tmp_path, "atlas", gens=2).go()
    d = tmp_path / "atlas"
    a = Archive(d)
    a.add(prog(99, 3, "p0001", 0.9))                            # half of a generation 3 that never finished
    with (d / "findings.jsonl").open("a") as f:
        f.write(json.dumps({"op": "new", "id": "F99", "gen": 3, "kind": "works", "claim": "x", "evidence": ["p0099"], "links": []}) + "\n")
    r = Run(d, llm=FakeLLM(fake_answer), gens=3, log=lambda m: None)
    assert "p0099" not in r.archive.programs and "F99" not in r.memory.findings
    s = r.go()
    assert s["gens"] == 3 and len(s["best_by_gen"]) == 4


def test_journal_compacts(tmp_path):
    r = fake_run(tmp_path, "journal", gens=4)
    r.cfg.journal_chars, r.cfg.journal_keep = 1500, 1
    r.go()
    st = r.memory.stats()
    assert st["compactions"] >= 1 and st["summary_upto_gen"] >= 1


def test_atlas_status_is_computed_from_results(tmp_path):
    r = fake_run(tmp_path, "atlas", gens=1)
    r.go()
    m, a = r.memory, r.archive
    gain = next(p for p in a.programs.values() if p.valid and (p.delta or 0) > 0)
    f = {"kind": "works", "evidence": [gain.id], "links": [], "claim": "c"}
    assert m.status(f).startswith("supported")
    f["kind"] = "fails"
    assert m.status(f).startswith("refuted")
    # the distiller can't cite programs that don't exist or link to findings that don't exist
    before = len(m.findings)
    r.llm = FakeLLM(lambda *a: json.dumps({"new": [{"kind": "works", "claim": "ghost", "evidence": ["p9999"]},
                                                     {"kind": "works", "claim": "real", "evidence": [gain.id],
                                                      "links": [{"to": "F777", "type": "refines"}]}]}))
    info = m.update(2, None, [])
    assert info["findings_added"] == 1 and len(m.findings) == before + 1
    assert all(not f["links"] for f in m.findings.values() if f["claim"] == "real")
