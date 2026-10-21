"""The presentation report for v4 (baselines), v4.5 and v5 together: one self-contained HTML page.

    python -m helix5.report results/v4 runs/v5 --out results/v5     # any number of run roots

Reuses the v4 report (helix4/report.py) for loading runs and the page, with: the two new conditions; the reference
lines that matter for the claim (the 2010 record, AlphaEvolve's May 2025 result, the published human best, the best
known); a y-axis zoomed on the interesting range; and, for v5, the researcher's agenda and theory.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from helix4 import report as R

COND_ORDER = ["v5", "v45", "atlas", "journal", "control"]
COND_LABEL = {"v5": "v5 (the researcher)", "v45": "v4.5 (Atlas+)", "atlas": "v4 Atlas", "journal": "v4 Journal",
              "control": "v4 Control (no memory)"}
REFS = [("2010 record", 0.88922), ("AlphaEvolve, May 2025", 0.896280), ("Boyer & Li 2025", 0.901564),
        ("human best (Jaech & Joseph)", 0.94136), ("AlphaEvolve, later", 0.9610), ("best known", 0.962643)]
CHART_REFS = [("2010 record", 0.88922), ("AlphaEvolve May 2025", 0.896280), ("human best", 0.94136),
              ("best known", 0.962643)]


def jl(path):
    return R.jl(path)


def v5_extras(d: Path):
    """The researcher's agenda and theory, replayed from its event logs."""
    if not (d / "notebook.jsonl").exists():
        return None
    items, beliefs, summary, steps = {}, {}, None, 0
    for ev in jl(d / "agenda.jsonl"):
        if ev["op"] in ("add", "branch"):
            items[ev["id"]] = {"id": ev["id"], "purpose": ev.get("purpose", ""), "status": "open", "outcome": "",
                               "gen": ev["gen"], "versions": 1}
        elif ev["id"] in items:
            it = items[ev["id"]]
            it["versions"] += 1
            if ev["op"] == "done":
                it["status"], it["outcome"] = "done", ev.get("outcome", "")
            elif ev["op"] in ("park", "drop"):
                it["status"] = {"park": "parked", "drop": "dropped"}[ev["op"]]
            elif ev["op"] == "reopen":
                it["status"] = "open"
    for ev in jl(d / "beliefs.jsonl"):
        if ev["op"] == "summary":
            summary = ev
        elif ev["op"] == "add":
            beliefs[ev["id"]] = {"id": ev["id"], "statement": ev.get("statement", ""), "kind": ev.get("kind"),
                                 "active": True, "versions": 1, "evidence": ev.get("evidence") or []}
        elif ev.get("id") in beliefs:
            b = beliefs[ev["id"]]
            b["versions"] += 1
            if ev["op"] == "drop":
                b["active"] = False
            if ev.get("statement"):
                b["statement"] = ev["statement"]
            b["evidence"] += ev.get("add_evidence") or []
    steps = sum(1 for e in jl(d / "notebook.jsonl") if e["op"] == "step")
    return {"items": list(items.values()), "beliefs": list(beliefs.values()), "summary": summary, "steps": steps}


def build(roots, out_dir: Path):
    runs = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                r = R.load_run(d)
                if r:
                    r["v5"] = v5_extras(d)
                    runs.append(r)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {"runs": runs, "refs": CHART_REFS, "labels": COND_LABEL, "order": COND_ORDER}
    best = max(runs, key=lambda r: r["best"]) if runs else None
    rows = []
    for c in COND_ORDER:
        rs = [r for r in runs if r["condition"] == c]
        if not rs:
            continue
        bests = [r["best"] for r in rs]
        dr = [r["deep_rate"] for r in rs if r["deep_rate"] is not None]
        wr = [r["wide_rate"] for r in rs if r["wide_rate"] is not None]
        rows.append(f"<tr><td><span class='key k-{c}'></span>{R.esc(COND_LABEL[c])}</td>"
                    f"<td class='num'>{', '.join(f'{b:.5f}' for b in bests)}</td>"
                    f"<td class='num'>{statistics.median(bests):.5f}</td><td class='num'>{max(bests):.5f}</td>"
                    f"<td class='num'>{(100 * statistics.mean(dr)) if dr else 0:.0f}%</td>"
                    f"<td class='num'>{(100 * statistics.mean(wr)) if wr else 0:.0f}%</td>"
                    f"<td class='num'>{sum(r['records']['deep'] for r in rs)} / {sum(r['records']['wide'] for r in rs)}</td>"
                    f"<td class='num'>{sum(1 for b in bests if b > 0.896280)} of {len(bests)}</td>"
                    f"<td class='num'>{sum(r['failed'] for r in rs)}/{sum(r['programs'] for r in rs)}</td></tr>")
    status = (f"{sum(r['finished'] for r in runs)} of {len(runs)} runs finished; generations done: "
              + ", ".join(f"{r['name']} {r['gens_done']}" for r in runs)) if runs else "no runs yet"
    hero = ""
    if best:
        beaten = [n for n, v in REFS if best["best"] > v]
        hero = (f"<div class='hero'><div class='tile'><div class='label'>Best lower bound found</div>"
                f"<div class='value'>{best['best']:.6f}</div><div class='sub'>{R.esc(best['name'])}, program "
                f"{R.esc(best['best_id'])}, {best['best_n']} steps</div></div>"
                f"<div class='tile'><div class='label'>AlphaEvolve, May 2025 (same problem, same scoring)</div>"
                f"<div class='value small'>0.896280</div><div class='sub'>50 steps; DeepMind's published construction</div></div>"
                f"<div class='tile'><div class='label'>Published results passed</div><div class='value small'>"
                f"{len(beaten)} of {len(REFS)}</div><div class='sub'>{R.esc(', '.join(beaten) or 'none yet')}</div></div></div>")
    v5html = v5_section([r for r in runs if r.get("v5")])
    page = R.TEMPLATE
    page = page.replace("--c-atlas:#2a78d6;--c-journal:#eb6834;--c-control:#1baf7a;",
                        "--c-v5:#2a78d6;--c-v45:#eb6834;--c-atlas:#1baf7a;--c-journal:#eda100;--c-control:#e87ba4;")
    page = page.replace("--c-atlas:#3987e5;--c-journal:#d95926;--c-control:#199e70;",
                        "--c-v5:#3987e5;--c-v45:#d95926;--c-atlas:#199e70;--c-journal:#c98500;--c-control:#d55181;")
    page = page.replace(".k-atlas{background:var(--c-atlas)}",
                        ".k-v5{background:var(--c-v5)}.k-v45{background:var(--c-v45)}.k-atlas{background:var(--c-atlas)}")
    page = page.replace("<title>Helix v4 results</title>", "<title>Helix v4.5 and v5</title>")
    page = page.replace("<h1>Helix v4: program evolution with memory</h1>", "<h1>Helix: v4, v4.5 and v5</h1>")
    page = page.replace("R=W<560?16:150", "R=W<560?16:200")
    page = page.replace("Three memory conditions\n(what the Researcher sees of the past) × several seeds, same models, budgets and evaluator.",
                        "v4's three memory conditions (Control, Journal, Atlas), v4.5 (Atlas with the fixes the v4 run "
                        "showed) and v5 (the researcher), several seeds each, same models, budgets and evaluator.")
    page = page.replace("const ymin=Math.floor(Math.min(0.66,...vals)*50)/50",
                        "const ymin=0.80")
    page = page.replace("Y=v=>T+(H-T-B)*(1-(v-ymin)/(ymax-ymin));", "Y=v=>T+(H-T-B)*(1-(Math.max(v,ymin)-ymin)/(ymax-ymin));")
    page = page.replace("Grey rules: published records (shown here only; the agents never see them).",
                        "Grey rules: published results (shown here only; the agents never see them). The axis starts at "
                        "0.80; every run starts at 0.667 (generation 0), drawn at the bottom edge.")
    page = page.replace("<th class=\"num\">Cited per plan</th>", "<th class=\"num\">Above AlphaEvolve May 2025</th>")
    page = page.replace('"Cited per plan" = earlier programs or findings each planned experiment says it builds on.',
                        '"Above AlphaEvolve May 2025" = runs whose best construction scores above 0.896280.')
    page = page.replace("<div id=\"tip\"></div>", v5html + "\n<div id=\"tip\"></div>")
    page = page.replace("/*DATA*/", json.dumps(data).replace("</", "<\\/")).replace("<!--HERO-->", hero) \
        .replace("<!--ROWS-->", "\n".join(rows)).replace("<!--STATUS-->", R.esc(status))
    (out_dir / "report.html").write_text(page)
    (out_dir / "report_data.json").write_text(json.dumps(data, indent=1))
    return out_dir / "report.html"


def v5_section(runs):
    if not runs:
        return ""
    r = max(runs, key=lambda r: r["best"])
    x = r["v5"]
    out = [f"<h2>What the v5 researcher kept</h2><p class='note'>{R.esc(r['name'])}: {x['steps']} notebook steps, "
           f"{len(x['items'])} agenda items, {len(x['beliefs'])} beliefs. Every change was an explicit, reasoned edit; "
           f"every version is kept.</p><div class='card'>"]
    if x.get("summary"):
        out.append(f"<p><strong>Its theory (generation {x['summary']['gen']}):</strong> {R.esc(x['summary']['text'])}</p>")
    out.append("<p><strong>Agenda</strong></p>")
    for it in x["items"]:
        out.append(f"<div class='finding'>{R.esc(it['id'])} · {R.esc(it['status'])}: {R.esc(it['purpose'][:300])}"
                   + (f"<div class='m'>outcome: {R.esc(it['outcome'][:300])}</div>" if it["outcome"] else "")
                   + f"<div class='m'>opened in generation {it['gen']} · {it['versions']} versions</div></div>")
    out.append("<p><strong>Beliefs</strong></p>")
    for b in x["beliefs"]:
        out.append(f"<div class='finding'>{R.esc(b['id'])} · {R.esc(b['kind'])}{'' if b['active'] else ' · dropped'}: "
                   f"{R.esc(b['statement'][:300])}<div class='m'>evidence {R.esc(', '.join(b['evidence'][:8]))} · "
                   f"{b['versions']} versions</div></div>")
    out.append("</div>")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="+", help="folders of run folders (e.g. results/v4 runs/v5)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    print(build(a.roots, Path(a.out)))


if __name__ == "__main__":
    main()
