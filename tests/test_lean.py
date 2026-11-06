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


def test_run_resume_and_arms(tmp_path):
    for kw in ({}, {"planned": 0, "mutations": 4, "parents": "best", "inspiration": False, "notes": False},
               {"planned": 4, "mutations": 0}):
        d = tmp_path / str(len(kw))
        Run(d, Config(rounds=2, budget=2, **kw), llm=FakeLLM(fake_answer), log=lambda m: None).go()
        Run(d, Config(rounds=3, budget=2, **kw), llm=FakeLLM(fake_answer), log=lambda m: None).go()
        rows = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
        assert [r["round"] for r in rows] == [0, 1, 2, 3]
        progs = [json.loads(l) for l in (d / "programs.jsonl").read_text().splitlines()]
        assert len(progs) == 1 + 3 * 6 * 0 + 3 * (kw.get("planned", 3) + kw.get("mutations", 3))
        roles = {p["role"] for p in progs}
        assert ("planned" in roles) == (kw.get("planned", 3) > 0)
        assert (d / "notes.jsonl").exists() == kw.get("notes", True)


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
