"""Guided walkthrough of a feature-engine run: one step per screen, explanation visible, raw text one click away.

    python -m viz.walk results/<run>            # writes <run>/walkthrough.html
    python -m viz.walk results/<run> --out x.html

Each generation becomes six steps (Inspect, Researcher, Coders, Mutator, Fit, Accept), followed by the run's
findings. The explanation on each step comes from the run's notes.json when there is one, otherwise from what
the trace itself shows. Every step also carries automatic checks ("does this match the intent?") computed from
the trace: repeated ideas, Mutator variants aimed at one feature, predictions never checked.
"""
import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from viz.export import build_trace

E = html.escape
NODES = ["Library", "Inspect", "Researcher", "Coder", "Mutator", "Fit", "Accept"]
LLM = {"Researcher", "Coder", "Mutator"}


def num(v, d=3):
    return "—" if v is None else f"{v:+.{d}f}".replace("-", "−")


def md(text):
    """Just enough markdown for the notes: paragraphs, bullets, bold, code."""
    out = []
    for block in re.split(r"\n\s*\n", text or ""):
        t = E(block.strip())
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", t)
        if t.startswith("- "):
            out.append("<ul>" + "".join(f"<li>{x[2:]}</li>" for x in t.split("\n")) + "</ul>")
        elif t:
            out.append(f"<p>{t}</p>")
    return "".join(out)


def raw(label, text):
    return f"<details><summary>{E(label)}</summary><pre>{E(text or '')}</pre></details>"


def check(ok, text):
    cls = {True: "ok", False: "bad", None: "warn"}[ok]
    mark = {True: "✓", False: "✗", None: "!"}[ok]
    return f'<li class="{cls}"><span>{mark}</span>{text}</li>'


def probe_key(f):
    p = f.get("probe") or []
    return tuple(sorted(round(x["delta"], 3) for x in p)) or None   # sign-blind: a flipped feature is the same idea


def steps_for(t):
    calls = {c["id"]: c for c in t["calls"]}
    ideas = {i["feature"]: i for i in t["ideas"] if i.get("feature")}
    notes = t.get("notes") or {}
    nc, nf, ng = notes.get("calls", {}), notes.get("features", {}), notes.get("generations", {})
    champs = t["champions"]
    margin = t["run"]["config"].get("accept_margin", 0.03)
    seen = {}                      # probe fingerprint -> first feature id, across generations (same champion only)
    steps = []

    cz = t["run"]["code_zero"]
    steps.append(dict(gen=0, title="Generation 0: Code Zero", lit=["Library"],
                      what=md(ng.get("0", "")) or "<p>The library starts empty. Every bin scores 0, so the oldest bin "
                                                     "that fits wins: First Fit.</p>",
                      body=f"<p class='big'>Score {num(cz['score'])}</p>" + (md(notes.get("run", "")) if notes.get("run") else ""),
                      checks=[], raw=""))

    for g in t["generations"]:
        n = g["gen"]
        if n == 0:
            continue
        gc = [c for c in t["calls"] if c["gen"] == n]
        feats = [f for f in t["features"] if f["gen"] == n]
        deep = [f for f in feats if f["branch"] == "deep"]
        wide = [f for f in feats if f["branch"] == "wide"]
        res = [c for c in gc if c["role"] == "researcher"]
        before = (g.get("before") or {})
        bchamp = before.get("id")

        # ---- Inspect
        rows = []
        for fam, p in sorted((g.get("packings") or {}).items(),
                             key=lambda kv: -(kv[1]["champion"]["bins"] - (kv[1].get("optimum") or {}).get("bins", 0))):
            c, o = p["champion"], p.get("optimum") or {}
            rows.append(f"<tr><td>{E(fam)}</td><td>{c['bins']} vs {o.get('bins','?')}</td>"
                        f"<td>{c['mean_jobs']} vs {o.get('mean_jobs','?')}</td><td>{c['stranded']} vs {o.get('stranded','?')}</td></tr>")
        steps.append(dict(gen=n, title=f"Generation {n} · Inspect", lit=["Library", "Inspect"],
                          what=f"<p>Code, not an LLM. The champion ({E(bchamp or '')}, {num(before.get('official'))}) packs one "
                               "instance per family, next to a near-optimal packing of the same jobs. This table is what the "
                               "Researcher will read. The Mutator never sees it.</p>",
                          body="<table><tr><th>Family</th><th>Bins</th><th>Jobs per bin</th><th>Stranded</th></tr>"
                               + "".join(rows) + "</table><p class='small'>champion vs near-optimal, biggest gap first</p>",
                          checks=[], raw=raw("Exact text sent to the Researcher", g.get("packings_text"))))

        # ---- Researcher
        lens = ""
        if res:
            m = re.search(r"through this lens: (.+?)\.", res[0]["user"])
            lens = m.group(1) if m else ""
        stuck = bool(res) and "hasn't improved" in res[0]["user"]
        idea_html = "".join(
            f"<div class='idea'><b>{E(f['name'])}</b><p><span class='lbl'>saw</span>{E(ideas[f['id']]['claim'])}</p>"
            f"<p><span class='lbl'>predicts</span>{E(ideas[f['id']]['target'])}</p></div>"
            for f in deep if f["id"] in ideas)
        ck = [check(None, "Each idea predicts a number that should move. Nothing ever checks it.")]
        if stuck and not (before.get("id") and champs.get(before["id"], {}).get("features")):
            ck.append(check(False, "Told “the small refinements are used up” while the policy has no features yet."))
        steps.append(dict(gen=n, title=f"Generation {n} · Researcher proposes ideas", lit=["Inspect", "Researcher"],
                          what=(f"<p class='lens'>Lens this generation: <b>{E(lens)}</b></p>" if lens else "")
                               + md(nc.get(res[0]["id"], "") if res else "")
                               + (f"<p class='small'>LLM call, {res[0]['seconds']:.1f} s, thinking off.</p>" if res else ""),
                          body=idea_html, checks=ck,
                          raw="".join(raw(f"Exact prompt ({c['id']})", c["user"]) + raw(f"Exact reply ({c['id']})", c["reply"])
                                      for c in res)))

        # ---- Coders
        rows = "".join(f"<tr><td><b>{E(f['name'])}</b></td><td>{E(f.get('note') or '')}</td></tr>" for f in deep)
        steps.append(dict(gen=n, title=f"Generation {n} · Coders write the ideas", lit=["Researcher", "Coder"],
                          what=f"<p>{len(deep)} LLM calls in parallel. Each Coder gets one idea and the list of existing "
                               "features, and writes it as <code>feature(item, bins, capacity)</code>. Its one sentence "
                               "says how it read the idea.</p>",
                          body=f"<table><tr><th>Feature</th><th>The Coder's note</th></tr>{rows}</table>",
                          checks=[], raw="".join(raw(f"{f['name']}: code", f.get("code")) for f in deep)))

        # ---- Mutator
        targets = Counter(f["note"].split(" | ")[0] for f in wide if (f.get("note") or "").startswith("variant"))
        rows = "".join(f"<tr><td><b>{E(f['name'])}</b></td><td>{E(f.get('note') or '')}</td>"
                       f"<td>{E(f.get('description') or '')}</td></tr>" for f in wide)
        ck = [check(None, "Sees only the champion's code and score: no packings, no ideas, no verdicts, no memory.")]
        if targets and max(targets.values()) >= 2:
            tgt, k = targets.most_common(1)[0]
            ck.append(check(False, f"{k} of {len(wide)} slots are a {E(tgt)}: not wide."))
        steps.append(dict(gen=n, title=f"Generation {n} · Mutator writes features (at the same time)", lit=["Library", "Mutator"],
                          what=f"<p>{len(wide)} LLM calls, running alongside the deep loop. Each is asked for a variant of a "
                               "named feature or a fresh one, and returns code and a name, with no explanation.</p>",
                          body=f"<table><tr><th>Feature</th><th>Asked for</th><th>Its docstring</th></tr>{rows}</table>",
                          checks=ck,
                          raw="".join(raw(f"{f['name']}: prompt", calls[f['calls'][0]]["user"]) + raw(f"{f['name']}: code", f.get("code"))
                                      for f in wide if f.get("calls"))))

        # ---- Fit
        groups = {}
        for f in feats:
            k = probe_key(f)
            if k:
                groups.setdefault((bchamp, k), []).append(f)
        rows = []
        for f in sorted(feats, key=lambda f: -(f.get("delta_valid") if f.get("delta_valid") is not None else -99)):
            best = max((p["delta"] for p in f.get("probe") or []), default=None)
            rows.append(f"<tr class='{f['verdict']}'><td>{E(f['name'])}</td><td>{f['branch']}</td><td>{num(best)}</td>"
                        f"<td>{num(f.get('delta_valid'))}</td><td>{E(f['verdict'])}</td></tr>")
        ck = []
        dup = [v for v in groups.values() if len(v) > 1]
        for v in dup:
            ck.append(check(False, "Same probe scores, so the same ranking of bins: "
                                   + ", ".join(E(f["name"]) for f in v) + "."))
        for (champ, k), v in groups.items():
            if (champ, k) in seen:
                ck.append(check(False, f"{E(v[0]['name'])} repeats {E(seen[(champ, k)])} from an earlier generation."))
            seen.setdefault((champ, k), v[0]["name"])
        np_ = sum(f["verdict"] == "probe-rejected" for f in feats)
        if np_:
            ck.append(check(None, f"{np_} of {len(feats)} rejected by the probe, each judged alone on top of the champion."))
        steps.append(dict(gen=n, title=f"Generation {n} · Fit judges every feature", lit=["Coder", "Mutator", "Fit"],
                          what="<p>Code, no LLM. <b>Probe:</b> the feature alone on top of the champion at four weights; "
                               "worse at every weight means rejected. <b>Trial</b> for survivors: refit with and without "
                               f"it, credited with the difference on validation (needs more than +{margin}).</p>",
                          body="<table><tr><th>Feature</th><th>Loop</th><th>Best probe</th><th>Validation</th><th>Verdict</th></tr>"
                               + "".join(rows) + "</table>",
                          checks=ck, raw=raw("The run's own log", "\n".join(g.get("console") or []))))

        # ---- Accept
        kept = [f for f in feats if f["verdict"] == "kept"]
        ch = champs.get(g["champion"], {})
        body = (f"<p class='big'>{num(before.get('official'))} → {num(g.get('official'))}"
                f" <span class='small'>{ch.get('progress', 0):.1f}% of the way to optimal</span></p>")
        body += "".join(f"<div class='idea kept'><b>kept: {E(f['name'])}</b> ({f['branch']}){md(nf.get(f['id'], ''))}</div>"
                        for f in kept) or "<p>Nothing kept. The champion carries over unchanged.</p>"
        ck = [check(None, "Verdicts go to the Researcher's log only. A probe rejection is logged as “refuted” with no number.")]
        if wide:
            ck.append(check(None if not any(f['verdict'] == 'kept' for f in wide) else True,
                            f"From the Mutator: {sum(f['verdict'] == 'kept' for f in wide)} of {len(wide)} kept."))
        steps.append(dict(gen=n, title=f"Generation {n} · Accept", lit=["Fit", "Accept", "Library"],
                          what=md(ng.get(str(n), "")), body=body, checks=ck,
                          raw=raw("New champion's code", ch.get("code"))))

    if notes.get("findings"):
        steps.append(dict(gen=None, title="What stands out", lit=[], what="",
                          body="".join(f"<div class='idea'><b>{E(x['title'])}</b>{md(x['text'])}</div>" for x in notes["findings"]),
                          checks=[], raw=""))
    return steps


def diagram(lit):
    pos = {"Library": (160, 20), "Inspect": (40, 75), "Researcher": (40, 125), "Coder": (40, 175),
           "Mutator": (280, 125), "Fit": (160, 230), "Accept": (160, 280)}
    out = ['<svg viewBox="0 0 380 320" class="dia">']
    for a, b in [("Library", "Inspect"), ("Inspect", "Researcher"), ("Researcher", "Coder"), ("Coder", "Fit"),
                 ("Library", "Mutator"), ("Mutator", "Fit"), ("Fit", "Accept"), ("Accept", "Library")]:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        on = a in lit and b in lit
        out.append(f'<line x1="{x1+50}" y1="{y1+16}" x2="{x2+50}" y2="{y2+16}" class="{"on" if on else ""}"/>')
    for k, (x, y) in pos.items():
        cls = ("lit " if k in lit else "") + ("llm" if k in LLM else "")
        out.append(f'<g class="{cls}"><rect x="{x}" y="{y}" width="100" height="32" rx="6"/>'
                   f'<text x="{x+50}" y="{y+21}">{k}</text></g>')
    out.append('<text x="330" y="100" class="gap">air gap</text></svg>')
    return "".join(out)


CSS = """
:root{--ink:#1d262c;--ink2:#5a6670;--line:#c9d0d5;--bg:#f4f5f6;--deep:#1f5fb4;--wide:#d9651c;--ok:#2d7a4e;--bad:#b33a3a;--warn:#a97a00}
*{box-sizing:border-box}body{margin:0;font:15.5px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--bg)}
header{display:flex;gap:16px;align-items:center;padding:12px 24px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
header h1{font-size:17px;margin:0}header .pos{color:var(--ink2);font-size:14px}header nav{margin-left:auto;display:flex;gap:6px}
button{font:inherit;border:1px solid var(--line);background:#fff;border-radius:7px;padding:5px 12px;cursor:pointer}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}select{font:inherit;padding:4px}
main{display:grid;grid-template-columns:300px minmax(0,1fr);gap:28px;max-width:1180px;margin:24px auto;padding:0 24px}
.dia{width:100%;position:sticky;top:76px}.dia rect{fill:#fff;stroke:var(--line);stroke-width:1.4}.dia text{font:600 13px system-ui;text-anchor:middle;fill:var(--ink2)}
.dia .llm rect{stroke-dasharray:4 3}.dia .lit rect{fill:var(--ink);stroke:var(--ink)}.dia .lit text{fill:#fff}
.dia line{stroke:var(--line);stroke-width:2}.dia line.on{stroke:var(--ink);stroke-width:3}.dia .gap{font:500 11px system-ui;fill:var(--wide);transform:rotate(90deg);transform-origin:330px 100px}
.legend{font-size:12.5px;color:var(--ink2);margin-top:8px}
h2{font-size:24px;margin:0 0 10px}.what{background:#fff;border-left:4px solid var(--deep);padding:10px 16px;border-radius:0 8px 8px 0;margin-bottom:16px}
.lens{color:var(--ink2)}.small{font-size:13px;color:var(--ink2)}.big{font-size:22px;font-weight:600}
ul.checks{list-style:none;padding:0;margin:0 0 16px}ul.checks li{background:#fff;border:1px solid var(--line);border-radius:7px;padding:7px 12px;margin:5px 0;display:flex;gap:10px}
ul.checks span{font-weight:700}li.ok span{color:var(--ok)}li.bad span{color:var(--bad)}li.warn span{color:var(--warn)}
table{border-collapse:collapse;width:100%;background:#fff;font-size:14px;margin:4px 0 10px}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #e3e7ea;vertical-align:top}
th{font-size:13px;color:var(--ink2)}tr.kept td{background:#e3f2e8}tr.redundant td,tr.flat td{color:var(--ink2)}
.idea{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0}.idea p{margin:4px 0}.idea.kept{border-color:var(--ok)}
.lbl{display:inline-block;min-width:68px;font-size:12px;font-weight:700;color:var(--ink2);text-transform:uppercase}
details{background:#fff;border:1px solid var(--line);border-radius:7px;margin:6px 0}summary{cursor:pointer;padding:7px 12px;color:var(--ink2);font-size:14px}
pre{margin:0;padding:10px 14px;font:12.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;border-top:1px solid var(--line);max-height:480px;overflow:auto}
code{font:13px ui-monospace,Menlo,monospace;background:#e9edf0;padding:0 3px;border-radius:3px}
.step{display:none}.step.on{display:block}
@media(max-width:820px){main{grid-template-columns:1fr}.dia{position:static;max-width:340px}}
"""

JS = """
const steps=[...document.querySelectorAll('.step')],dias=[...document.querySelectorAll('.diahost')];let i=0;
const jump=document.getElementById('jump');
function show(k){i=Math.max(0,Math.min(steps.length-1,k));steps.forEach((s,j)=>s.classList.toggle('on',j===i));
dias.forEach((d,j)=>d.hidden=j!==i);document.getElementById('pos').textContent=`Step ${i+1} of ${steps.length}`;
jump.value=steps[i].dataset.gen;try{history.replaceState(null,'','#'+(i+1))}catch(e){}window.scrollTo(0,0)}
document.getElementById('prev').onclick=()=>show(i-1);document.getElementById('next').onclick=()=>show(i+1);
jump.onchange=()=>show(steps.findIndex(s=>s.dataset.gen===jump.value));
document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowRight')show(i+1);if(e.key==='ArrowLeft')show(i-1)});
let h=1;try{h=parseInt(location.hash.slice(1))||1}catch(e){}show(h-1);
"""


def to_html(t):
    steps = steps_for(t)
    gens = sorted({s["gen"] for s in steps if s["gen"] is not None})
    opts = "".join(f'<option value="{g}">Generation {g}</option>' for g in gens) + '<option value="end">Findings</option>'
    dias, body = [], []
    for s in steps:
        dias.append(f'<div class="diahost" hidden>{diagram(s["lit"])}</div>')
        body.append(f'<section class="step" data-gen="{s["gen"] if s["gen"] is not None else "end"}"><h2>{E(s["title"])}</h2>'
                    + (f'<div class="what">{s["what"]}</div>' if s["what"] else "")
                    + (f'<ul class="checks">{"".join(s["checks"])}</ul>' if s["checks"] else "")
                    + s["body"] + s["raw"] + "</section>")
    run = t["run"]
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Helix walkthrough {E(run['id'])}</title><style>{CSS}</style></head><body>"
            f"<header><h1>Helix run {E(run['id'])}: walkthrough</h1><span class='pos' id='pos'></span>"
            f"<nav><select id='jump'>{opts}</select><button id='prev'>← Back</button>"
            f"<button id='next' class='primary'>Next →</button></nav></header>"
            f"<main><aside>{''.join(dias)}<p class='legend'>Dashed boxes are LLMs; solid are code. "
            f"Dark = this step. Arrow keys move.</p></aside><div>{''.join(body)}</div></main>"
            f"<script>{JS}</script></body></html>")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    t = build_trace(Path(a.run))
    out = Path(a.out or Path(a.run) / "walkthrough.html")
    out.write_text(to_html(t))
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
