"""Tests for Helix v9's design-map components (helix9/): the codebook, the landscape model, the race, drop and flip
selection, the annotator's parsing and reliability, effort, and the continuation pack.

    python -m pytest tests/test_helix9_map.py -q
"""
import json
import math

import numpy as np
import pytest

from helix9 import annotate as A
from helix9.codebook import Codebook, consolidate, hamming, similar
from helix9.drops import choose_drop, choose_flip, shared_axes
from helix9.model import LandscapeModel
from helix9.race import Race, best_at, record_curve, rose_late


# ---------------------------------------------------------------------------------------------- the codebook
def test_ids_are_permanent_and_names_are_matched():
    cb = Codebook()
    a1 = cb.add_axis("How is the first solution built?", 1, "seed")
    a2 = cb.add_axis("How the objective's maximum is handled", 1, "scan")
    assert (a1, a2) == ("A1", "A2")
    assert cb.add_axis("how is the first solution built", 5, "annotator") == "A1"          # the same, said again
    v1 = cb.add_value(a1, "greedy insertion", 2)
    assert cb.add_value(a1, "Greedy insertion.", 3) == v1
    v2 = cb.add_value(a1, "savings construction", 3)
    assert v2 == "A1.v2" and cb.values(a1) == ["A1.v1", "A1.v2"]
    # merging keeps old ids resolvable, and never renumbers
    a3 = cb.add_axis("construction of the initial solution", 4)
    v3 = cb.add_value(a3, "regret insertion", 4)
    cb.merge_axis(a3, a1, 6)
    assert cb.resolve(a3) == "A1" and cb.resolve_value(v3).startswith("A1.v")
    assert cb.canonical({a3: v3}) == {"A1": cb.resolve_value(v3)}
    assert cb.add_axis("a brand new decision", 7) == "A4"                                  # A3 is never reused
    # round trip
    cb2 = Codebook(json.loads(json.dumps(cb.to_json())))
    assert cb2.canonical({a3: v3}) == cb.canonical({a3: v3}) and cb2.next_axis == cb.next_axis


def test_incompatible_pairs_and_distance():
    cb = Codebook()
    a, b = cb.add_axis("first decision"), cb.add_axis("second decision")
    va, vb = cb.add_value(a, "x"), cb.add_value(b, "y")
    vb2 = cb.add_value(b, "z")
    cb.mark_incompatible(va, vb)
    assert not cb.compatible({a: va, b: vb}) and cb.compatible({a: va, b: vb2})
    assert hamming({a: va, b: vb}, {a: va, b: vb2}) == 1
    assert hamming({a: va}, {b: vb}) == 0                    # unknowns don't count
    s = similar("Handling of zero entries / support", "treatment of the support / zeros")
    assert 0.3 < s < Codebook.MATCH            # related words, but merging such pairs is left to the model


def test_consolidation_merges_and_keeps_coordinates_valid():
    cb = Codebook()
    for q in ("objective form", "representation of f", "how the objective is optimised", "support handling"):
        cb.add_axis(q)
    v = cb.add_value("A3", "a smooth surrogate")
    done = consolidate(cb, {"merge": [["A1", "A3"], ["A9", "A2"], ["A2"]]})
    assert done == [("A3", "A1")]
    assert cb.canonical({"A3": v})["A1"].startswith("A1.v") and "A3" not in cb.active_axes()


# ---------------------------------------------------------------------------------------------- the model
def planted_rows(n=300, seed=1, frozen=False):
    rng = np.random.default_rng(seed)
    axes = {f"A{i}": [f"A{i}.v{j}" for j in range(1, 5)] for i in range(1, 7)}
    rows = []
    for _ in range(n):
        c = {a: str(rng.choice(v)) for a, v in axes.items()}
        if frozen:
            c["A6"] = "A6.v1"
        e = float(rng.integers(1, 60))
        y = 0.6 * (c["A1"] == "A1.v2") - 0.4 * (c["A2"] == "A2.v4") + 0.9 * (c["A3"] == "A3.v1" and c["A4"] == "A4.v3")
        y += 0.5 * (1 - math.exp(-e / 10)) + rng.normal(0, 0.05)
        rows.append({"coord": c, "y": y, "effort": e})
    return axes, rows


def test_the_model_recovers_planted_effects_an_interaction_and_the_noise():
    axes, rows = planted_rows()
    m = LandscapeModel(axes).fit(rows)
    assert m.ready and ("A3", "A4") in m.pairs
    imp = m.importance()
    top = [k for k in imp if k != "effort"][:3]
    assert set(map(str, top)) >= {"A1", "('A3', 'A4')"}
    assert imp.get("A5", 0) < 0.02 and imp.get("A6", 0) < 0.02                    # no effect: shrunk away
    e = m.effects("A1")
    assert e["A1.v2"][0] - e["A1.v1"][0] == pytest.approx(0.6, abs=0.08)
    assert 0.02 < m.noise_sd() < 0.09
    base = {a: v[0] for a, v in axes.items()}
    mu, sd = m.predict([base, {**base, "A3": "A3.v1", "A4": "A4.v3"}], effort=60)
    assert mu[1] - mu[0] == pytest.approx(0.9, abs=0.15)


def test_a_frozen_axis_keeps_its_uncertainty():
    """An axis nobody varied has no data on how much it matters: its untried options must stay uncertain."""
    axes, rows = planted_rows(frozen=True)
    m = LandscapeModel(axes).fit(rows)
    base = {a: v[0] for a, v in axes.items()}
    _, sd = m.predict([base, {**base, "A6": "A6.v2"}, {**base, "A5": "A5.v2"}])
    assert sd[1] > 5 * sd[2]                       # frozen A6: wide; varied-but-useless A5: narrow


def test_thompson_samples_vary_and_track_the_posterior():
    axes, rows = planted_rows()
    m = LandscapeModel(axes).fit(rows)
    rng = np.random.default_rng(3)
    base = {a: v[0] for a, v in axes.items()}
    c = [{**base, "A6": "A6.v3"}]
    draws = [m.sample(rng)(c)[0] for _ in range(200)]
    mu, sd = m.predict(c)
    assert abs(np.mean(draws) - mu[0]) < 3 * sd[0] / math.sqrt(200) + 1e-3
    assert np.std(draws) == pytest.approx(sd[0], rel=0.3)


def test_the_model_refuses_too_little_data():
    axes, rows = planted_rows(n=4)
    m = LandscapeModel(axes).fit(rows)
    assert not m.ready
    with pytest.raises(RuntimeError):
        m.predict([{}])


# ---------------------------------------------------------------------------------------------- the race
def track(tid, kind, curve, exps=None):
    t = {"id": tid, "kind": kind, "curve": curve, "exps": exps if exps is not None else (curve[-1][0] if curve else 0)}
    return t


def test_best_at_and_rising():
    c = [[1, 0.5], [2, 0.52], [3, None], [4, 0.6]]
    assert best_at(c, 2) == 0.52 and best_at(c, 3) == 0.52 and best_at(c, 4) == 0.6 and best_at(c, 0) is None
    assert rose_late(c, 4, 2) and not rose_late([[1, 0.5], [4, 0.5]], 4, 2)
    assert not rose_late([[1, 0.5], [3, 0.5000001]], 4, 2, floor=lambda r: 1e-3)      # noise is not a rise


def test_rising_rule_keeps_a_slow_climber_that_levels_would_kill():
    """The planted lesson: at equal effort a slow tall hill sits below fast traps; levels kill it, rising keeps it."""
    traps = [track(f"T{i}", "restart", [[1, 0.80], [2, 0.86], [4, 0.87], [8, 0.871]]) for i in range(5)]
    slow = track("S", "drop", [[1, 0.70], [2, 0.72], [3, 0.74], [4, 0.76]])
    level = Race(rule="level")
    level.start(slow, bracket=1)                         # judged at 4
    assert "paused" in level.decide(slow, traps + [slow])
    rising = Race(rule="rising")
    s2 = dict(slow, curve=list(slow["curve"]))
    rising.start(s2, bracket=1)
    assert "next rung" in rising.decide(s2, traps + [s2])
    flat = track("F", "drop", [[1, 0.70], [2, 0.70], [4, 0.70]])
    rising.start(flat, bracket=1)
    assert "paused" in rising.decide(flat, traps + [flat])


def test_the_cohort_is_the_same_kind_of_start_and_small_cohorts_get_the_benefit_of_the_doubt():
    r = Race(rule="level")
    flips = [track(f"F{i}", "flip", [[2, 0.94]]) for i in range(5)]
    d = track("D", "drop", [[1, 0.6], [2, 0.6]])
    r.start(d)
    assert "benefit of the doubt" in r.decide(d, flips + [d])       # flips are another group
    assert r.cohort(flips + [d], d, 2) == []


def test_race_lifecycle_wake_and_finish():
    r = Race(rule="rising", rungs=(2, 4))
    t = track("T", "drop", [[1, 0.5], [2, 0.6]])
    r.start(t)
    assert r.live(t) and r.decide(t, [t]) is not None and t["race"]["budget"] == 4
    t["exps"] = 4
    t["curve"] += [[4, 0.6]]
    assert "paused" in r.decide(t, [t]) and not r.live(t)
    assert r.wake(t) and r.live(t) and t["race"]["budget"] >= 6
    t["exps"] = t["race"]["budget"]
    t["curve"] += [[t["exps"], 0.7]]
    assert "finished" in r.decide(t, [t]) and not r.live(t)
    t2 = {"exps": 3, "best": 0.5}
    record_curve(t2)
    t2["best"] = 0.6
    record_curve(t2)
    assert t2["curve"] == [[3, 0.6]]


def test_brackets_rotate_first_rungs():
    r = Race(brackets=(0, 2))
    a, b, c = {"id": "a"}, {"id": "b"}, {"id": "c"}
    for t in (a, b, c):
        r.start(t)
    assert [a["race"]["budget"], b["race"]["budget"], c["race"]["budget"]] == [2, 8, 2]


# ---------------------------------------------------------------------------------------------- drops and flips
def levels():
    return {f"A{i}": [f"A{i}.v{j}" for j in range(1, 5)] + [f"A{i}.new"] for i in range(1, 7)}


def test_drops_change_2_to_4_axes_far_from_known_hills_and_skip_tabu():
    rng = np.random.default_rng(1)
    base = {f"A{i}": f"A{i}.v1" for i in range(1, 7)}
    hill = {**base, "A1": "A1.v2"}
    axes = list(base)
    seen = set()
    for _ in range(40):
        coord, change, _ = choose_drop(None, base, axes, levels(), rng, avoid=[base, hill], min_dist=2, tabu=seen)
        assert 2 <= len(change) <= 4 and all(coord[a] == v for a, v in change.items())
        assert hamming(coord, base) >= 2 and hamming(coord, hill) >= 2
        key = tuple(sorted(change.items()))
        assert key not in seen
        seen.add(key)


def test_a_sampled_model_steers_drops_and_flips():
    rng = np.random.default_rng(2)
    base = {f"A{i}": f"A{i}.v1" for i in range(1, 7)}

    def sample(coords):                        # a "model" that likes A3.v4 and A5.v2 together
        return np.array([1.0 * (c.get("A3") == "A3.v4") + 1.0 * (c.get("A5") == "A5.v2") for c in coords])
    coord, change, rating = choose_drop(sample, base, list(base), levels(), rng, kmin=2, kmax=2, n=2000)
    assert change == {"A3": "A3.v4", "A5": "A5.v2"} and rating == 2.0
    coord, change, _ = choose_flip(sample, base, list(base), levels(), rng, tried={(("A3", "A3.v4"),)})
    assert change == {"A5": "A5.v2"}                                   # the tried flip is skipped
    assert shared_axes([base, {**base, "A1": "A1.v2"}], list(base)) == {a: v for a, v in base.items() if a != "A1"}


def test_incompatible_values_are_never_dropped_on():
    cb = Codebook()
    for i in range(1, 4):
        a = cb.add_axis(f"decision number {i} of the design")
        for j in range(1, 4):
            cb.add_value(a, f"option {j} of {a}")
    cb.mark_incompatible("A1.v2", "A2.v2")
    rng = np.random.default_rng(0)
    base = {"A1": "A1.v1", "A2": "A2.v1", "A3": "A3.v1"}
    lv = {a: cb.values(a) for a in base}
    for _ in range(60):
        pick = choose_drop(None, base, list(base), lv, rng, compatible=cb.compatible, kmin=2, kmax=3, include_new=False)
        if pick:
            assert cb.compatible(pick[0])


# ---------------------------------------------------------------------------------------------- the annotator
def small_codebook():
    cb = Codebook()
    a = cb.add_axis("How is the first solution built?")
    cb.add_value(a, "greedy")
    cb.add_value(a, "random")
    b = cb.add_axis("Which moves change a solution?")
    cb.add_value(b, "swap")
    return cb


def test_diff_readings_inherit_and_grow_the_codebook():
    cb = small_codebook()
    base = {"A1": "A1.v1", "A2": "A2.v1"}
    reply = json.dumps({"changes": [{"axis": "A1", "value": "A1.v2"}, {"axis": "A2", "new_value": "2-opt moves"},
                                    {"new_axis": "How is time split?", "base_value": "all in one phase",
                                     "value": "two phases"}]})
    coord, info = A.apply_diff_reply(cb, "```json\n" + reply + "\n```", base, 5)
    assert coord["A1"] == "A1.v2" and cb.value_name(coord["A2"]) == "2-opt moves"
    assert info["new_axes"] == ["A3"] and cb.value_name(coord["A3"]) == "two phases"
    same, info2 = A.apply_diff_reply(cb, '{"changes": []}', base, 5)
    assert same == base and info2["readable"] and not info2["changed"]
    junk, info3 = A.apply_diff_reply(cb, "I think it changed things", base, 5)
    assert junk == base and not info3["readable"]                      # unreadable: the base's coordinate stands
    bad, _ = A.apply_diff_reply(cb, json.dumps({"changes": [{"axis": "A1", "value": "A2.v1"}, {"axis": "A9", "value": "x"}]}), base, 5)
    assert bad == base                                                  # another axis's id, an unknown axis: ignored


def test_full_readings_handle_new_values_na_and_new_axes():
    cb = small_codebook()
    text = json.dumps({"design": {"A1": "A1.v1", "A2": "n/a", "A7": "A7.v1"},
                       "new_axes": [{"axis": "How is the problem decomposed?", "value": "by clusters"}]})
    coord, info = A.apply_full_reply(cb, text, cb.active_axes(), 3)
    assert coord["A1"] == "A1.v1" and "A2" not in coord and info["new_axes"] == ["A3"]
    coord2, _ = A.apply_full_reply(cb, json.dumps({"design": {"A1": {"new_value": "savings"}}}), cb.active_axes(), 3)
    assert cb.value_name(coord2["A1"]) == "savings"


def test_reliability_measures():
    k, agree, n = A.kappa([("a", "a"), ("b", "b"), ("a", "b"), ("b", "b")])
    assert (agree, n) == (3, 4) and 0 < k < 1
    assert A.kappa([("a", "a")] * 5)[0] == 1.0
    rows = [{"first": {"A1": "A1.v1"}, "second": {"A1": "A1.v1"}}, {"first": {"A1": "A1.v1"}, "second": {"A1": "A1.v2"}}]
    cb = small_codebook()
    A.update_agreement(cb, rows)
    assert cb.axes["A1"]["agreement"]["rate"] == 0.5
    for _ in range(3):
        rows += rows
    A.update_agreement(cb, rows)
    assert "A1" not in cb.reliable_axes(0.6) and "A1" in cb.reliable_axes(0.4)


def test_effort_rules():
    assert A.effort_of({"A1": "x"}, 10, {"A1": "x"}) == 11
    assert A.effort_of({"A1": "x", "A2": "y"}, 10, {"A1": "z", "A2": "y"}) == 7
    assert A.effort_of({"A1": "x", "A2": "y"}, 100, {"A1": "z", "A2": "w"}) == 3
    assert A.effort_of({}, None, {"A1": "x"}) == 1.0


def test_the_fake_annotator_reads_designs():
    # decisions the codebook names come back by their ids; the others as new decisions
    cb = "A3: D1\n   A3.v1: option 1\n"
    full = json.loads(A.fake_reply(cb, '## The program (p0003)\n```python\nDESIGN = {"D1": "option 2", "D2": "option 1"}\n```'))
    assert full["design"] == {"A3": "option 2"} and full["new_axes"] == [{"axis": "D2", "value": "option 1"}]
    diff = json.loads(A.fake_reply(cb, '```diff\n-DESIGN = {"D1": "option 1", "D2": "option 1"}\n'
                                       '+DESIGN = {"D1": "option 2", "D2": "option 3"}\n```'))
    assert diff["changes"] == [{"axis": "A3", "value": "option 2"},
                               {"new_axis": "D2", "base_value": "option 1", "value": "option 3"}]


# ---------------------------------------------------------------------------------------------- the continuation pack
def make_run(tmp, n=12, seed=0):
    from helix4.problems import ac2
    rng = np.random.default_rng(seed)
    run = tmp / "run"
    cons = tmp / "local" / "constructions"
    run.mkdir(parents=True)
    cons.mkdir(parents=True)
    progs = []
    for i in range(1, n + 1):
        h = rng.random(int(rng.integers(20, 200)))
        h, _ = ac2.check(h)
        pid = f"p{i:04d}"
        progs.append({"id": pid, "gen": i, "role": "deep" if i > 1 else "seed", "parent": f"p{i - 1:04d}" if i > 1 else None,
                      "intent": "", "code": "", "plan": {"track": "T1"}, "valid": True, "score": float(ac2.score(h)),
                      "n": len(h), "feedback": []})
        np.save(cons / f"{pid}.npy", h)
    (run / "programs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in progs))
    (run / "state.json").write_text(json.dumps({"config": {"problem": "ac2"}, "gen_done": n}))
    (run / "tracks.jsonl").write_text(json.dumps({"gen": n, "tracks": [{"id": "T1", "best_id": progs[-1]["id"], "root": "p0001"}]}) + "\n")
    return run, cons, progs


def test_the_pack_verifies_rejects_and_restores_losslessly(tmp_path):
    from helix9 import pack
    run, cons, progs = make_run(tmp_path)
    np.save(cons / "p0005.npy", np.load(cons / "p0005.npy") * 1.0 + 0.01)        # a corrupted file
    (cons / "p0006.npy").unlink()                                                   # a lost one
    man = pack.build(run, [str(cons)], budget_mb=50, log=lambda m: None)
    assert man["verified"] == 10 and "p0005" in man["rejected"] and man["missing"] == 1
    assert "p0005" not in man["packed"] and "p0006" not in man["packed"]
    out = tmp_path / "new"
    out.mkdir()
    (out / "programs.jsonl").write_text((run / "programs.jsonl").read_text())
    n, s = pack.restore(run / "pack", out, log=lambda m: None)
    assert n == len(man["packed"]) and s == 10
    for pid in man["packed"]:
        assert np.array_equal(np.load(out / "constructions" / f"{pid}.npy"), np.load(cons / f"{pid}.npy"))


def test_the_pack_keeps_to_its_budget_in_priority_order(tmp_path):
    from helix9 import pack
    run, cons, progs = make_run(tmp_path, n=30)
    man = pack.build(run, [str(cons)], budget_mb=0.004, log=lambda m: None)
    assert 0 < len(man["packed"]) < 30 and man["bytes"] <= 4000
    best = max(progs, key=lambda p: p["score"])["id"]
    assert man["packed"][0] == best and man["why"][best] == "the record"


def test_a_tampered_pack_is_refused(tmp_path):
    from helix9 import pack
    run, cons, progs = make_run(tmp_path)
    man = pack.build(run, [str(cons)], log=lambda m: None)
    man["sha256"][man["packed"][0]] = "0" * 64
    (run / "pack" / "manifest.json").write_text(json.dumps(man))
    out = tmp_path / "new"
    out.mkdir()
    with pytest.raises(SystemExit):
        pack.restore(run / "pack", out, log=lambda m: None)


# ---------------------------------------------------------------------------------------------- keeping the map tidy
def test_tidying_groups_reworded_options_and_old_readings_still_resolve():
    import json as _json
    from helix9 import upkeep
    from helix9.codebook import Codebook
    cb = Codebook()
    a = cb.add_axis("How is the step size chosen?", 1, "test")
    vs = [cb.add_value(a, n, 1, "test") for n in ("a fixed learning rate of 0.01", "constant step, never changed",
                                                   "backtracking line search", "Armijo line search with halving",
                                                   "a decaying schedule")]
    coords = {"p1": {a: vs[0]}, "p2": {a: vs[1]}, "p3": {a: vs[1]}, "p4": {a: vs[3]}}

    def call(role, system, user, t, m):
        assert "Group them into at most 3" in user and vs[4] in user
        return _json.dumps({"options": [{"name": "Fixed step", "ids": [vs[0], vs[1]]},
                                        {"name": "Line search", "ids": [vs[2], vs[3]]},
                                        {"name": "Decaying schedule", "ids": [vs[4]]}]})
    merged = upkeep.tidy(cb, call, upkeep.uses_of(cb, coords), max_values=3, log=lambda m: None)
    assert merged == 2 and len(cb.values(a)) == 3
    assert cb.resolve_value(vs[0]) == vs[1] and cb.value_name(vs[1]) == "Fixed step"     # the most used survives
    assert cb.resolve_value(vs[2]) == vs[3] and cb.value_name(vs[3]) == "Line search"
    assert cb.canonical(coords["p1"]) == {a: vs[1]}                                      # old readings resolve
    assert "constant step, never changed" in cb.axes[a]["values"][vs[1]]["aliases"]


def test_pruning_drops_decisions_hardly_any_program_makes():
    from helix9 import upkeep
    from helix9.codebook import Codebook
    cb = Codebook()
    big = cb.add_axis("How is a solution represented?", 0, "replay")
    rare = cb.add_axis("Is the answer mirrored at the end?", 5, "annotator")
    young = cb.add_axis("Which random seed policy is used?", 19, "annotator")
    v1, v2 = cb.add_value(big, "grid", 0), cb.add_value(rare, "yes", 5)
    coords = {f"p{i}": {big: v1} for i in range(10)}
    coords["p0"][rare] = v2
    dropped = upkeep.prune(cb, coords, min_support=3, gen=20, min_age=10, log=lambda m: None)
    assert dropped == [rare] and young in cb.active_axes() and big in cb.active_axes()


def test_importance_weights_decisions_by_how_many_programs_make_them():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(60):
        c = {"A1": "A1.v1" if i % 2 else "A1.v2"}
        if i < 2:
            c["A2"] = "A2.v1" if i == 0 else "A2.v2"          # read on two programs only, far apart
        y = (0.02 if c["A1"] == "A1.v1" else 0.0) + (0.03 if c.get("A2") == "A2.v1" else 0.0) + rng.normal(0, 0.002)
        rows.append({"coord": c, "y": y, "effort": 5.0})
    m = LandscapeModel({"A1": ["A1.v1", "A1.v2"], "A2": ["A2.v1", "A2.v2"]}, effort=False).fit(rows, min_rows=5)
    imp = m.importance()
    assert imp["A1"] > 5 * imp["A2"]          # a larger effect on two programs explains less of the whole
