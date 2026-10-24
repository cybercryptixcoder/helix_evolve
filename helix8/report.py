"""A v8 run's report (REPORT.md): v7's report (helix7/report.py), plus the map of hills.

    python -m helix8.report runs/v8warm --out results/v8warm/REPORT.md

The hills section lists every hill on the map: how it was found (a track and its kind, or an earlier run), its
top, how often other tracks landed on it, and its description; then the decisions every hill shared, and which were
flipped, with where each flip landed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from helix7.report import jl, report_run as report7


def hills_section(d):
    d = Path(d)
    rows = jl(d / "hills.jsonl")
    if not rows:
        return ""
    last, first = rows[-1], rows[0]
    hills = sorted(last.get("hills", []), key=lambda h: -h["top_score"])
    tracks = {t["id"]: t for t in ((jl(d / "tracks.jsonl")[-1:] or [{}])[0].get("tracks") or [])}
    start = len(first.get("hills", []))
    found = [h for h in hills if h["found_gen"] > first["gen"]]
    out = ["", f"### Hills ({len(hills)}: {start} on the map after its first generation, {len(found)} found since)", "",
           "| Hill | Top | Found | By | Other tracks landed on it | Description |", "|---|---|---|---|---|---|"]
    for h in hills:
        by = h.get("founder") or "-"
        kind = (tracks.get(by) or {}).get("kind", "")
        out.append(f"| {h['id']} | {h['top_score']:.6f} ({h['top']}) | {h['found_gen']} | {by}{' (' + kind + ')' if kind else ''}"
                   f" | {h['reached']} | {(h.get('description') or '-').replace('|', '/')[:220]} |")
    if last.get("shared"):
        out += ["", f"Decisions every hill shared (mapped at generation {last['shared'][0]['gen']}):", ""]
        tried = {}
        for key, g, tid in last.get("flipped", []):
            tried.setdefault(key, []).append((g, tid))
        for x in last["shared"]:
            t = tried.get(x["id"], [])
            where = "; ".join(f"generation {g} by {tid} ({(tracks.get(tid) or {}).get('hill_status') or 'unplaced'} "
                              f"{(tracks.get(tid) or {}).get('hill') or ''})".strip() for g, tid in t)
            out.append(f"- {x['id']}: {x['decision']} (all: {x['everyone']}){'; flipped at ' + where if where else ''}")
    return "\n".join(out) + "\n"


def report_run(d):
    return report7(d).replace("# Helix v7", "# Helix v8") + hills_section(d)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="a folder of run folders, or one run folder")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    root = Path(a.root)
    runs = [root] if (root / "history.jsonl").exists() else sorted(p for p in root.glob("*") if (p / "history.jsonl").exists())
    text = "# Helix v8: what exploration did, and the map of hills\n\n" + "\n".join(report_run(d) for d in runs)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
