"""Stage 0 of the proof of concept: the offline replay on an earlier run's archive (docs/V9_DESIGN.md; section 7 of
docs/SEARCH_SPACE_MODEL.md). No programs are run: only model calls, a few hundred.

    python -m helix9.replay --run results/v8warm/v8-s1 --out results/v9warm/replay            # real model
    python -m helix9.replay --run results/v8warm/v8-s1 --out /tmp/replay --fake --sample 30   # a test

It answers, before anything is built on it, whether the design map is real:
1. **A codebook from the run's own scans.** v8's Cartographer named the shared decisions 82 times in 460 wordings.
   They are matched, a batch at a time, against the codebook as it grows (one call per batch), into axes with values
   (each scan's shared option and its alternatives).
2. **Coordinates.** A selection of programs (every hill's top, every track's best, the record's lineage, and a random
   sample) is read in full by the annotator; a quarter of them a second time, independently.
3. **Reliability:** agreement and Cohen's kappa per axis between the two readings. Pass: raw agreement of at least
   0.8 on most axes.
4. **Does the model know anything?** It is fitted on the programs up to a generation and asked about the later ones:
   does its predicted change from base to child (model(child) - model(base)) rank the actual changes better than
   chance? Pass: a positive rank correlation, unlikely to be chance.
5. **What helped and what hurt:** the model's importance of each decision and the effects of its options, on the
   whole archive.

Its outputs seed v9's warm start (helix9/warm.py --replay): codebook.json, coords.jsonl, annotations.jsonl; and
REPLAY.md with the verdicts.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from helix4 import prompts as P4
from helix4.archive import Program
from helix9 import annotate as A
from helix9 import prompts as P
from helix9.codebook import Codebook, consolidate
from helix9.model import LandscapeModel
from helix9.pack import jl


# ---------------------------------------------------------------------------------------------- 1. the codebook
def scan_decisions(run):
    """Every distinct shared decision the run's Cartographer named (hills.jsonl), oldest first."""
    seen, out = set(), []
    for row in jl(Path(run) / "hills.jsonl"):
        for d in row.get("shared") or []:
            key = " ".join(str(d.get("decision", "")).lower().split())
            if key and key not in seen:
                seen.add(key)
                out.append({"decision": d.get("decision"), "everyone": d.get("everyone"),
                            "alternatives": d.get("alternatives") or [], "gen": d.get("gen") or row.get("gen")})
    return out


def build_codebook(call, decisions, batch=30, max_axes=14, log=print):
    cb = Codebook()
    for i in range(0, len(decisions), batch):
        part = decisions[i: i + batch]
        items = "\n".join(f"{j}. {d['decision']} (all use: {d.get('everyone')}; alternatives: "
                          f"{'; '.join(d.get('alternatives') or []) or '-'})" for j, d in enumerate(part, 1))
        matches = {}
        if cb.active_axes():
            text = call("cartographer", P.MATCH_SYSTEM, P.MATCH_ASK.format(axes=cb.text(max_values=4), items=items),
                        0.2, 2500)
            js = P4.extract_json(text) or {}
            for m in js.get("matches") or []:
                if isinstance(m, dict):
                    try:
                        matches[int(m.get("item"))] = m
                    except (TypeError, ValueError):
                        pass
        for j, d in enumerate(part, 1):
            m = matches.get(j) or {}
            aid = cb.resolve(str(m.get("axis") or "").strip())
            if aid not in cb.axes:
                aid = cb.add_axis(m.get("question") or d["decision"], d.get("gen"), "replay")
            if d.get("everyone"):
                cb.add_value(aid, d["everyone"], d.get("gen"), "replay")
            for alt in d.get("alternatives") or []:
                cb.add_value(aid, alt, d.get("gen"), "replay")
        log(f"   codebook: {len(cb.active_axes())} decisions after {min(i + batch, len(decisions))} of {len(decisions)} names")
    for _ in range(3):                       # merge duplicates until stable (at most 3 calls)
        if len(cb.active_axes()) <= max_axes:
            break
        text = call("cartographer", P.MATCH_SYSTEM, P.CONSOLIDATE_ASK.format(axes=cb.text(max_values=3), k=max_axes),
                    0.2, 2500)
        merged = consolidate(cb, P4.extract_json(text) or {})
        log(f"   consolidated: {len(merged)} merges, {len(cb.active_axes())} decisions")
        if not merged:
            break
    return cb


# ---------------------------------------------------------------------------------------------- 2. coordinates
def select(run, progs, sample=150, seed=1):
    run = Path(run)
    valid = {k: p for k, p in progs.items() if p.valid and p.score is not None}
    pick = []

    def add(pid):
        if pid in valid and pid not in pick:
            pick.append(pid)
    for h in (jl(run / "hills.jsonl")[-1:] or [{}])[0].get("hills", []):
        add(h.get("top"))
    for t in (jl(run / "tracks.jsonl")[-1:] or [{}])[0].get("tracks", []):
        add(t.get("best_id"))
    best = max(valid.values(), key=lambda p: p.score) if valid else None
    q = best
    for _ in range(40):
        if q is None:
            break
        add(q.id)
        q = progs.get(q.parent) if q.parent else None
    rest = sorted(set(valid) - set(pick))
    random.Random(seed).shuffle(rest)
    for pid in rest[:sample]:
        add(pid)
    return pick


def annotate_all(call, cb, progs, pids, double=0.25, seed=1, workers=8, log=print):
    axes = cb.active_axes()
    rng = random.Random(seed)
    twice = {pid for pid in pids if rng.random() < double}
    jobs = [(pid, "first") for pid in pids] + [(pid, "second") for pid in sorted(twice)]
    t0 = time.time()

    def one(job):
        pid, kind = job
        p = progs[pid]
        return call("annotator", A.SYSTEM, A.full_prompt(cb, axes, p), 0.2 if kind == "first" else 0.7, 1500)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        texts = list(ex.map(one, jobs))
    coords, seconds, unread = {}, {}, 0
    for (pid, kind), text in zip(jobs, texts):
        c, info = A.apply_full_reply(cb, text, axes, None, "replay")
        if not info["readable"]:
            unread += 1
        (coords if kind == "first" else seconds)[pid] = c
    rows = [{"id": pid, "first": coords.get(pid), "second": seconds[pid]} for pid in sorted(seconds)]
    log(f"   annotated {len(coords)} programs ({len(seconds)} twice, {unread} replies unreadable) in "
        f"{time.time() - t0:.0f} s")
    return coords, rows


def lineage_effort(progs, pid, cap=500):
    """Experiments spent on a design: the program's ancestors back to the last fresh start (Code Zero, a restart or
    a bold experiment), as a proxy when ancestors have no coordinates."""
    n, q = 0, progs.get(pid)
    while q is not None and n < cap:
        n += 1
        kind = (q.plan or {}).get("kind")
        if q.role == "seed" or kind in ("restart", "bold") and q.parent and progs.get(q.parent) and \
                progs[q.parent].role == "seed":
            break
        q = progs.get(q.parent) if q.parent else None
    return float(n)


# ---------------------------------------------------------------------------------------------- 4. the model's test
def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return None
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def permutation_p(a, b, rho, n=2000, seed=1):
    if rho is None:
        return None
    rng = np.random.default_rng(seed)
    b = np.asarray(b, float)
    hits = 0
    for _ in range(n):
        r = spearman(a, rng.permutation(b))
        if r is not None and r >= rho:
            hits += 1
    return (hits + 1) / (n + 1)


def model_test(cb, coords, progs, effort, split):
    axes = cb.active_axes()

    def row(pid):
        p = progs[pid]
        return {"coord": {a: v for a, v in coords[pid].items() if a in axes}, "y": p.score, "effort": effort[pid]}
    train = [pid for pid in coords if progs[pid].gen <= split]
    test = [pid for pid in coords if progs[pid].gen > split and progs[pid].parent in coords]
    m = LandscapeModel({a: cb.values(a) for a in axes}).fit([row(pid) for pid in train], min_rows=8)
    if not m.ready or len(test) < 5:
        return {"train": len(train), "test": len(test), "rho": None, "p": None}
    pred_c = m.features([coords[pid] for pid in test], [effort[pid] for pid in test]) @ m.m
    par = [progs[pid].parent for pid in test]
    pred_p = m.features([coords[q] for q in par], [effort[q] for q in par]) @ m.m
    pred_delta = (pred_c - pred_p) * m.y_sd
    actual = [progs[pid].score - progs[q].score for pid, q in zip(test, par)]
    rho = spearman(pred_delta, actual)
    moved = [i for i, (pid, q) in enumerate(zip(test, par)) if coords[pid] != coords[q]]
    rho_moved = spearman(pred_delta[moved], np.asarray(actual)[moved]) if len(moved) >= 5 else None
    return {"train": len(train), "test": len(test), "moved": len(moved), "rho": rho,
            "p": permutation_p(pred_delta, actual, rho), "rho_moved": rho_moved,
            "p_moved": permutation_p(pred_delta[moved], np.asarray(actual)[moved], rho_moved) if moved else None}


# ---------------------------------------------------------------------------------------------- the whole replay
def replay(run, out, call, sample=150, double=0.25, seed=1, log=print):
    run, out = Path(run), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    progs = {}
    for r in jl(run / "programs.jsonl"):
        try:
            progs[r["id"]] = Program(**r)
        except TypeError:
            continue
    log(f"== replay of {run} ({len(progs)} programs)")
    decisions = scan_decisions(run)
    log(f"1. the codebook, from {len(decisions)} distinct names the Cartographer gave")
    cb = build_codebook(call, decisions, log=log)
    pids = select(run, progs, sample, seed)
    log(f"2. coordinates: reading {len(pids)} programs")
    coords, rows = annotate_all(call, cb, progs, pids, double, seed, log=log)
    A.update_agreement(cb, rows)
    ag = A.agreement(rows, cb.active_axes())
    effort = {pid: lineage_effort(progs, pid) for pid in coords}
    gens = sorted(progs[pid].gen for pid in coords)
    split = gens[int(0.75 * (len(gens) - 1))] if gens else 0
    log(f"4. the model's test (fitted up to generation {split}, asked about the later programs)")
    test = model_test(cb, coords, progs, effort, split)
    axes = cb.active_axes()
    full = LandscapeModel({a: cb.values(a) for a in axes}).fit(
        [{"coord": coords[pid], "y": progs[pid].score, "effort": effort[pid]} for pid in coords], min_rows=8)
    (out / "coords.jsonl").write_text("".join(json.dumps({"id": pid, "gen": progs[pid].gen, "coord": coords[pid],
                                                          "how": "replay", "effort": effort[pid]}) + "\n"
                                              for pid in sorted(coords)))
    (out / "annotations.jsonl").write_text("".join(json.dumps({**r, "gen": progs[r["id"]].gen}) + "\n" for r in rows))
    verdict = write_report(out / "REPLAY.md", run, cb, coords, rows, ag, test, full, progs, decisions)
    tmp = out / ".codebook.json.tmp"                  # written last: its presence means the replay finished
    tmp.write_text(json.dumps(cb.to_json(), indent=1))
    tmp.replace(out / "codebook.json")
    log("\n".join("   " + v for v in verdict))
    return {"axes": len(axes), "coords": len(coords), "twice": len(rows), "test": test, "verdict": verdict}


def write_report(path, run, cb, coords, rows, ag, test, m, progs, decisions):
    axes = cb.active_axes()
    good = [a for a in axes if ag.get(a, (0, 0, None))[0] >= 6 and ag[a][1] / ag[a][0] >= 0.8]
    measured = [a for a in axes if ag.get(a, (0, 0, None))[0] >= 6]
    v1 = (f"Reliability: {len(good)} of {len(measured)} measured decisions read with at least 80% agreement "
          f"({'pass' if measured and len(good) >= 0.5 * len(measured) else 'FAIL'})")
    rho, p = test.get("rho"), test.get("p")
    v2 = ("The model's knowledge: not testable (too few programs)" if rho is None else
          f"The model's knowledge: predicted vs actual change from base to child, rank correlation {rho:+.3f} over "
          f"{test['test']} later programs (permutation p = {p:.3f}; on the {test.get('moved')} that moved a decision: "
          + (f"{test['rho_moved']:+.3f}, p = {test['p_moved']:.3f}" if test.get("rho_moved") is not None else "-")
          + f") ({'pass' if rho > 0 and p is not None and p < 0.05 else 'FAIL'})")
    lines = [f"# The replay: is the design map real? ({Path(run).name})", "",
             f"Stage 0 of the proof of concept (`helix9/replay.py`, `docs/V9_DESIGN.md`). No programs were run.", "",
             "## Verdicts", "", f"- {v1}", f"- {v2}",
             f"- The codebook: {len(axes)} decisions from {len(decisions)} distinct names the Cartographer gave; "
             f"{len(coords)} programs read, {len(rows)} of them twice.", "",
             "## The decisions, how reliably they are read, and what the model says about them", "",
             "| Decision | Read twice | Agreement | Kappa | Importance |", "|---|---|---|---|---|"]
    imp = m.importance() if m.ready else {}
    for a in sorted(axes, key=lambda a: -imp.get(a, 0)):
        n, agree, k = ag.get(a, (0, 0, None))
        lines.append(f"| {a}: {cb.name(a)[:90]} | {n} | {agree / n:.0%} | {k:.2f} | {100 * imp.get(a, 0):.0f}% |"
                     if n else f"| {a}: {cb.name(a)[:90]} | 0 | - | - | {100 * imp.get(a, 0):.0f}% |")
    if m.ready:
        lines += ["", "## Options and their estimated effects (the whole archive)", ""]
        for a in sorted(axes, key=lambda a: -imp.get(a, 0))[:10]:
            eff = m.effects(a)
            lines.append(f"- **{a}: {cb.name(a)}**")
            for v, (e, sd, n) in sorted(eff.items(), key=lambda x: -x[1][0]):
                if v == "?" or n == 0:
                    continue
                lines.append(f"  - {cb.value_name(v)}: {n} programs, effect {e:+.6f} ± {sd:.6f}")
        if m.pairs:
            lines += ["", "Interacting decisions: " + ", ".join(f"{a} x {b}" for a, b in m.pairs)]
    Path(path).write_text("\n".join(lines) + "\n")
    return [v1, v2]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--double", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--fake", action="store_true")
    a = ap.parse_args(argv)
    if a.fake:
        from helix4.llm import FakeLLM
        from helix9.run import fake_answer
        import os
        llm = FakeLLM(fake_answer, delay=float(os.environ.get("FAKE_DELAY", "0") or 0))
    else:
        from helix4.llm import LLM
        trace = (Path(a.out) / "trace.jsonl")
        Path(a.out).mkdir(parents=True, exist_ok=True)
        fh = trace.open("a")

        def rec(c):
            fh.write(json.dumps({"t": round(time.time(), 1), **c}) + "\n")
            fh.flush()
        llm = LLM(on_call=rec)

    def call(role, system, user, temperature, max_tokens):
        try:
            return llm.chat(role, system, user, temperature=temperature, max_tokens=max_tokens, effort="none").text
        except Exception as exc:                                  # noqa: BLE001
            print(f"   ({role} call failed: {exc})", flush=True)
            return ""
    replay(a.run, a.out, call, a.sample, a.double, a.seed, log=lambda m: print(m, flush=True))


if __name__ == "__main__":
    main()
