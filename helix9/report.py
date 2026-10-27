"""A v9 run's report (REPORT.md): v8's report (helix8/report.py: v7's, plus the map of hills), plus the design map.

    python -m helix9.report runs/v9warm --out results/v9warm/REPORT.md

The design-map section: the decisions found and how reliably they are read; the model's importance of each and its
options' effects; every drop, flip and ablation with its target, how much of it the coder built (read back), how its
race went and where it ended; discoveries; and constructions rebuilt on demand.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from helix8.report import report_run as report8
from helix9.codebook import Codebook
from helix9.pack import jl


def design_section(d):
    d = Path(d)
    rows = jl(d / "codebook.jsonl")
    if not rows:
        return ""
    cb = Codebook(rows[-1]["codebook"])
    hist = [h for h in jl(d / "history.jsonl") if h.get("map")]
    last = hist[-1]["map"] if hist else {}
    imp = last.get("importance") or {}
    coords = {r["id"]: r for r in jl(d / "coords.jsonl")}
    out = ["", f"### The design map ({len(cb.active_axes())} decisions, {len(coords)} programs placed)", "",
           "| Decision | Options | Read twice: agreement | Importance (last fit) |", "|---|---|---|---|"]
    for a in sorted(cb.active_axes(), key=lambda a: -imp.get(a, -1)):
        ag = cb.axes[a].get("agreement") or {}
        agt = f"{ag['rate']:.0%} of {ag['n']} (kappa {ag['kappa']:.2f})" if ag.get("n") and ag.get("kappa") is not None else "-"
        vals = "; ".join(cb.value_name(v)[:40] for v in cb.values(a)[:5]) + (" ..." if len(cb.values(a)) > 5 else "")
        out.append(f"| {a}: {(cb.axes[a].get('question') or cb.name(a)).replace('|', '/')[:90]} | {vals.replace('|', '/')} | "
                   f"{agt} | {100 * imp[a]:.0f}% |" if a in imp else
                   f"| {a}: {(cb.axes[a].get('question') or cb.name(a)).replace('|', '/')[:90]} | {vals.replace('|', '/')} | {agt} | - |")
    pairs = [k for k in imp if k.startswith("(")]
    if pairs:
        out += ["", "Interacting decisions in the last fit: " + ", ".join(pairs)]
    tracks = (jl(d / "tracks.jsonl")[-1:] or [{}])[0].get("tracks") or []
    mapped = [t for t in tracks if t.get("target")]
    if mapped:
        out += ["", f"### Explorations chosen from the map ({len(mapped)}: "
                + ", ".join(f"{n} {k}s" for k, n in Counter(t['kind'] for t in mapped).items()) + ")", "",
                "| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |",
                "|---|---|---|---|---|---|---|---|---|"]
        for t in sorted(mapped, key=lambda t: t["opened"]):
            land = t.get("landing") or {}
            built = f"{land['matched']}/{land['of']}" if land else "-"
            race = t.get("race") or {}
            last_dec = (race.get("decisions") or [{}])[-1]
            rs = race.get("status", "-") + (f" at {last_dec.get('rung')}" if last_dec.get("rung") else "")
            tgt = "; ".join(f"{a} -> {cb.value_name(v)[:30]}" for a, v in (t["target"] or {}).items())
            best = f"{t['best']:.6f}" if t.get("best") is not None else "-"
            out.append(f"| {t['id']} | {t['kind']} | {t['opened']} | {tgt.replace('|', '/')} | {built} | {t.get('exps', 0)} | "
                       f"{best} | {rs} | {t.get('hill_status') or '-'} {t.get('hill') or ''} |")
    disc = jl(d / "discoveries.jsonl")
    if disc:
        out += ["", "### Discoveries (programs at the same design that scored too differently: what differs?)", ""]
        for r in disc:
            dec = (r.get("reply") or {}).get("decision")
            out.append(f"- generation {r['gen']}, {r['pair'][0]} vs {r['pair'][1]}: "
                       + (f"{dec} ({r.get('axis')}{', new' if r.get('new') else ', an existing axis'})" if dec else "no decision named"))
    reb = jl(d / "rebuilt.jsonl")
    if reb:
        out += ["", f"### Constructions rebuilt on demand ({len(reb)})", ""]
        for r in reb[-20:]:
            out.append(f"- {r['id']} (generation {r['gen']}): from {r.get('from') or 'nothing'}, "
                       + (f"{r['rebuilt']:.6f} (recorded {r['recorded']:.6f})" if r.get("ok") else "failed"))
    return "\n".join(out) + "\n"


def report_run(d):
    return report8(d).replace("# Helix v8", "# Helix v9") + design_section(d)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="a folder of run folders, or one run folder")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    root = Path(a.root)
    runs = [root] if (root / "history.jsonl").exists() else sorted(p for p in root.glob("*") if (p / "history.jsonl").exists())
    text = "# Helix v9: the map of hills and the design map\n\n" + "\n".join(report_run(d) for d in runs)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
