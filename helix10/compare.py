"""v10.2's report (docs/V102_DESIGN.md): Helix from Code Zero with the field's ideas as axes, one or more seeds, set
against what is known from nothing: the field's own optimisers, the world's best program run here at the same CPU (if
the reference job runs), and Helix's earlier versions from Code Zero without the field's axes.

    python -m helix10.compare runs/v102 --out results/v102/COMPARISON.md       # also writes curves.csv beside it

Reads the run folders as the jobs write them (programs.jsonl, history.jsonl, trace.jsonl, tracks.jsonl,
borrowed.json, codebook.jsonl) and the field job's streams. Every number is computed from those files.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from helix10 import sota

ARMS = (("v102-helix", "Helix v10.2"),)
EARLIER = ("Helix v4 (Atlas) from Code Zero without the field's axes: 0.9390 at generation 20, 0.9408 by about "
           "generation 50, flat to generation 150 (results/v4cont/atlas-s1, docs/V4_CEILING.md); the long line of Helix "
           "runs continuing each other from Code Zero (v4.7, v7, v8, v9: about 800 generations) ended at 0.941442 "
           "(docs/VERSIONS.md).")
PUBLISHED = (   # LLM-driven discovery systems on this problem, with the budgets they report (TTT-Discover, Table 2,
                # arXiv:2601.16175; ThetaEvolve, Table 2, arXiv:2511.23473). Each starts from scratch or a simple program.
    ("AlphaEvolve (May 2025)", 0.8962, "Gemini 2.0 Pro + Flash", None, "not stated"),
    ("Best-of-25,600 samples", 0.9344, "gpt-oss-120b", 25600, "10 min"),
    ("OpenEvolve", 0.9449, "gpt-oss-120b", 25600, "10 min"),
    ("ThetaEvolve, without RL", 0.9434, "R1-Distill-Qwen3-8B", 51200, "350 s"),
    ("ThetaEvolve, with RL", 0.9469, "R1-Distill-Qwen3-8B (trained at test time)", 33280, "350 s"),
    ("TTT-Discover", 0.9591, "gpt-oss-120b (trained at test time)", 25600, "10 min"),
    ("AlphaEvolve V2 (Nov 2025; 50,000 steps)", 0.9610, "Gemini 2.0 Pro + Flash", None, "not stated"),
)
FIELD_SCRATCH = (0.90, 0.93)          # what the field's own optimisers reach from nothing (docs/AC2_SOTA.md)


def jl(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def arm_data(d):
    """Per generation: best, programs, CPU and tokens so far, for one run folder."""
    d = Path(d)
    progs = jl(d / "programs.jsonl")
    if not progs:
        return None
    by_gen = defaultdict(list)
    for p in progs:
        by_gen[p["gen"]].append(p)
    tok = Counter()
    calls = Counter()
    for r in jl(d / "trace.jsonl"):
        g = r.get("gen")
        if g is None:
            continue
        tok[g] += int(r.get("tokens_in") or 0) + int(r.get("tokens_out") or 0)
        calls[g] += 1
    st = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else {}
    done = st.get("gen_done", max(by_gen))
    rows, best, best_id, cpu, ntok, n = [], None, None, 0.0, 0, 0
    for g in range(0, done + 1):
        for p in by_gen.get(g, []):
            n += 1
            cpu += float(p.get("cpu") or 0.0)
            if p.get("valid") and p.get("score") is not None and (best is None or p["score"] > best):
                best, best_id = p["score"], p["id"]
        ntok += tok[g]
        rows.append({"gen": g, "best": best, "best_id": best_id, "programs": n, "cpu": round(cpu, 1),
                     "tokens": ntok, "calls": calls[g]})
    return {"rows": rows, "programs": {p["id"]: p for p in progs}, "state": st, "dir": d}


def at_gen(a, g):
    rows = [r for r in a["rows"] if r["gen"] <= g]
    return rows[-1] if rows else None


def at_cpu(a, c):
    rows = [r for r in a["rows"] if r["cpu"] <= c]
    return rows[-1] if rows else None


def fmt(x, d=9):
    return "-" if x is None else f"{x:.{d}f}"


def helix_story(a):
    """Where Helix's record came from: its track, how that track was opened, and every exploration built from nothing."""
    d = a["dir"]
    tr = jl(d / "tracks.jsonl")
    if not tr:
        return []
    last = tr[-1]
    tracks = {t["id"]: t for t in last.get("tracks", [])}
    best = max((p for p in a["programs"].values() if p.get("valid") and p.get("score") is not None),
               key=lambda p: p["score"])
    tid = (best.get("plan") or {}).get("track")
    t = tracks.get(tid) or {}
    takes = [(r["gen"], r["main"]) for r in tr]
    changes = [(g, m) for i, (g, m) in enumerate(takes) if i == 0 or m != takes[i - 1][1]]
    lines = [f"Helix's record: {best['score']:.12f} ({best['id']}, n = {best.get('n')}), on track {tid}: "
             f"{t.get('source', '?')}.",
             "The track holding the record, over the run: " + ", ".join(f"{m} from generation {g}" for g, m in changes)
             + "."]
    built = [t for t in tracks.values() if t.get("built")]
    if built:
        bv = json.loads((d / "borrowed.json").read_text()) if (d / "borrowed.json").exists() else {}
        lines += ["", f"Explorations built from nothing: {len(built)} "
                      f"({sum(1 for t in built if t['kind'] == 'build')} around an option of the field, "
                      f"{sum(1 for t in built if t['kind'] != 'build')} new designs from the map). Their climbs:", "",
                  "| Track | Built around | Opened | Experiments | Best | Race | Held the record |",
                  "|---|---|---|---|---|---|---|"]
        held = {m for _, m in changes}
        for t in sorted(built, key=lambda t: -(t.get("best") or 0))[:25]:
            r = t.get("race") or {}
            src = t["source"]
            what = src.split(" around ", 1)[1] if " around " in src else src.split("from nothing: ", 1)[-1]
            lines.append(f"| {t['id']} | {what[:90]} | {t['opened']} | "
                         f"{t.get('exps', 0)} | {fmt(t.get('best'))} | {r.get('status', '-')} | "
                         f"{'yes' if t['id'] in held else ''} |")
        vals = bv.get("values", {})
        tried = Counter()
        for t in tracks.values():
            for v in (t.get("target") or {}).values():
                if v in vals:
                    tried[v] += 1
        lines += ["", f"The field's options built at least once: {len(tried)} of {len(vals)}."]
    return lines


def report(root, out=None):
    root = Path(root)
    arms = {}
    for prefix, label in ARMS:
        for d in sorted(root.glob(prefix + "*")):
            if d.is_dir() and (d.name == prefix or d.name.startswith(prefix + "-s")):
                a = arm_data(d)
                if a is not None:
                    arms[d.name] = (label + ("" if d.name == prefix else f", seed {d.name.rsplit('-s', 1)[1]}"), a)
    cap = next((a["state"].get("config", {}).get("max_n") for _, a in arms.values()), None) or 50_000
    lines = ["# v10.2: Helix from Code Zero, with the field's ideas as axes", "",
             f"From Code Zero (R = 2/3), with the field's {len(sota.FINDINGS)} findings and "
             f"{sum(len(x['options']) for x in sota.AXES)} options on {len(sota.AXES)} decisions (the deep research, "
             f"helix10/sota.py) as axes, at most {cap:,} steps, the same CPU seconds per program, 3 planned "
             f"experiments and 3 mutations a generation. {EARLIER} For scale: the field's optimisers from nothing reach about "
             f"{FIELD_SCRATCH[0]:.2f}-{FIELD_SCRATCH[1]:.2f}; the best construction known with n <= 50,000 is AlphaEvolve "
             f"V2's 0.961021, with n <= 100,000 {sota.CLASS_BEST['score']:.12f} ({sota.CLASS_BEST['who']}), the arena's record "
             f"{sota.RECORD['score']:.12f} (n = 1,999,999).", ""]
    if not arms:
        lines.append("(no run has started yet)")
    else:
        common = min(a["rows"][-1]["gen"] for _, a in arms.values())
        marks = sorted({g for g in (1, 5, 10, 20, 30, 40, 60, 80, 100, 150, 200, 250, 300) if g <= common} | {common})
        lines += [f"## The climb, by generation (every run has finished {common})", "",
                  "| Generation | " + " | ".join(lbl for lbl, _ in arms.values()) + " |",
                  "|---|" + "---|" * len(arms)]
        for g in marks:
            vals = [at_gen(a, g) for _, a in arms.values()]
            lines.append(f"| {g} | " + " | ".join(fmt(v["best"] if v else None) for v in vals) + " |")
        cmax = min(a["rows"][-1]["cpu"] for _, a in arms.values())
        lines += ["", f"## The climb, by CPU ({cmax / 3600:.1f} CPU hours on programs so far)", "",
                  "| CPU hours | " + " | ".join(lbl for lbl, _ in arms.values()) + " |", "|---|" + "---|" * len(arms)]
        for frac in (0.1, 0.25, 0.5, 0.75, 1.0):
            c = cmax * frac
            lines.append(f"| {c / 3600:.2f} | " + " | ".join(fmt((at_cpu(a, c) or {}).get("best"))
                                                              for _, a in arms.values()) + " |")
        lines += ["", "## Cost", "", "| Run | Generations | Programs | CPU hours | Model calls | Tokens | Best |",
                  "|---|---|---|---|---|---|---|"]
        for name, (lbl, a) in arms.items():
            r = a["rows"][-1]
            lines.append(f"| {name} | {r['gen']} | {r['programs']} | {r['cpu'] / 3600:.1f} | "
                         f"{sum(x['calls'] for x in a['rows'])} | {r['tokens']:,} | {fmt(r['best'], 12)} ({r['best_id']}) |")
    if arms:
        lines += ["", "## Against the published LLM-driven systems", "",
                  "Their values and budgets as they report them (TTT-Discover's Table 2, arXiv:2601.16175: "
                  "AlphaEvolve, OpenEvolve, best-of-N and TTT-Discover; ThetaEvolve's Table 2, arXiv:2511.23473: its "
                  "steps of 512 programs; AlphaEvolve V2's construction has 50,000 steps). Each column: the programs "
                  "the run had evaluated when its best first passed that value (Helix's programs have "
                  f"{next(iter(arms.values()))[1]['state'].get('config', {}).get('budget', '?')} CPU s each).", "",
                  "| System | Model | Its value | Its programs | Its time per program | "
                  + " | ".join(f"{n}: programs to pass it" for n in arms) + " |",
                  "|---|---|---|---|---|" + "---|" * len(arms)]
        for name, val, model, progs, t in PUBLISHED:
            cells = []
            for _, a in arms.values():
                hit = next((r for r in a["rows"] if r["best"] is not None and r["best"] > val), None)
                cells.append(f"{hit['programs']:,} (generation {hit['gen']})" if hit else "not yet")
            lines.append(f"| {name} | {model} | {val:.4f} | {f'{progs:,}' if progs else 'not stated'} | {t} | "
                         + " | ".join(cells) + " |")
        lines.append("")
        lines.append("Helix's knowledge differs from theirs: its axes are the field's ideas as of October 2026 (the "
                     "deep research), some published after these systems ran. That is the claim under test: given "
                     "the literature's axes, Helix searches them as a space.")
    fdir = next((d for d in (root / "v102-field", root / "field") if (d / "field.jsonl").exists()), None)
    srows = [r for r in jl(fdir / "field.jsonl") if r.get("stream") == "scratch"] if fdir else []
    if srows:
        lines += ["", "## The world's best program from nothing (a reference)", "",
                  "ClaudeExplorer's method (iterated Dinkelbach alternating with velocity cycles, helix10/programs/), "
                  "chained from nothing at the same step limit and CPU per round, set beside each run at the same CPU:",
                  "", "| CPU hours | The field's program | " + " | ".join(n for n in arms) + " |",
                  "|---|---|" + "---|" * len(arms)]
        pick = sorted({max(1, len(srows) * k // 4) - 1 for k in (1, 2, 3, 4)})
        for i in pick:
            r = srows[i]
            c = float(r.get("cpu_total") or 0.0)
            lines.append(f"| {c / 3600:.2f} | {fmt(r.get('best'))} | "
                         + " | ".join(fmt((at_cpu(a, c) or {}).get("best")) for _, a in arms.values()) + " |")
        st = next((json.loads(f.read_text()) for f in [fdir / "streams" / "scratch.json"] if f.exists()), {})
        if st.get("finished"):
            lines.append(f"\nThe field's program {st['finished']}.")
    for name in [n for n in arms if n.startswith("v102-helix")]:
        lines += ["", f"## Where Helix's progress came from ({name})", ""] + helix_story(arms[name][1])
    text = "\n".join(lines) + "\n"
    if out:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        with (out.parent / "curves.csv").open("w") as fh:
            fh.write("arm,gen,best,programs,cpu_s,tokens\n")
            for name, (_, a) in arms.items():
                for r in a["rows"]:
                    fh.write(f"{name},{r['gen']},{r['best'] if r['best'] is not None else ''},{r['programs']},"
                             f"{r['cpu']},{r['tokens']}\n")
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="the folder holding v102-helix, v102-helix-s2 and v102-field")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    print(report(a.root, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
