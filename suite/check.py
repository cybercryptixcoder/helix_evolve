"""Check a suite problem: determinism, speed, Code Zero, the example features, diagnostics.

    python -m suite.check tsp
    python -m suite.check --all
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from helix3.policy import compile_feature, make_priority
from helix3.problem import REGISTRY, load_problem


def check(name, verbose=True):
    say = print if verbose else (lambda *a, **k: None)
    p = load_problem(name)
    problems = []
    say(f"== {name}: {p.title}")
    for attr in ("description", "signature", "signature_doc", "families"):
        if not getattr(p, attr):
            problems.append(f"missing {attr}")
    zero = make_priority([], [], p.n_candidates)
    for split in ("train", "valid", "test"):
        insts = p.instances(split)
        again = p.instances(split)
        if [i["id"] for i in insts] != [i["id"] for i in again]:
            problems.append(f"{split}: instances are not deterministic")
        fams = sorted({i["family"] for i in insts})
        t = time.time()
        gaps = [p.run(i, zero)["gap"] for i in insts]
        dt = time.time() - t
        say(f"  {split:5s}: {len(insts):3d} instances, families {fams}; Code Zero mean gap {np.mean(gaps):.2f}% "
            f"({dt:.2f}s, {1000 * dt / max(1, len(insts)):.0f} ms each)")
        if split == "train" and dt > 1.5:
            problems.append(f"train split takes {dt:.1f}s with Code Zero; keep it under ~1s")
        if any(not np.isfinite(g) for g in gaps):
            problems.append(f"{split}: non-finite gap")
        if getattr(p, "open_ceiling", False) and any(g != 100.0 for g in gaps):
            problems.append(f"{split}: open-ceiling problem, but Code Zero's gap is not exactly 100")
        if split == "train" and set(fams) != set(p.families):
            problems.append(f"train families {fams} != declared {p.families}")
    for i, code in enumerate(p.example_features):
        compile_feature(code)
        pr = make_priority([code], [[1.0]], p.n_candidates)
        t = time.time()
        gaps = [p.run(inst, pr)["gap"] for inst in p.instances("train")]
        say(f"  example feature {i}: mean train gap {np.mean(gaps):.2f}% ({time.time() - t:.2f}s)")
    iid = p.diagnostic_ids()[0]
    inst = p.instance("train", iid)
    d = p.diagnose(inst, zero)
    r = p.reference_metrics(inst)
    say(f"  diagnose {iid}: {d}")
    say(f"  reference {iid}: {r}")
    unknown = [k for k in d if not k.startswith("_") and k != "gap" and k not in p.metric_notes]
    if unknown:
        problems.append(f"metrics without a note in metric_notes: {unknown}")
    for fam in p.families:
        try:
            p.floor(fam)
        except TypeError:
            p.floor(fam, "train")
    say("  OK" if not problems else "  PROBLEMS: " + "; ".join(problems))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    names = list(REGISTRY) if a.all else a.names
    bad = {}
    for n in names:
        try:
            pr = check(n)
        except Exception as exc:  # noqa: BLE001
            pr = [f"{type(exc).__name__}: {exc}"]
            print(f"  FAILED: {pr[0]}")
        if pr:
            bad[n] = pr
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
