"""The presentation report for a Helix v4 job: one self-contained HTML page (no external files or libraries).

    python -m helix4.report runs/v4 results/v4        # reads every run folder in runs/v4, writes results/v4/report.html

Works on partial results (runs still going, or stopped by the deadline). Shows: the best score reached and how it
compares with the published records; best score by generation for each memory condition (each seed, and the
median); how the two loops contributed; the best construction and its autoconvolution; the chain of changes that
built the best program; and, for Atlas runs, the findings the memory recorded.
"""
from __future__ import annotations

import html
import json
import statistics
import sys
from pathlib import Path

import numpy as np

from helix4.problems import ac2

COND_ORDER = ["atlas", "journal", "control"]
COND_LABEL = {"atlas": "Atlas (structured memory)", "journal": "Journal (appended context)", "control": "Control (no memory)"}
REFS = [("2010 record", 0.88922), ("human best", 0.94136), ("AlphaEvolve", 0.9610), ("best known", 0.962643)]
CHART_REFS = REFS[:3]          # the last two are too close to label apart on the chart


def jl(path):
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


def load_run(d: Path):
    state = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else None
    if state is None:
        return None
    cfg = state["config"]
    hist = jl(d / "history.jsonl")
    progs = {p["id"]: p for p in jl(d / "programs.jsonl")}
    valid = [p for p in progs.values() if p.get("valid")]
    if not valid:
        return None
    best = max(valid, key=lambda p: p["score"])
    chain, p = [], best
    while p is not None:
        chain.append(p)
        p = progs.get(p.get("parent")) if p.get("parent") else None
    chain.reverse()
    best_curve, b = [], 0.0
    for h in hist:
        b = max(b, h["best"])
        best_curve.append([h["gen"], b])
    deep = [p for p in progs.values() if p["role"] == "deep"]
    wide = [p for p in progs.values() if p["role"] == "wide"]

    def rate(ps):
        return (sum(1 for p in ps if p.get("valid") and (p.get("delta") or 0) > 1e-9) / len(ps)) if ps else None

    # which loop set each new record
    records, top = {"deep": 0, "wide": 0}, -1.0
    for p in sorted(progs.values(), key=lambda p: (p["gen"], p["id"])):
        if p.get("valid") and p["score"] > top + 1e-12:
            if p["role"] in records and top >= 0:
                records[p["role"]] += 1
            top = p["score"]
    findings = []
    if cfg["condition"] == "atlas":
        evs = jl(d / "findings.jsonl")
        fs = {}
        for e in evs:
            if e["op"] == "new":
                fs[e["id"]] = dict(e)
            elif e["op"] == "evidence" and e["id"] in fs:
                fs[e["id"]]["evidence"] = fs[e["id"]]["evidence"] + [x for x in e["programs"] if x not in fs[e["id"]]["evidence"]]
        for f in fs.values():
            ds = [progs[x]["delta"] for x in f["evidence"] if x in progs and progs[x].get("valid") and progs[x].get("delta") is not None]
            f["best_gain"] = max(ds) if ds else None
            f["gains"] = sum(1 for x in ds if x > 1e-9)
        findings = sorted(fs.values(), key=lambda f: -(f["best_gain"] or -1))
    plans = jl(d / "plans.jsonl")
    refs = sum(len(e.get("builds_on") or []) for pl in plans for e in pl.get("experiments", []))
    exps = sum(len(pl.get("experiments", [])) for pl in plans)
    construction = None
    f = d / "constructions" / f"{best['id']}.npy"
    if not f.exists():
        f = d / "best.npy"
    if f.exists():
        h = np.load(f)
        h = h / h.max()
        g = ac2.autoconv(h)
        construction = {"n": int(len(h)), "h": downsample(h, 600), "ff": downsample(g / g.max(), 600)}
    return {"name": d.name, "condition": cfg["condition"], "seed": cfg["seed"], "gens_planned": cfg["gens"],
            "gens_done": state["gen_done"], "budget": cfg["budget"], "best": best["score"], "best_id": best["id"],
            "best_n": best.get("n"), "curve": best_curve, "programs": len(progs),
            "failed": sum(1 for p in progs.values() if not p.get("valid")), "deep_rate": rate(deep),
            "wide_rate": rate(wide), "records": records, "builds_on_per_exp": (refs / exps) if exps else None,
            "chain": [{"id": p["id"], "gen": p["gen"], "role": p["role"], "score": p["score"], "delta": p.get("delta"),
                       "intent": (p.get("intent") or "")[:220], "summary": (p.get("summary") or "")[:220]} for p in chain],
            "findings": [{"id": f["id"], "gen": f["gen"], "kind": f["kind"], "claim": f["claim"][:420],
                          "evidence": f["evidence"][:8], "best_gain": f["best_gain"], "gains": f["gains"],
                          "links": f.get("links", [])} for f in findings[:12]],
            "n_findings": len(findings), "construction": construction,
            "graph": [{"id": f["id"], "gen": f["gen"], "kind": f["kind"], "claim": f["claim"][:300],
                       "links": f.get("links", []), "n_ev": len(f["evidence"]), "gains": f["gains"],
                       "best_gain": f["best_gain"]} for f in sorted(findings, key=lambda f: int(f["id"][1:]))],
            "finished": (d / "summary.json").exists()}


def downsample(a, k):
    a = np.asarray(a, float)
    if len(a) <= k:
        return [round(float(x), 6) for x in a]
    return [round(float(c.max()), 6) for c in np.array_split(a, k)]     # bucket maxima keep narrow spikes visible


def esc(s):
    return html.escape(str(s if s is not None else ""))


def build(runs_dir: Path, out_dir: Path):
    runs = [r for r in (load_run(d) for d in sorted(runs_dir.iterdir()) if d.is_dir() and not d.name.startswith(".")) if r]
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
        bo = [r["builds_on_per_exp"] for r in rs if r["builds_on_per_exp"] is not None]
        rows.append(f"<tr><td><span class='key k-{c}'></span>{esc(COND_LABEL[c])}</td>"
                    f"<td class='num'>{', '.join(f'{b:.5f}' for b in bests)}</td>"
                    f"<td class='num'>{statistics.median(bests):.5f}</td><td class='num'>{max(bests):.5f}</td>"
                    f"<td class='num'>{(100 * statistics.mean(dr)) if dr else 0:.0f}%</td>"
                    f"<td class='num'>{(100 * statistics.mean(wr)) if wr else 0:.0f}%</td>"
                    f"<td class='num'>{sum(r['records']['deep'] for r in rs)} / {sum(r['records']['wide'] for r in rs)}</td>"
                    f"<td class='num'>{statistics.mean(bo) if bo else 0:.1f}</td>"
                    f"<td class='num'>{sum(r['failed'] for r in rs)}/{sum(r['programs'] for r in rs)}</td></tr>")
    status = (f"{sum(r['finished'] for r in runs)} of {len(runs)} runs finished; generations done: "
              + ", ".join(f"{r['name']} {r['gens_done']}" for r in runs)) if runs else "no runs yet"
    hero = ""
    if best:
        beaten = [n for n, v in REFS if best["best"] > v]
        hero = (f"<div class='hero'><div class='tile'><div class='label'>Best lower bound found</div>"
                f"<div class='value'>{best['best']:.6f}</div><div class='sub'>{esc(best['name'])}, program "
                f"{esc(best['best_id'])}, {best['best_n']} steps</div></div>"
                f"<div class='tile'><div class='label'>Starting point (Code Zero)</div><div class='value small'>0.666667</div>"
                f"<div class='sub'>a constant function</div></div>"
                f"<div class='tile'><div class='label'>Published records passed</div><div class='value small'>"
                f"{len(beaten)} of {len(REFS)}</div><div class='sub'>{esc(', '.join(beaten) or 'none yet')}</div></div></div>")
    page = TEMPLATE.replace("/*DATA*/", json.dumps(data).replace("</", "<\\/")).replace("<!--HERO-->", hero) \
        .replace("<!--ROWS-->", "\n".join(rows)).replace("<!--STATUS-->", esc(status))
    (out_dir / "report.html").write_text(page)
    (out_dir / "report_data.json").write_text(json.dumps(data, indent=1))
    return out_dir / "report.html"


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Helix v4 results</title>
<style>
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;
--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--c-atlas:#2a78d6;--c-journal:#eb6834;--c-control:#1baf7a;--single:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--c-atlas:#3987e5;--c-journal:#d95926;--c-control:#199e70;--single:#3987e5}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--c-atlas:#3987e5;--c-journal:#d95926;--c-control:#199e70;--single:#3987e5}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 16px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:34px 0 6px}
p.lead,.note{color:var(--ink2);margin:4px 0 14px}.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:16px;margin:12px 0}
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tile .label{color:var(--ink2);font-size:13px}.tile .value{font-size:44px;font-weight:600;line-height:1.15}.tile .value.small{font-size:30px}
.tile .sub{color:var(--muted);font-size:13px}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.scroll{overflow-x:auto}
.key{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:8px;vertical-align:middle}
.k-atlas{background:var(--c-atlas)}.k-journal{background:var(--c-journal)}.k-control{background:var(--c-control)}
.legend{display:flex;flex-wrap:wrap;gap:16px;color:var(--ink2);font-size:13px;margin:6px 0}
svg text{fill:var(--muted);font-size:11px}svg .reflabel{fill:var(--ink2)}#tip{position:fixed;pointer-events:none;background:var(--surface);
border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:5}
#tip{max-width:420px}#tip .v{font-weight:600;font-variant-numeric:tabular-nums}#tip .r{color:var(--ink2)}.chain li{margin:4px 0}.chain .d{font-variant-numeric:tabular-nums;font-weight:600}
.role{display:inline-block;font-size:11px;padding:0 6px;border-radius:4px;border:1px solid var(--ring);color:var(--ink2);margin-right:6px}
details summary{cursor:pointer;color:var(--ink2)}select{font:inherit;padding:4px 6px;border-radius:6px;border:1px solid var(--ring);background:var(--surface);color:var(--ink)}
.finding{margin:8px 0;padding-left:10px;border-left:2px solid var(--grid)}.finding .m{color:var(--muted);font-size:12px}
</style></head><body><main>
<h1>Helix v4: program evolution with memory</h1>
<p class="lead">Problem: the second autocorrelation inequality. Find a non-negative step function f maximising
‖f*f‖₂² / (‖f*f‖₁·‖f*f‖∞); every construction is a proven lower bound for the constant. Three memory conditions
(what the Researcher sees of the past) × several seeds, same models, budgets and evaluator. <span class="note"><!--STATUS--></span></p>
<!--HERO-->
<h2>Best score by generation</h2>
<p class="note">Thin lines: individual seeds. Thick lines: the median across seeds. Grey rules: published records (shown here only; the agents never see them).</p>
<div class="legend" id="legend"></div>
<div class="card"><div id="curve"></div></div>
<details><summary>Table view</summary><div class="scroll" id="curvetable"></div></details>
<h2>By condition</h2>
<div class="card scroll"><table><thead><tr><th>Condition</th><th class="num">Best per seed</th><th class="num">Median</th><th class="num">Max</th>
<th class="num">Deep gained</th><th class="num">Wide gained</th><th class="num">Records deep / wide</th>
<th class="num">Cited per plan</th><th class="num">Failed</th></tr></thead><tbody>
<!--ROWS-->
</tbody></table><p class="note">"Gained" = share of children that scored higher than the construction they started from. "Records" = new bests set by each loop. "Cited per plan" = earlier programs or findings each planned experiment says it builds on. Deep = planned by the Researcher (the only part whose memory differs); wide = the memoryless Mutator, identical in every condition.</p></div>
<h2>The best construction</h2>
<div class="legend"><label>Run <select id="runsel"></select></label></div>
<div class="card"><div id="steps"></div><div id="ffplot"></div></div>
<h2>How the best program was built</h2>
<p class="note">The chain of programs from Code Zero to the run's best, each change with its gain over its start.</p>
<div class="card"><ol class="chain" id="chain"></ol></div>
<div id="findwrap"><h2>What Atlas recorded</h2>
<p class="note">Findings written by the Distiller, each citing its evidence; the gains are measured by code, not claimed by the model. Top findings by measured gain.</p>
<p class="note">The findings graph: one dot per finding, placed by the generation that wrote it; lines are the links the Distiller drew between findings (refines, contradicts, requires, combines with, explains). Hover a dot for the claim.</p>
<div class="legend"><span><svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="var(--c-atlas)"/></svg> works</span>
<span><svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="var(--c-journal)"/></svg> fails</span>
<span><svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="var(--c-control)"/></svg> mechanism</span>
<span><svg width="12" height="12"><circle cx="6" cy="6" r="4" fill="none" stroke="var(--ink2)" stroke-width="2"/></svg> open question</span></div>
<div class="card"><div id="fgraph"></div></div>
<div class="card" id="findings"></div></div>
<div id="tip"></div>
<script>
const D = /*DATA*/;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e}
function txt(tag, s, parent, cls){const e=document.createElement(tag);e.textContent=s;if(cls)e.className=cls;if(parent)parent.appendChild(e);return e}
const tip=document.getElementById("tip");
function showTip(x,y,rows){tip.replaceChildren();rows.forEach(([v,label,color])=>{const d=txt("div","",tip);if(color){const k=document.createElement("span");k.className="key";k.style.background=color;d.appendChild(k)}
txt("span",v,d,"v");txt("span"," "+label,d,"r")});tip.style.display="block";const w=tip.offsetWidth;tip.style.left=Math.min(x+14,innerWidth-w-8)+"px";tip.style.top=(y+14)+"px"}
function hideTip(){tip.style.display="none"}
const conds=D.order.filter(c=>D.runs.some(r=>r.condition===c));
const leg=document.getElementById("legend");
conds.forEach(c=>{const s=document.createElement("span");const k=document.createElement("span");k.className="key k-"+c;s.appendChild(k);s.appendChild(document.createTextNode(D.labels[c]));leg.appendChild(s)});
function median(a){const s=[...a].sort((x,y)=>x-y),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2}
function curve(){
  const box=document.getElementById("curve");box.replaceChildren();
  const W=Math.max(320,box.clientWidth),H=Math.round(Math.min(440,Math.max(280,W*0.5))),L=52,R=W<560?16:150,T=12,B=34;
  const gmax=Math.max(1,...D.runs.map(r=>r.curve.length?r.curve[r.curve.length-1][0]:0));
  const vals=D.runs.flatMap(r=>r.curve.map(p=>p[1]));
  const ymin=Math.floor(Math.min(0.66,...vals)*50)/50,ymax=Math.max(0.97,Math.ceil(Math.max(...vals,0.9)*100)/100);
  const X=g=>L+(W-L-R)*g/gmax,Y=v=>T+(H-T-B)*(1-(v-ymin)/(ymax-ymin));
  const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":"best score by generation"},box);
  for(let v=Math.ceil(ymin*20)/20;v<=ymax+1e-9;v+=0.05){el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:css("--grid")},svg);el("text",{x:L-8,y:Y(v)+4,"text-anchor":"end"},svg).textContent=v.toFixed(2)}
  const step=gmax>12?Math.ceil(gmax/10):1;for(let g=0;g<=gmax;g+=step){el("text",{x:X(g),y:H-B+18,"text-anchor":"middle"},svg).textContent=g}
  el("text",{x:(L+W-R)/2,y:H-2,"text-anchor":"middle"},svg).textContent="generation";
  el("line",{x1:L,x2:W-R,y1:H-B,y2:H-B,stroke:css("--axis")},svg);
  D.refs.forEach(([n,v])=>{if(v<ymin||v>ymax)return;el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:css("--axis")},svg);
    if(R>100)el("text",{x:W-R+6,y:Y(v)+4,class:"reflabel"},svg).textContent=n+" "+v.toFixed(4)});
  const path=pts=>pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).join("");
  const med={};
  conds.forEach(c=>{const rs=D.runs.filter(r=>r.condition===c),col=css("--c-"+c);
    rs.forEach(r=>el("path",{d:path(r.curve),fill:"none",stroke:col,"stroke-width":1.2,"stroke-opacity":.45,"stroke-linejoin":"round"},svg));
    const m=[];for(let g=0;g<=gmax;g++){const v=rs.map(r=>r.curve.find(p=>p[0]===g)).filter(Boolean).map(p=>p[1]);if(v.length)m.push([g,median(v)])}
    med[c]=m;el("path",{d:path(m),fill:"none",stroke:col,"stroke-width":2.5,"stroke-linejoin":"round","stroke-linecap":"round"},svg);
    if(m.length){const p=m[m.length-1];el("circle",{cx:X(p[0]),cy:Y(p[1]),r:4,fill:col,stroke:css("--surface"),"stroke-width":2},svg)}});
  const cross=el("line",{y1:T,y2:H-B,stroke:css("--axis"),visibility:"hidden"},svg);
  const hit=el("rect",{x:L,y:T,width:W-L-R,height:H-T-B,fill:"transparent"},svg);
  hit.addEventListener("pointermove",e=>{const b=svg.getBoundingClientRect(),g=Math.max(0,Math.min(gmax,Math.round((e.clientX-b.left-L)/(W-L-R)*gmax)));
    cross.setAttribute("x1",X(g));cross.setAttribute("x2",X(g));cross.setAttribute("visibility","visible");
    const rows=[[`generation ${g}`,"",""]];conds.forEach(c=>{const p=med[c].find(q=>q[0]===g);if(p)rows.push([p[1].toFixed(6),D.labels[c]+" (median)",css("--c-"+c)])});
    D.runs.forEach(r=>{const p=r.curve.find(q=>q[0]===g);if(p)rows.push([p[1].toFixed(6),r.name,""])});showTip(e.clientX,e.clientY,rows)});
  hit.addEventListener("pointerleave",()=>{cross.setAttribute("visibility","hidden");hideTip()});
  const t=document.getElementById("curvetable");t.replaceChildren();const tb=document.createElement("table");t.appendChild(tb);
  const hr=tb.insertRow();txt("th","generation",hr);D.runs.forEach(r=>txt("th",r.name,hr,"num"));
  for(let g=0;g<=gmax;g++){const tr=tb.insertRow();txt("td",g,tr);D.runs.forEach(r=>{const p=r.curve.find(q=>q[0]===g);txt("td",p?p[1].toFixed(6):"",tr,"num")})}
}
function series(boxId,vals,label,stepped){
  const box=document.getElementById(boxId);box.replaceChildren();if(!vals||!vals.length)return;
  const W=Math.max(300,box.clientWidth),H=160,L=40,R=10,T=18,B=18,n=vals.length;
  const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":label},box);
  el("text",{x:L,y:12},svg).textContent=label;
  const X=i=>L+(W-L-R)*i/Math.max(1,n-1),Y=v=>T+(H-T-B)*(1-v);
  [0,0.5,1].forEach(v=>{el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:css("--grid")},svg);el("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},svg).textContent=v});
  let d="";vals.forEach((v,i)=>{d+=(i?"L":"M")+X(i).toFixed(1)+","+Y(v).toFixed(1)});
  el("path",{d:d+`L${X(n-1)},${Y(0)}L${X(0)},${Y(0)}Z`,fill:css("--single"),"fill-opacity":.10},svg);
  el("path",{d,fill:"none",stroke:css("--single"),"stroke-width":2,"stroke-linejoin":"round"},svg);
}
const sel=document.getElementById("runsel");
[...D.runs].sort((a,b)=>b.best-a.best).forEach(r=>{const o=document.createElement("option");o.value=r.name;o.textContent=`${r.name} (${r.best.toFixed(6)})`;sel.appendChild(o)});
function showRun(){
  const r=D.runs.find(x=>x.name===sel.value);if(!r)return;const c=r.construction;
  if(c){series("steps",c.h,`step heights h (N = ${c.n}, scaled to max 1)`);series("ffplot",c.ff,"its autoconvolution f*f (scaled to max 1): a flat top is what scores")}
  const ol=document.getElementById("chain");ol.replaceChildren();
  r.chain.forEach(p=>{const li=document.createElement("li");txt("span",p.role,li,"role");txt("span",p.id+" ",li);
    txt("span",p.delta==null?p.score.toFixed(6):(p.delta>=0?"+":"")+p.delta.toFixed(6),li,"d");txt("span",` → ${p.score.toFixed(6)}: ${p.intent||p.summary}`,li);ol.appendChild(li)});
  const fw=document.getElementById("findwrap"),fb=document.getElementById("findings");fb.replaceChildren();
  const fr=r.condition==="atlas"?r:D.runs.filter(x=>x.condition==="atlas").sort((a,b)=>b.best-a.best)[0];
  if(!fr||!fr.findings.length){fw.style.display="none";return}fw.style.display="";
  txt("p",`${fr.name}: ${fr.n_findings} findings recorded.`,fb,"note");fgraph(fr);
  fr.findings.forEach(f=>{const d=txt("div","",fb,"finding");txt("div",`${f.id} · ${f.kind}: ${f.claim}`,d);
    txt("div",`generation ${f.gen} · evidence ${f.evidence.join(", ")} · ${f.gains} gained`+(f.best_gain!=null?`, best ${f.best_gain>=0?"+":""}${f.best_gain.toFixed(6)}`:"")+(f.links.length?" · "+f.links.map(l=>l.type+" "+l.to).join(", "):""),d,"m")});
}
function fgraph(r){
  const box=document.getElementById("fgraph");box.replaceChildren();const G=r.graph||[];if(!G.length)return;
  const W=Math.max(320,box.clientWidth),gmax=Math.max(1,...G.map(f=>f.gen)),gmin=Math.min(...G.map(f=>f.gen));
  const per={};G.forEach(f=>{(per[f.gen]=per[f.gen]||[]).push(f)});const most=Math.max(...Object.values(per).map(a=>a.length));
  const H=Math.max(220,Math.min(520,most*26+50)),L=24,R=24,T=16,B=28,pos={};
  const X=g=>gmax===gmin?W/2:L+(W-L-R)*(g-gmin)/(gmax-gmin);
  Object.entries(per).forEach(([g,a])=>a.forEach((f,i)=>{pos[f.id]=[X(+g),T+(H-T-B)*(i+0.5)/a.length]}));
  const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":"findings graph"},box);
  for(let g=gmin;g<=gmax;g++){el("line",{x1:X(g),x2:X(g),y1:T,y2:H-B,stroke:css("--grid")},svg);
    if(gmax-gmin<=12||g%2===0)el("text",{x:X(g),y:H-8,"text-anchor":"middle"},svg).textContent="g"+g}
  G.forEach(f=>f.links.forEach(l=>{const a=pos[f.id],b=pos[l.to];if(!a||!b)return;const mx=(a[0]+b[0])/2,my=Math.min(a[1],b[1])-18;
    el("path",{d:`M${a[0]},${a[1]}Q${mx},${my} ${b[0]},${b[1]}`,fill:"none",stroke:css("--axis"),"stroke-width":1.2},svg)}));
  const col={works:css("--c-atlas"),fails:css("--c-journal"),mechanism:css("--c-control")};
  G.forEach(f=>{const [x,y]=pos[f.id];
    if(f.kind==="question")el("circle",{cx:x,cy:y,r:4.5,fill:css("--surface"),stroke:css("--ink2"),"stroke-width":2},svg);
    else el("circle",{cx:x,cy:y,r:5,fill:col[f.kind]||css("--ink2"),stroke:css("--surface"),"stroke-width":2},svg);
    const hit=el("circle",{cx:x,cy:y,r:12,fill:"transparent",tabindex:0},svg);
    const rows=()=>[[f.id+" · "+f.kind,`generation ${f.gen} · ${f.n_ev} evidence · ${f.gains} gained`+(f.best_gain!=null?` · best ${f.best_gain>=0?"+":""}${f.best_gain.toFixed(5)}`:""),""],
      [f.claim.length>200?f.claim.slice(0,200)+"…":f.claim,"",""]].concat(f.links.length?[[f.links.map(l=>l.type+" "+l.to).join(", "),"",""]]:[]);
    hit.addEventListener("pointermove",e=>showTip(e.clientX,e.clientY,rows()));hit.addEventListener("pointerleave",hideTip);
    hit.addEventListener("focus",()=>{const b=hit.getBoundingClientRect();showTip(b.right,b.top,rows())});hit.addEventListener("blur",hideTip)});
}
sel.addEventListener("change",showRun);
function all(){curve();showRun()}all();let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(all,150)});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",all);
</script></main></body></html>
"""


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/v4")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "results/v4")
    print(build(src, dst))
