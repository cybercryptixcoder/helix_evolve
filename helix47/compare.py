"""v4.7 against v4, from the run folders of one job: a Markdown table, generation by generation.

    python -m helix47.compare runs/v47 --out results/v47/COMPARISON.md

Reads each run folder's history.jsonl (and v4.7's lines.jsonl and programs.jsonl). Works on unfinished runs.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def at(hist, g):
    rows = [h for h in hist if h["gen"] <= g]
    return rows[-1]["best"] if rows else None


def last_real_gain(hist, eps=1e-5):
    g = 0
    for i in range(1, len(hist)):
        if hist[i]["best"] > hist[i - 1]["best"] * (1 + eps):
            g = hist[i]["gen"]
    return g


def build(root):
    root = Path(root)
    runs = sorted(d for d in root.glob("*-s*") if d.is_dir() and (d / "history.jsonl").exists())
    marks = [5, 10, 15, 20, 25, 30, 40, 50]
    rows, by_cond = [], {}
    gmax = 0
    for d in runs:
        h = jl(d / "history.jsonl")
        if not h:
            continue
        gmax = max(gmax, h[-1]["gen"])
        cond = d.name.rsplit("-s", 1)[0]
        by_cond.setdefault(cond, []).append(h)
        extra = ""
        if (d / "lines.jsonl").exists():
            rows_l = jl(d / "lines.jsonl")
            lines = rows_l[-1]["lines"] if rows_l else []
            alts = sum(1 for p in jl(d / "programs.jsonl") if p.get("role") == "alt")
            first_close = next((x["ended"] for x in lines if x.get("ended")), None)
            records = [r for r in h[1:] if r.get("new_best")]
            late = [r for r in records if first_close is not None and r["gen"] > first_close]
            by_new = [r for r in late if r.get("best_line") not in (None, "L1")]
            extra = (f"{len(lines)} lines (first closed at g{first_close}); records after it: {len(late)}, "
                     f"{len(by_new)} by new lines; best now on {h[-1].get('best_line', '?')}; {alts} alternatives kept"
                     if first_close is not None else f"1 line, never closed; {alts} alternatives kept")
        rows.append((d.name, h, extra))
    marks = [m for m in marks if m <= gmax] + ([gmax] if gmax not in marks else [])
    out = [f"# v4.7 against v4 ({root})", "", "Best score by generation (the second autocorrelation inequality; higher is "
           "better). 'Last real gain' is the last generation where the best rose by more than 1e-5 relative.", "",
           "| Run | " + " | ".join(f"g{m}" for m in marks) + " | Last real gain | v4.7 mechanisms |",
           "|---|" + "---|" * len(marks) + "---|---|"]
    for name, h, extra in rows:
        cells = [f"{at(h, m):.6f}" if at(h, m) is not None else "-" for m in marks]
        out.append(f"| {name} | " + " | ".join(cells) + f" | g{last_real_gain(h)} | {extra} |")
    out += ["", "| Condition (median of seeds) | " + " | ".join(f"g{m}" for m in marks) + " |",
            "|---|" + "---|" * len(marks)]
    for cond, hs in sorted(by_cond.items()):
        cells = []
        for m in marks:
            v = [at(h, m) for h in hs if at(h, m) is not None and h[-1]["gen"] >= m]
            cells.append(f"{statistics.median(v):.6f}" if v else "-")
        out.append(f"| {cond} ({len(hs)} runs) | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    text = build(a.root)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
