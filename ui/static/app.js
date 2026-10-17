"use strict";
/* Helix dashboard. Plain JS, no build step. Routes: #/ (runs), #/run/<id>, #/suite, #/meta.
   Units: progress % (0 = Code Zero, 100 = the reference) and gains in progress points ("pts"). */

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\n/g, "<br>");
const fmt = (v, d = 1) => v == null || isNaN(v) ? "—" : Number(v).toFixed(d);
const pct = v => v == null ? "—" : `${fmt(v)}%`;
const api = (u, opt) => fetch(u, opt).then(r => r.json());
const SVG = "http://www.w3.org/2000/svg";

const state = { runs: [], run: null, runId: null, tab: "story", gen: null, timer: null, suite: null };

/* ------------------------------------------------------------------ run model */
function model(detail) {
  const ev = detail.events;
  const start = ev.find(e => e.type === "run_start") || {};
  const gens = ev.filter(e => e.type === "gen_end");
  const feats = {}, plans = {}, research = {}, diag = {}, sens = {}, trees = {}, accepts = {}, calls = [];
  for (const e of ev) {
    if (e.type === "feature_done") feats[e.feature.id] = e.feature;
    else if (e.type === "plan") plans[e.gen] = e.plan;
    else if (e.type === "research") research[e.gen] = e;
    else if (e.type === "diagnostics") diag[e.gen] = e;
    else if (e.type === "sensitivity") sens[e.gen] = e.rows;
    else if (e.type === "tree") trees[e.gen] = e.nodes;
    else if (["accept", "redundant", "retire", "combination", "refit"].includes(e.type)) (accepts[e.gen] = accepts[e.gen] || []).push(e);
    else if (e.type === "call") calls.push(e);
  }
  const fl = start.floors || {}, cz = (start.code_zero_families || {}).train || {};
  const fams = Object.keys(cz);
  const wasteCZ = fams.length ? fams.reduce((a, f) => a + cz[f] - (fl[f] || 0), 0) / fams.length : 1;
  const pts = d => d == null ? null : 100 * d / wasteCZ;          // gap reduction -> progress points
  const lastTree = trees[Math.max(-1, ...Object.keys(trees).map(Number))] || [];
  return { id: detail.id, start, gens, feats, plans, research, diag, sens, trees, lastTree, accepts, calls, pts,
           status: detail.status, champion: detail.champion, end: ev.find(e => e.type === "run_end") };
}

const verdictOf = f => {
  if (f.status === "kept") return ["kept", "kept"];
  if (f.status === "retired") return ["retired", "bad"];
  if (f.status === "duplicate") return [`duplicate of ${f.duplicate_of}`, "dup"];
  if (f.status === "inert" || f.status === "span") return [`certified ${f.status}`, "dup"];
  if (f.status === "invalid") return ["invalid", "bad"];
  if (f.status === "rejected") return ["rejected by the probe", "bad"];
  if (f.verdict === "redundant") return ["redundant", ""];
  if (f.d_valid != null) return [f.verdict === "gain" ? "gained, not kept" : f.verdict, f.verdict === "worse" ? "bad" : ""];
  return [f.status, ""];
};

function gainOf(m, f) {
  const d = f.d_valid != null ? f.d_valid : f.best_probe;
  if (d == null) return "";
  const p = m.pts(d);
  const cls = p > 0.05 ? "up" : p < -0.05 ? "down" : "";
  return `<span class="gain ${cls}">${p > 0 ? "+" : ""}${fmt(p)} pts</span><span class="small muted">${f.d_valid != null ? "on validation" : "best probe, train"}</span>`;
}

/* ------------------------------------------------------------------ rail */
function spark(curve, w = 240, h = 22) {
  if (!curve || curve.length < 2) return "";
  const mx = Math.max(10, ...curve);
  const pts = curve.map((v, i) => `${(i / (curve.length - 1)) * w},${h - 2 - (Math.max(0, v) / mx) * (h - 4)}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}

function runLabel(r) { return r.title || r.problem; }

function renderRail() {
  const ol = $("#runlist");
  ol.innerHTML = state.runs.slice(0, 40).map(r => `<li><a href="#/run/${encodeURIComponent(r.id)}" ${r.id === state.runId ? 'aria-current="true"' : ""}>
    <span class="rname">${r.state === "running" ? '<span class="live" title="running"></span>' : ""}${esc(r.problem)}${r.label ? ` <span class="muted">${esc(r.label)}</span>` : ""}</span>
    <span class="rprog">${pct(r.progress)}</span>
    <span class="rmeta">${r.generations}${r.target ? "/" + r.target : ""} generations · ${r.kept} kept</span>
    ${spark(r.curve)}</a></li>`).join("") || `<li class="muted small">No runs yet.</li>`;
}

async function refreshRuns() {
  try { state.runs = await api("/api/runs"); } catch (e) { return; }
  renderRail();
  if (location.hash === "" || location.hash === "#/") renderHome();
}

/* ------------------------------------------------------------------ home */
function renderHome() {
  const main = $("#main");
  const runs = state.runs;
  main.innerHTML = `<h1>Helix</h1>
    <p class="intro">An evolutionary search with two loops: a Researcher that goes deep and a Mutator that goes wide, steered by a Navigator over a map of approaches. Each run starts from Code Zero (0%) and climbs toward the problem's reference (100%).</p>
    <h2>Runs</h2>
    ${runs.length ? `<ul class="runrows">${runs.map(r => `<li><a href="#/run/${encodeURIComponent(r.id)}">
      <span><span class="rt">${r.state === "running" ? '<span class="live"></span>' : ""}${esc(runLabel(r))}</span><br>
      <span class="muted small">${esc(r.label || "unlabelled")} · ${r.generations}${r.target ? " of " + r.target : ""} generations · ${r.kept} features kept · ${r.calls ?? 0} model calls${r.state === "running" && r.phase ? " · now: " + esc(r.phase) : ""}</span></span>
      ${spark(r.curve, 220, 40)}<span class="rp">${pct(r.progress)}</span></a></li>`).join("")}</ul>`
      : `<p class="empty">No runs yet. Start one with the button on the left, or from a terminal: <code>python -m helix3.run binpack2d -g 5</code>.</p>`}`;
}

/* ------------------------------------------------------------------ run view */
async function loadRun(id, keep) {
  const detail = await api(`/api/run?id=${encodeURIComponent(id)}`);
  const m = model(detail);
  const first = state.runId !== id;
  state.run = m; state.runId = id;
  if (first) { state.tab = "story"; state.gen = null; }
  if (state.gen == null || (!keep && first)) state.gen = Math.max(1, m.gens.length - 1);
  renderRun();
  renderRail();
}

function renderRun() {
  const m = state.run, main = $("#main");
  const last = m.gens[m.gens.length - 1] || {};
  const running = m.status && m.status.state === "running";
  const kept = Object.values(m.feats).filter(f => f.status === "kept").length;
  const tried = Object.values(m.feats).length;
  const test = m.end && m.end.test && m.end.test.progress;
  main.innerHTML = `
    <header class="runhead">
      <div><h1>${esc(m.start.title || m.start.problem)}</h1>
        <p class="sub">${esc(m.start.label || "")} ${running ? `<span class="state"><span class="live"></span>generation ${m.status.gen}: ${esc(m.status.note || m.status.phase)}</span>` : `<span class="state">finished</span>`}</p></div>
      <div class="big"><b>${pct(last.progress)}</b><span>of the way from Code Zero to the reference</span></div>
    </header>
    <ul class="facts">
      <li><b>${pct(last.valid_progress)}</b>on validation</li>
      ${test != null ? `<li><b>${pct(test)}</b>on the held-out test</li>` : ""}
      <li><b>${fmt(last.train, 2)}%</b>gap to the reference (Code Zero ${fmt((m.start.code_zero || {}).train, 2)}%)</li>
      <li><b>${kept}</b>features kept of ${tried}</li>
      <li><b>${last.calls ?? 0}</b>model calls</li>
      <li><b>${fmt((m.gens.reduce((a, g) => a + (g.seconds || 0), 0)) / 60, 1)}</b>minutes</li>
    </ul>
    <section class="hero" aria-label="Progress by generation"><div id="chart"></div>
      <div class="legend"><span><i style="background:var(--ink)"></i>train</span><span><i style="background:var(--ink-3)"></i>validation</span>
      <span><i style="background:var(--deep)"></i>kept from the deep loop</span><span><i style="background:var(--wide)"></i>kept from the wide loop</span></div></section>
    <div class="tabs" role="tablist">${[["story", "Generations"], ["tree", "Approaches"], ["features", "Every feature"], ["policy", "The policy"], ["calls", "Model calls"]]
      .map(([k, l]) => `<button role="tab" data-tab="${k}" aria-selected="${state.tab === k}">${l}</button>`).join("")}</div>
    <section id="tabbody"></section>`;
  drawChart(m);
  main.querySelectorAll(".tabs button").forEach(b => b.onclick = () => { state.tab = b.dataset.tab; renderRun(); });
  ({ story: renderStory, tree: renderTree, features: renderFeatures, policy: renderPolicy, calls: renderCalls })[state.tab](m);
}

function drawChart(m) {
  const box = $("#chart");
  const W = 1000, H = 280, L = 44, R = 16, T = 14, B = 30;
  const n = Math.max(1, m.gens.length - 1);
  const target = (m.start.config && m.start.config.generations) || n;
  const N = Math.max(n, target || n);
  const vals = m.gens.map(g => g.progress || 0), vv = m.gens.map(g => g.valid_progress ?? null);
  const top = Math.max(10, Math.ceil(Math.max(...vals, ...vv.filter(v => v != null)) / 10) * 10);
  const x = i => L + (W - L - R) * (i / N), y = v => T + (H - T - B) * (1 - Math.max(0, v) / top);
  const s = document.createElementNS(SVG, "svg");
  s.setAttribute("viewBox", `0 0 ${W} ${H}`); s.setAttribute("role", "img");
  s.setAttribute("aria-label", `Progress over ${n} generations, now ${fmt(vals[vals.length - 1])}%`);
  let h = `<g class="axis">`;
  for (let v = 0; v <= top; v += top > 40 ? 20 : 10) h += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`;
  for (let i = 0; i <= N; i++) h += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${i === 0 ? "Code Zero" : "G" + i}</text>`;
  h += `</g>`;
  h += `<polyline class="curve valid" points="${vv.map((v, i) => v == null ? null : `${x(i)},${y(v)}`).filter(Boolean).join(" ")}"/>`;
  h += `<polyline class="curve" points="${vals.map((v, i) => `${x(i)},${y(v)}`).join(" ")}"/>`;
  m.gens.forEach((g, i) => {
    const kept = (g.accepted || []).map(id => m.feats[id]).filter(Boolean);
    kept.forEach((f, j) => {
      h += `<circle class="bead ${f.origin}" cx="${x(i)}" cy="${y(vals[i]) - 14 - j * 15}" r="6.5" data-f="${f.id}"><title>${esc(f.name)} (${f.origin})</title></circle>`;
    });
    if (!kept.length) h += `<circle cx="${x(i)}" cy="${y(vals[i])}" r="3" fill="var(--ink)"/>`;
  });
  s.innerHTML = h;
  box.innerHTML = ""; box.appendChild(s);
  s.querySelectorAll(".bead").forEach(c => c.onclick = () => openFeature(c.dataset.f));
}

/* ------------------------------------------------------------------ the generation story */
function genSummary(m, g) {
  const ge = m.gens.find(e => e.gen === g) || {};
  const fs = (ge.features || []).map(id => m.feats[id]).filter(Boolean);
  const prev = m.gens.find(e => e.gen === g - 1) || {};
  const kept = fs.filter(f => f.status === "kept");
  const dup = fs.filter(f => ["duplicate", "inert", "span"].includes(f.status)).length;
  const preds = fs.filter(f => f.prediction && f.prediction.checked);
  const held = preds.filter(f => f.prediction.held).length;
  const dp = (ge.progress || 0) - (prev.progress || 0);
  let s = kept.length ? `Kept ${kept.map(f => `<b>${esc(f.name)}</b> (${f.origin})`).join(" and ")}: progress ${pct(prev.progress)} → <b>${pct(ge.progress)}</b> (${dp >= 0 ? "+" : ""}${fmt(dp)} pts).`
    : `Nothing kept; progress stays at ${pct(ge.progress)}.`;
  s += ` ${fs.length} features written (${fs.filter(f => f.origin === "deep").length} deep, ${fs.filter(f => f.origin === "wide").length} wide)`;
  if (dup) s += `, ${dup} discarded as repeats`;
  if (preds.length) s += `; ${held} of ${preds.length} predictions held`;
  return s + ".";
}

function renderStory(m) {
  const body = $("#tabbody");
  const gens = m.gens.filter(g => g.gen > 0);
  if (!gens.length) { body.innerHTML = `<p class="empty">Generation 1 is under way.</p>`; return; }
  const g = Math.min(state.gen, gens[gens.length - 1].gen);
  const ge = m.gens.find(e => e.gen === g);
  const plan = m.plans[g] || {}, res = m.research[g] || {}, dg = m.diag[g] || {}, se = m.sens[g] || [];
  const fs = (ge.features || []).map(id => m.feats[id]).filter(Boolean);
  const deep = fs.filter(f => f.origin === "deep"), wide = fs.filter(f => f.origin === "wide");
  const tree = m.trees[g] || m.lastTree;
  const title = id => { const n = tree.find(n => n.id === id); return n ? n.title : id; };
  body.innerHTML = `
    <div class="gens" role="group" aria-label="Generation">${gens.map(e => `<button aria-pressed="${e.gen === g}" data-g="${e.gen}"><b>G${e.gen}</b><span>${pct(e.progress)}</span></button>`).join("")}</div>
    <p class="gensum">${genSummary(m, g)}</p>
    <div class="timeline">
      <div class="step"><h3>Inspect</h3>
        <p class="lead">The champion's solutions next to the reference, on one instance per family. Code, no model.</p>
        ${diagTable(dg)}
        ${se.length ? `<h3>Sensitivity: each kept feature knocked out, halved, doubled, quadrupled</h3>${sensTable(m, se)}` : ""}</div>
      <div class="step"><h3>Navigator's plan</h3>
        <p class="lead">${plan.source === "navigator" ? "The Navigator read the approach tree and the ledger and decided where the effort goes." : "Rule-based plan (the Navigator was off or failed)."}</p>
        ${plan.note ? `<div class="note">${md(plan.note)}</div>` : ""}
        <table class="t"><tr><th>Researcher works on</th><th>Mode</th><th>Why</th></tr>
        ${(plan.research || []).map(r => `<tr><td>${esc(r.approach)} ${esc(title(r.approach))}</td><td>${esc(r.mode)}</td><td class="muted">${esc(r.why)}</td></tr>`).join("")}</table>
        <p class="small muted">Mutator: ${(plan.mutate && plan.mutate.vary || []).length ? "vary " + plan.mutate.vary.map(v => `<b>${esc((m.feats[v] || {}).name || v)}</b>`).join(", ") + ", plus " : ""}${(plan.mutate || {}).fresh || 0} fresh. ${(plan.combine || []).length ? "Retry together: " + plan.combine.map(p => p.join(" + ")).join("; ") + "." : ""} ${(plan.prune || []).length ? "Asked to prune: " + plan.prune.join(", ") + "." : ""}${(plan.dropped || []).length ? " Combinations that couldn't run: " + plan.dropped.map(d => `${d.pair.join(" + ")} (${esc(d.why)})`).join("; ") + "." : ""}</p></div>
      <div class="step deep"><h3>Deep loop: the Researcher's experiments</h3>
        ${res.analysis ? `<div class="note deep">${md(res.analysis)}</div>` : ""}
        ${deep.map(f => expRow(m, f, title)).join("") || `<p class="muted">No experiments.</p>`}</div>
      <div class="step wide"><h3>Wide loop: the Mutator's variations</h3>
        <p class="lead">Code and scores only, no hypotheses. Each variation is checked for repeats before anyone spends time on it.</p>
        ${wide.map(f => expRow(m, f, title)).join("") || `<p class="muted">No variations.</p>`}</div>
      <div class="step fit"><h3>Fit and accept</h3>
        <p class="lead">Each feature is probed alone on top of the champion, survivors are refitted with and without it, and the ones that help on validation are combined.</p>
        ${acceptLines(m, g)}</div>
    </div>`;
  body.querySelectorAll(".gens button").forEach(b => b.onclick = () => { state.gen = +b.dataset.g; renderStory(m); });
  body.querySelectorAll("[data-f]").forEach(b => b.onclick = () => openFeature(b.dataset.f));
}

function diagTable(dg) {
  const ch = dg.champion || {}, ref = dg.reference || {};
  const ids = Object.keys(ch);
  if (!ids.length) return "";
  const keys = [...new Set(ids.flatMap(i => Object.keys(ch[i]).filter(k => !k.startsWith("_") && k !== "error")))].slice(0, 7);
  return `<div style="overflow-x:auto"><table class="t"><tr><th>Instance</th>${keys.map(k => `<th>${esc(k.replace(/_/g, " "))}</th>`).join("")}</tr>
    ${ids.map(i => `<tr><td>${esc(i)}</td>${keys.map(k => `<td>${fmt(ch[i][k], 2)}${ref[i] && ref[i][k] != null ? ` <span class="muted small">ref ${fmt(ref[i][k], 2)}</span>` : ""}</td>`).join("")}</tr>`).join("")}</table></div>`;
}

function sensTable(m, rows) {
  const mults = Object.keys(rows[0].deltas);
  return `<table class="t"><tr><th>Feature</th>${mults.map(x => `<th>×${x}</th>`).join("")}</tr>${rows.map(r => `<tr><td><button class="chip" data-f="${r.feature}">${esc(r.name)}</button></td>${mults.map(x => { const p = m.pts(r.deltas[x]); return `<td class="${p > 0.05 ? "gain up" : ""}" style="font-size:.92rem">${p == null ? "—" : p < -100 ? "collapses" : (p > 0 ? "+" : "") + fmt(p) + " pts"}</td>`; }).join("")}</tr>`).join("")}</table>
    <p class="small muted">A gain from amplifying means the policy under-uses that direction; a big loss from knocking it out means it relies on it.</p>`;
}

function expRow(m, f, title) {
  const [v, cls] = verdictOf(f);
  const p = f.prediction || {};
  const idea = f.idea || {};
  const pred = p.metric ? `<div class="pred">Predicted <b>${esc(p.metric)}</b> ${esc(p.direction)} in ${esc(p.family)}: ${p.checked ? `${fmt(p.before, 2)} → ${fmt(p.after, 2)}, <span class="${p.held ? "ok" : "no"}">${p.held ? "held" : "did not hold"}</span>` : esc(p.why || "not checked")}</div>` : "";
  const why = f.origin === "deep" ? (idea.hypothesis || "") : (f.kind === "variant" ? `Variant of ${esc((m.feats[f.parent] || {}).name || f.parent)}. ` : "Fresh. ") + (f.measures || "");
  const lesson = f.origin === "deep" && idea.lesson ? `<div class="why"><b>Lesson it builds on:</b> ${md(idea.lesson)}</div>` : "";
  return `<div class="exp"><div class="title"><button data-f="${f.id}">${esc(f.name || f.id)}</button>${f.kind ? `<span class="kind">${esc(f.kind)}</span>` : ""}
      <span class="small muted"> · ${esc(f.node)} ${esc(title(f.node))}</span></div>
    <div class="why">${md(why)}${f.origin === "deep" && f.measures ? `<br><span class="small">Code computes: ${esc(f.measures)}</span>` : ""}</div>
    ${lesson}${pred ? `<div class="why">${pred}</div>` : ""}
    <div class="res"><span class="verdict ${cls}">${esc(v)}</span>${gainOf(m, f)}</div></div>`;
}

function acceptLines(m, g) {
  const ev = m.accepts[g] || [];
  const ge = m.gens.find(e => e.gen === g) || {};
  const fs = (ge.features || []).map(id => m.feats[id]).filter(Boolean).filter(f => f.probe && f.probe.length);
  fs.sort((a, b) => (b.d_valid ?? b.best_probe ?? -9) - (a.d_valid ?? a.best_probe ?? -9));
  const lines = ev.map(e => {
    if (e.type === "refit") return `Champion's own weights refitted${e.improved ? " (that alone helped)" : ""}.`;
    if (e.type === "accept") return `<b>Kept</b> ${e.features.map(i => esc((m.feats[i] || {}).name || i)).join(" + ")}.`;
    if (e.type === "redundant") return `${e.features.map(i => esc((m.feats[i] || {}).name || i)).join(" + ")} helped alone but added nothing next to what was kept.`;
    if (e.type === "retire") return `Retired ${esc((m.feats[e.feature] || {}).name || e.feature)}: the policy is better without it.`;
    if (e.type === "combination") return `Tried ${e.pair.map(i => esc((m.feats[i] || {}).name || i)).join(" + ")} together: ${e.d_valid != null ? fmt(m.pts(e.d_valid)) + " pts on validation" : "failed"}.`;
    return "";
  }).filter(Boolean);
  return `${fs.length ? `<table class="t"><tr><th>Feature</th><th>Loop</th><th>Best probe</th><th>Validation</th><th>Verdict</th></tr>
    ${fs.map(f => `<tr class="click" data-f="${f.id}"><td>${esc(f.name)}</td><td><span class="dot ${f.origin}"></span>${f.origin}</td><td>${f.best_probe != null ? fmt(m.pts(f.best_probe)) + " pts" : "—"}</td><td>${f.d_valid != null ? fmt(m.pts(f.d_valid)) + " pts" : "—"}</td><td>${esc(verdictOf(f)[0])}</td></tr>`).join("")}</table>` : ""}
    <ul>${lines.map(l => `<li>${l}</li>`).join("")}</ul>`;
}

/* ------------------------------------------------------------------ approaches */
function renderTree(m) {
  const nodes = m.lastTree;
  const body = $("#tabbody");
  if (!nodes.length) { body.innerHTML = `<p class="empty">The approach tree appears after the first generation.</p>`; return; }
  const kids = {};
  nodes.forEach(n => (kids[n.parent || ""] = kids[n.parent || ""] || []).push(n));
  const order = { promising: 0, unproven: 1, untried: 2, pruned: 3 };
  const li = n => {
    const fs = (n.features || []).map(i => m.feats[i]).filter(Boolean);
    const sub = (kids[n.id] || []).sort((a, b) => order[a.state] - order[b.state]);
    return `<li><div class="node"><span class="st ${n.state}">${n.state}</span>
      <div><div class="nt">${esc(n.title)} <span class="muted small">${n.id} · ${n.origin === "wide" ? "found by the Mutator" : n.origin === "researcher" ? "opened by the Researcher" : "brainstormed by the Navigator"} in G${n.created_gen}</span></div>
      <div class="nd">${esc(n.description)}</div>
      <div class="chips">${fs.map(f => `<button class="chip ${f.origin} ${f.status}" data-f="${f.id}">${esc(f.name)}</button>`).join("")}</div>
      ${n.certificate && n.certificate.length ? `<div class="small muted">Pruned by certificate: ${n.certificate.map(c => `${c.feature} ${c.type}${c.of ? " of " + c.of : ""}`).join(", ")}</div>` : ""}</div>
      <div class="nb">${n.best_gain != null ? `<b>${m.pts(n.best_gain) > 0 ? "+" : ""}${fmt(m.pts(n.best_gain))} pts</b><br>` : ""}<span class="small muted">${fs.length} tried</span></div></div>
      ${sub.length ? `<ul>${sub.map(li).join("")}</ul>` : ""}</li>`;
  };
  const counts = Object.entries(nodes.reduce((a, n) => (a[n.state] = (a[n.state] || 0) + 1, a), {})).map(([k, v]) => `${v} ${k}`).join(", ");
  body.innerHTML = `<p class="gensum">The map of ways to improve the policy: ${counts}. Effort follows evidence; only a verified certificate prunes.</p>
    <ul class="tree">${(kids[""] || []).sort((a, b) => order[a.state] - order[b.state]).map(li).join("")}</ul>`;
  body.querySelectorAll("[data-f]").forEach(b => b.onclick = () => openFeature(b.dataset.f));
}

/* ------------------------------------------------------------------ all features, policy, calls */
function renderFeatures(m) {
  const fs = Object.values(m.feats).sort((a, b) => a.id.localeCompare(b.id));
  $("#tabbody").innerHTML = `<div style="overflow-x:auto"><table class="t" style="margin-top:20px"><tr><th>Feature</th><th>Gen</th><th>Loop</th><th>Approach</th><th>Best probe</th><th>Validation</th><th>Prediction</th><th>Verdict</th></tr>
    ${fs.map(f => `<tr class="click" data-f="${f.id}"><td><b>${esc(f.name)}</b> <span class="muted small">${f.id}</span></td><td>${f.gen}</td><td><span class="dot ${f.origin}"></span>${f.origin}${f.kind ? " · " + f.kind : ""}</td><td>${esc(f.node)}</td>
      <td>${f.best_probe != null ? fmt(m.pts(f.best_probe)) : "—"}</td><td>${f.d_valid != null ? fmt(m.pts(f.d_valid)) : "—"}</td>
      <td>${f.prediction && f.prediction.checked ? (f.prediction.held ? "held" : "missed") : "—"}</td><td>${esc(verdictOf(f)[0])}</td></tr>`).join("")}</table></div>
    <p class="small muted">Gains are progress points (pts): how much closer to the reference the policy got with the feature.</p>`;
  $("#tabbody").querySelectorAll("[data-f]").forEach(b => b.onclick = () => openFeature(b.dataset.f));
}

function renderPolicy(m) {
  $("#tabbody").innerHTML = `<p class="gensum">The champion written out as an ordinary program: the kept features and their weights.</p><pre class="code">${esc(m.champion || "")}</pre>`;
}

function renderCalls(m) {
  $("#tabbody").innerHTML = `<div style="overflow-x:auto"><table class="t" style="margin-top:20px"><tr><th>Call</th><th>Gen</th><th>Role</th><th>Step</th><th>Feature</th><th>Thinking</th><th>Time</th><th>Tokens in / out</th></tr>
    ${m.calls.map(c => `<tr class="click" data-c="${c.id}"><td>${c.id}</td><td>${c.gen}</td><td>${esc(c.role)}</td><td>${esc(c.step || "")}</td><td>${esc((m.feats[c.feature] || {}).name || "")}</td><td>${esc(c.effort)}${c.reasoning_tokens ? ` (${c.reasoning_tokens})` : ""}</td><td>${fmt(c.seconds)} s</td><td>${c.tokens_in} / ${c.tokens_out}</td></tr>`).join("")}</table></div>`;
  $("#tabbody").querySelectorAll("[data-c]").forEach(r => r.onclick = () => openCall(r.dataset.c));
}

/* ------------------------------------------------------------------ drawer */
function drawer(html) {
  $("#drawerBody").innerHTML = html;
  $("#drawer").hidden = false;
  $(".drawer-panel .close").focus();
}
document.addEventListener("click", e => { if (e.target.closest("[data-close]")) $("#drawer").hidden = true; });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#drawer").hidden = true; });

function probeSvg(m, f) {
  if (!f.probe || !f.probe.length) return "";
  const W = 520, H = 110, b = (W - 40) / f.probe.length;
  const vals = f.probe.map(p => m.pts(p[1]));
  const mx = Math.max(1, ...vals.map(v => Math.min(Math.abs(v), 30)));
  const y0 = H / 2;
  return `<svg class="probe" viewBox="0 0 ${W} ${H}" role="img" aria-label="Probe results by weight"><line x1="30" x2="${W}" y1="${y0}" y2="${y0}" stroke="var(--rule)"/>
    ${f.probe.map((p, i) => { const v = vals[i], hgt = Math.min(Math.abs(v), 30) / mx * (H / 2 - 16); return `<rect x="${36 + i * b}" y="${v >= 0 ? y0 - hgt : y0}" width="${b - 14}" height="${Math.max(1.5, hgt)}" fill="${v >= 0 ? "var(--kept)" : "var(--bad)"}"/>
      <text x="${36 + i * b + (b - 14) / 2}" y="${H - 2}" text-anchor="middle" font-size="11" fill="var(--ink-2)">w ${p[0]}</text><text x="${36 + i * b + (b - 14) / 2}" y="${v >= 0 ? y0 - hgt - 4 : y0 + hgt + 12}" text-anchor="middle" font-size="11" fill="var(--ink)">${v > 0 ? "+" : ""}${fmt(v)}</text>`; }).join("")}</svg>`;
}

function openFeature(id) {
  const m = state.run, f = m.feats[id];
  if (!f) return;
  const [v, cls] = verdictOf(f);
  const idea = f.idea || {}, p = f.prediction || {};
  const node = m.lastTree.find(n => n.id === f.node);
  drawer(`<h2 id="drawerTitle">${esc(f.name)}</h2>
    <p><span class="verdict ${cls}">${esc(v)}</span> <span class="muted">${f.id} · generation ${f.gen} · <span class="dot ${f.origin}"></span>${f.origin} loop${f.kind ? ", " + esc(f.kind) : ""}${node ? " · approach " + esc(node.title) : ""}</span></p>
    <dl class="kv">
      ${idea.hypothesis ? `<dt>Hypothesis</dt><dd>${md(idea.hypothesis)}</dd><dt>Asked to measure</dt><dd>${md(idea.feature)}</dd>` : ""}
      ${f.parent ? `<dt>Varied</dt><dd><button class="chip" data-f="${f.parent}">${esc((m.feats[f.parent] || {}).name || f.parent)}</button></dd>` : ""}
      <dt>Code computes</dt><dd>${esc(f.measures)}</dd>
      ${f.coder_note ? `<dt>Coder's note</dt><dd>${esc(f.coder_note)}</dd>` : ""}
      ${p.metric ? `<dt>Prediction</dt><dd><b>${esc(p.metric)}</b> ${esc(p.direction)} in ${esc(p.family)}${p.checked ? `: ${fmt(p.before, 3)} → ${fmt(p.after, 3)}, <b>${p.held ? "held" : "did not hold"}</b>` : " (not checked)"}</dd>` : ""}
      ${f.d_valid != null ? `<dt>Trial</dt><dd>${fmt(m.pts(f.d_train))} pts on train, <b>${fmt(m.pts(f.d_valid))} pts</b> on validation (with vs without, refitted)</dd>` : ""}
      ${f.certificate && f.certificate.type ? `<dt>Certificate</dt><dd>${esc(f.certificate.type)}${f.certificate.of ? " of " + esc(f.certificate.of) : ""}${f.certificate.rho ? ` (ρ = ${f.certificate.rho})` : ""}${f.certificate.r2 ? ` (R² = ${f.certificate.r2})` : ""}</dd>` : (f.certificate && f.certificate.nearest ? `<dt>Nearest</dt><dd>${esc(f.certificate.nearest)} (ρ = ${f.certificate.rho})</dd>` : "")}
      ${f.error ? `<dt>Error</dt><dd>${esc(f.error)}</dd>` : ""}
    </dl>
    ${f.probe && f.probe.length ? `<h3>Probe: alone on top of the champion, at four weights</h3>${probeSvg(m, f)}` : ""}
    <h3>Code</h3><pre class="code">${esc(f.code)}</pre>
    ${(f.calls || []).length ? `<h3>Model calls</h3><div class="chips">${f.calls.map(c => `<button class="chip" data-c="${c}">${c}</button>`).join("")}</div>` : ""}`);
  $("#drawerBody").querySelectorAll("[data-f]").forEach(b => b.onclick = () => openFeature(b.dataset.f));
  $("#drawerBody").querySelectorAll("[data-c]").forEach(b => b.onclick = () => openCall(b.dataset.c));
}

async function openCall(cid) {
  const c = await api(`/api/call?id=${encodeURIComponent(state.runId)}&call=${cid}`);
  const parts = [["reply", "Reply"], ["user", "What it was sent"], ["reasoning", "Hidden thinking"], ["system", "System prompt"]];
  drawer(`<h2 id="drawerTitle">${esc(c.role)} · ${esc(c.id)}</h2>
    <p class="muted">Generation ${c.gen} · ${esc(c.step || "")} · ${fmt(c.seconds)} s · ${c.tokens_in} tokens in, ${c.tokens_out} out · thinking ${esc(c.effort)}${c.reasoning_tokens ? ` (${c.reasoning_tokens} tokens)` : ""}</p>
    <div class="seg" role="group">${parts.map(([k, l], i) => `<button data-k="${k}" aria-pressed="${i === 0}">${l}</button>`).join("")}</div>
    <pre class="text" id="callText"></pre>`);
  const show = k => { $("#callText").textContent = c[k] || (k === "reasoning" ? "No hidden thinking (thinking was off for this call)." : ""); };
  show("reply");
  $("#drawerBody").querySelectorAll(".seg button").forEach(b => b.onclick = () => {
    $("#drawerBody").querySelectorAll(".seg button").forEach(x => x.setAttribute("aria-pressed", x === b)); show(b.dataset.k); });
}

/* ------------------------------------------------------------------ suite and meta */
async function renderSuite() {
  const main = $("#main");
  main.innerHTML = `<h1>Problems</h1><p class="intro">The verifiable problems Helix is tested on. In every one a solution is built decision by decision, and the evolved policy scores the candidates of each decision. Code Zero always takes the first candidate.</p><div id="plist"><p class="muted">Loading…</p></div>`;
  if (!state.suite) state.suite = await api("/api/suite");
  $("#plist").innerHTML = state.suite.map(p => p.error ? `<div class="problem"><h3>${esc(p.name)}</h3><p class="muted">Not available: ${esc(p.error)}</p></div>` :
    `<div class="problem"><div><h3>${esc(p.title)}</h3><p class="small muted"><code>${esc(p.name)}</code><br>${p.instances.train} train · ${p.instances.valid} validation · ${p.instances.test} test instances</p>
      <button class="ghost" data-run="${esc(p.name)}">Start a run</button></div>
      <div><div class="desc">${md(p.description)}</div><p class="small"><b>Families:</b> ${p.families.map(esc).join(", ")}${p.held_out.length ? ` · held out on test: ${p.held_out.map(esc).join(", ")}` : ""}</p>
      <p class="small"><b>Feature:</b> <code>${esc(p.signature)}</code></p></div></div>`).join("");
  main.querySelectorAll("[data-run]").forEach(b => b.onclick = () => openNewRun(b.dataset.run));
}

async function renderMeta() {
  const main = $("#main");
  main.innerHTML = `<h1>Meta loop</h1><p class="intro">The same kind of evolutionary search, one level up: its candidates are strategies (how Helix searches), scored by running Helix with them on several problems. When a strategy wins, it replaces the one the meta loop itself runs on.</p><div id="mlist"><p class="muted">Loading…</p></div>`;
  const items = await api("/api/meta");
  if (!items.length) { $("#mlist").innerHTML = `<p class="empty">No meta runs yet. Evaluate a strategy with <code>python -m meta.evaluate</code>, or run the loop with <code>python -m meta.outer</code>.</p>`; return; }
  $("#mlist").innerHTML = items.map(it => it.kind === "evaluation" ? metaEval(it) : metaOuter(it)).join("");
}

function metaEval(it) {
  const r = it.result;
  return `<h2>Evaluation <span class="muted small">${esc(it.id)}</span></h2><p>Score <b>${fmt(r.score)}</b> over ${Object.keys(r.problems).length} problems (${r.generations} generations × ${r.repeats} repeats), held-out ${r.held_out_score == null ? "—" : fmt(r.held_out_score)}; ${r.calls} model calls, ${r.minutes} min.</p>
    <table class="t"><tr><th>Problem</th><th>Score</th><th>Final test progress</th><th>Area under the curve</th><th>90% by</th><th>Crashes</th></tr>
    ${[...Object.entries(r.problems), ...Object.entries(r.held_out).map(([k, v]) => [k + " (held out)", v])].map(([k, v]) => `<tr><td>${esc(k)}</td><td>${fmt(v.score)}</td><td>${pct(v.final)}</td><td>${pct(v.auc)}</td><td>${v.plateau != null ? "G" + fmt(v.plateau, 0) : "—"}</td><td>${v.crashes}</td></tr>`).join("")}</table>`;
}

function metaChart(it) {
  const cs = (it.state.candidates || []).filter(c => c.result);
  if (!cs.length) return "";
  const W = 1000, H = 220, L = 44, R = 16, T = 14, B = 30;
  const G = Math.max(1, ...cs.map(c => c.gen));
  const sc = cs.map(c => c.result.score);
  const lo = Math.floor(Math.min(...sc) / 5) * 5, hi = Math.ceil(Math.max(...sc, lo + 5) / 5) * 5;
  const x = g => L + (W - L - R) * (g / G), y = v => T + (H - T - B) * (1 - (v - lo) / Math.max(1, hi - lo));
  const byId = Object.fromEntries(cs.map(c => [c.id, c]));
  let inc = cs.find(c => c.origin === "seed") || cs[0], line = [[0, inc.result.score]];
  for (let g = 1; g <= G; g++) {
    const sw = it.swaps.filter(w => w.type === "swap" && w.gen === g).pop();
    if (sw && byId[sw.new]) inc = byId[sw.new];
    line.push([g, inc.result.score]);
  }
  let h = `<g class="axis">`;
  for (let v = lo; v <= hi; v += Math.max(1, Math.round((hi - lo) / 4))) h += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  for (let g = 0; g <= G; g++) h += `<text x="${x(g)}" y="${H - 8}" text-anchor="middle">${g === 0 ? "start" : "G" + g}</text>`;
  h += `</g><polyline class="curve" points="${line.map(([g, v]) => `${x(g)},${y(v)}`).join(" ")}"/>`;
  cs.forEach(c => { h += `<circle class="bead ${c.origin === "wide" ? "wide" : c.origin === "deep" ? "deep" : "combo"}" cx="${x(c.gen) + (c.origin === "wide" ? 7 : c.origin === "deep" ? -7 : 0)}" cy="${y(c.result.score)}" r="6"><title>${esc(c.id)} ${esc(c.name || "")}: ${fmt(c.result.score)}</title></circle>`; });
  return `<section class="hero"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Strategy scores by outer generation">${h}</svg>
    <div class="legend"><span><i style="background:var(--ink)"></i>incumbent</span><span><i style="background:var(--deep)"></i>from the Researcher</span><span><i style="background:var(--wide)"></i>from the Mutator</span></div></section>`;
}

function metaOuter(it) {
  const s = it.state, cs = s.candidates || [];
  return `<h2>Outer run <span class="muted small">${esc(it.id)}</span></h2>${metaChart(it)}
    <p>Incumbent <b>${esc(s.incumbent)}</b> after ${s.gen} outer generations; ${it.swaps.filter(x => x.type === "swap").length} promotions (each swapped into the outer loop itself).</p>
    <table class="t"><tr><th>Strategy</th><th>Gen</th><th>From</th><th>What changed</th><th>Score</th><th>Verdict</th></tr>
    ${cs.map(c => `<tr><td><b>${esc(c.id)}</b> ${esc(c.name || "")}</td><td>${c.gen}</td><td><span class="dot ${c.origin === "deep" ? "deep" : c.origin === "wide" ? "wide" : ""}"></span>${esc(c.origin)}${c.parent ? " of " + esc(c.parent) : ""}</td>
      <td class="small">${esc((c.change || "").slice(0, 160))}${(c.changed || []).length ? `<br><span class="muted">${c.changed.map(esc).join(", ")}</span>` : ""}</td>
      <td>${c.result ? fmt(c.result.score) : "—"}${c.delta != null ? ` <span class="muted small">(${c.delta > 0 ? "+" : ""}${fmt(c.delta)})</span>` : ""}</td><td>${esc(c.verdict || "")}</td></tr>`).join("")}</table>`;
}

/* ------------------------------------------------------------------ new run */
async function openNewRun(problem) {
  if (!state.suite) state.suite = await api("/api/suite");
  $("#problemSelect").innerHTML = state.suite.filter(p => !p.error).map(p => `<option value="${esc(p.name)}" ${p.name === problem ? "selected" : ""}>${esc(p.title)}</option>`).join("");
  $("#newRun").showModal();
}
$("#newRunBtn").onclick = () => openNewRun();
$("#newRunForm").addEventListener("submit", async e => {
  if (e.submitter && e.submitter.value !== "go") return;
  const fd = new FormData(e.target);
  await api("/api/launch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.fromEntries(fd)) });
  setTimeout(refreshRuns, 2500);
});

/* ------------------------------------------------------------------ router */
async function route() {
  const h = location.hash || "#/";
  document.querySelectorAll(".views a").forEach(a => a.removeAttribute("aria-current"));
  clearInterval(state.timer);
  if (h.startsWith("#/run/")) {
    const id = decodeURIComponent(h.slice(6));
    await loadRun(id);
    state.timer = setInterval(() => { const r = state.runs.find(r => r.id === id); if (r && r.state === "running") loadRun(id, true); }, 5000);
  } else if (h === "#/suite") {
    $('[data-view="suite"]').setAttribute("aria-current", "page"); state.runId = null; renderRail(); renderSuite();
  } else if (h === "#/meta") {
    $('[data-view="meta"]').setAttribute("aria-current", "page"); state.runId = null; renderRail(); renderMeta();
  } else {
    $('[data-view="home"]').setAttribute("aria-current", "page"); state.runId = null; renderRail(); renderHome();
  }
}
window.addEventListener("hashchange", route);
refreshRuns().then(route);
setInterval(refreshRuns, 6000);
