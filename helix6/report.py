"""The presentation report for every version together (v4 baselines, v4.5, v5, v4.6, v6): one self-contained page.

    python -m helix6.report results/v4 results/v5 runs/v6 --out results/v6      # any number of run roots

Reuses the v4.5/v5 report (helix5/report.py) with the two new versions added, and, for v6, the agent's threads and
theory replayed from its event logs.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from helix4 import report as R
from helix5 import report as R5

ORDER = ["v6", "v46", "v5", "v45", "atlas", "journal", "control"]
LABEL = dict(R5.COND_LABEL, v6="v6 (the agent)", v46="v4.6 (Atlas, ideas + halo)")
LIGHT = "--c-v6:#7a3fd6;--c-v46:#0b0b0b;"
DARK = "--c-v6:#a37cf0;--c-v46:#e8e8e3;"


def v6_extras(d: Path):
    """The agent's threads and theory, replayed from its event logs."""
    if not (d / "threads.jsonl").exists():
        return None
    threads, theory = {}, {}
    for ev in R.jl(d / "threads.jsonl"):
        if ev["op"] == "open":
            threads[ev["id"]] = {"id": ev["id"], "question": ev.get("question", ""), "status": "open",
                                 "gen": ev["gen"], "versions": 1, "outcome": ""}
        elif ev.get("id") in threads:
            t = threads[ev["id"]]
            t["versions"] += 1
            if ev["op"] in ("close", "park"):
                t["status"] = {"close": "closed", "park": "parked"}[ev["op"]]
                t["outcome"] = ev.get("outcome") or ev.get("why") or t["outcome"]
            elif ev["op"] == "revise" and ev.get("question"):
                t["question"] = ev["question"]
    for ev in R.jl(d / "theory.jsonl"):
        if ev["op"] == "add":
            theory[ev["id"]] = {"id": ev["id"], "statement": ev.get("statement", ""), "kind": ev.get("kind", ""),
                                "confidence": ev.get("confidence", ""), "active": True, "versions": 1}
        elif ev.get("id") in theory:
            h = theory[ev["id"]]
            h["versions"] += 1
            if ev["op"] == "drop":
                h["active"] = False
            for k in ("statement", "kind", "confidence"):
                if ev.get(k):
                    h[k] = ev[k]
    return {"threads": list(threads.values()), "theory": list(theory.values())}


def v6_section(runs):
    runs = [r for r in runs if r.get("v6")]
    if not runs:
        return ""
    r = max(runs, key=lambda r: r["best"])
    x = r["v6"]
    out = [f"<h2>What the v6 agent kept</h2><p class='note'>{R.esc(r['name'])}: {len(x['threads'])} threads, "
           f"{len(x['theory'])} theory entries; every change is an explicit edit and every version is kept.</p>"
           "<div class='card'><p><strong>Threads</strong></p>"]
    for t in x["threads"]:
        out.append(f"<div class='finding'>{R.esc(t['id'])} · {R.esc(t['status'])}: {R.esc(t['question'][:300])}"
                   + (f"<div class='m'>outcome: {R.esc(str(t['outcome'])[:300])}</div>" if t["outcome"] else "")
                   + f"<div class='m'>opened in generation {t['gen']} · {t['versions']} versions</div></div>")
    out.append("<p><strong>Theory</strong></p>")
    for h in x["theory"]:
        out.append(f"<div class='finding'>{R.esc(h['id'])} · {R.esc(h['kind'])} ({R.esc(h['confidence'])})"
                   f"{'' if h['active'] else ' · dropped'}: {R.esc(h['statement'][:300])}"
                   f"<div class='m'>{h['versions']} versions</div></div>")
    out.append("</div>")
    return "\n".join(out)


def build(roots, out_dir: Path):
    old = R5.COND_ORDER, R5.COND_LABEL, R.load_run
    load = R.load_run

    def load_run(d):
        r = load(d)
        if r:
            r["v6"] = v6_extras(d)
        return r

    R5.COND_ORDER, R5.COND_LABEL, R.load_run = ORDER, LABEL, load_run
    try:
        path = R5.build(roots, out_dir)
    finally:
        R5.COND_ORDER, R5.COND_LABEL, R.load_run = old
    import json
    data = json.loads((out_dir / "report_data.json").read_text())
    page = path.read_text()
    page = page.replace("--c-v5:#2a78d6;", LIGHT + "--c-v5:#2a78d6;")
    page = page.replace("--c-v5:#3987e5;", DARK + "--c-v5:#3987e5;")
    page = page.replace(".k-v5{", ".k-v6{background:var(--c-v6)}.k-v46{background:var(--c-v46)}.k-v5{")
    page = page.replace("<title>Helix v4.5 and v5</title>", "<title>Helix, every version</title>")
    page = page.replace("<h1>Helix: v4, v4.5 and v5</h1>", "<h1>Helix: v4, v4.5, v5, v4.6 and v6</h1>")
    page = page.replace("and v5 (the researcher), several seeds each",
                        "v5 (the researcher), v4.6 (Atlas around ideas, with the mutation halo) and v6 (the agent), "
                        "several seeds each")
    page = page.replace("<div id=\"tip\"></div>", v6_section(data["runs"]) + "\n<div id=\"tip\"></div>", 1)
    path.write_text(page)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="+", help="folders of run folders (e.g. results/v4 results/v5 runs/v6)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    print(build(a.roots, Path(a.out)))


if __name__ == "__main__":
    main()
