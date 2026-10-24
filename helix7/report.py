"""A v7 run's report (REPORT.md): what exploration did, generation by generation.

    python -m helix7.report runs/v7warm --out results/v7warm/REPORT.md

For each run: the best score and where it came from, every record (the generation, the track and the kind of slot
that set it), how often each exploration level was used, the tracks opened by kind and how far each got, and one row
per generation (the level, the slots, the record, the track events).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()] if Path(p).exists() else []


def record_gens(d, rows):
    """The generations at which the record rose above the floor since the last record (the runs' own definition:
    helix7.run.Run.records), so small rises that add up count, as they do for the stall clock."""
    st = json.loads((Path(d) / "state.json").read_text()) if (Path(d) / "state.json").exists() else {}
    nz = json.loads((Path(d) / "noise.json").read_text()) if (Path(d) / "noise.json").exists() else {}
    fl = max(float((st.get("config") or {}).get("gain_floor", 1e-6)), float(nz.get("rel", 0.0)))
    rows = sorted((r for r in rows if r.get("best") is not None), key=lambda r: r["gen"])
    out, ref = [], rows[0]["best"] if rows else None
    for r in rows[1:]:
        if r["best"] > ref + fl * max(abs(ref), 1e-12):
            out.append(r["gen"])
            ref = r["best"]
    return out


def report_run(d):
    d = Path(d)
    hist = [h for h in jl(d / "history.jsonl") if "level" in h]
    if not hist:
        return f"## {d.name}\n\n(no v7 generations yet)\n"
    progs = {p["id"]: p for p in jl(d / "programs.jsonl")}
    tracks = (jl(d / "tracks.jsonl")[-1:] or [{"tracks": [], "main": None}])[0]
    noise = json.loads((d / "noise.json").read_text()) if (d / "noise.json").exists() else None
    first, last = hist[0], hist[-1]
    start = jl(d / "history.jsonl")
    before = [h for h in start if h["gen"] < first["gen"]]
    b0 = before[-1]["best"] if before else first["best"]
    out = [f"## {d.name}", "",
           f"- Generations {first['gen']}-{last['gen']}: best {b0:.9f} -> {last['best']:.9f} ({last['best_id']}, "
           f"track {last.get('best_track')}); the main track now: {tracks.get('main')}."]
    if noise:
        out.append(f"- Noise: the starting program scored {', '.join(f'{s:.6f}' for s in noise['scores'])}; a gain "
                   f"counts above {100 * noise['floor']:.3f}% (relative).")
    lv = Counter(h["level"] for h in hist)
    out.append(f"- Exploration levels: " + ", ".join(f"level {k}: {lv[k]} generations" for k in sorted(lv)) + ".")
    kinds = Counter(s.split(":")[0] for h in hist for s in h["slots"])
    out.append("- Planned experiments by slot: " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()) + ".")
    recs = [h for h in hist if h["gen"] in set(record_gens(d, start))]
    out += ["", f"### Records ({len(recs)})", ""]
    if recs:
        out += ["| Gen | Best | Program | Its role | Its slot | Track |", "|---|---|---|---|---|---|"]
        for h in recs:
            p = progs.get(h["best_id"], {})
            kind = (p.get("plan") or {}).get("kind") or ("mutation" if p.get("role") == "wide" else p.get("role", "?"))
            out.append(f"| {h['gen']} | {h['best']:.9f} | {h['best_id']} | {p.get('role', '?')} | {kind} | "
                       f"{h.get('best_track')} |")
    else:
        out.append("(none)")
    side = [t for t in tracks.get("tracks", []) if t.get("kind") in ("revive", "backtrack", "bold")]
    out += ["", f"### Side tracks opened ({len(side)})", ""]
    if side:
        out += ["| Track | Kind | Opened | From | Experiments | Its best | Last gain |", "|---|---|---|---|---|---|---|"]
        for t in side:
            b = f"{t['best']:.6f} ({t['best_id']})" if t.get("best") is not None else "-"
            out.append(f"| {t['id']} | {t['kind']}{' ' + t['revives'] if t.get('revives') else ''} | {t['opened']} | "
                       f"{t['root']} | {t.get('exps', 0)} | {b} | {t.get('last_gain')} |")
    out += ["", "### Generation by generation", "",
            "| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |",
            "|---|---|---|---|---|---|---|---|"]
    for h in hist:
        eb = f"{h['explore_best']:.6f}" if h.get("explore_best") is not None else ""
        ev = "; ".join(h.get("track_events") or [])
        out.append(f"| {h['gen']} | {h['best']:.9f} | {'yes' if h.get('new_best') else ''} | {h['stall']} / "
                   f"{h['typical_gap']:g} | {h['level']} | {', '.join(h['slots'])} | {eb} | {ev} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="a folder of run folders, or one run folder")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    root = Path(a.root)
    runs = [root] if (root / "history.jsonl").exists() else sorted(p for p in root.glob("*") if (p / "history.jsonl").exists())
    text = "# Helix v7: what exploration did\n\n" + "\n".join(report_run(d) for d in runs)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
