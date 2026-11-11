"""The Atlas: v4's memory (helix4/memory.py, class Atlas), ported unchanged in what it does. Every run starts it empty.

Three layers:
- the immutable log: every program and plan (the archive, plans.jsonl);
- the tree of attempts: who built on whom, and what each change did;
- a graph of findings: claims written by a Distiller after each generation, each citing the programs that are its
  evidence, linked by type (refines, contradicts, requires, combines-with, explains). A finding's status (supported,
  mixed, refuted) is computed by code from the measured gains of its evidence, never taken from the model.

Before planning, the planner sees a map: the pruned tree, the findings index, and the last generation in full. It
opens up to `open_k` items (programs or findings), then plans.

Differences from v4's code (docs/LEAN_V4.md): the map is built under the run's lock (v4 read the archive while
mutations wrote to it); code is shown at the problem's clip sizes (v4: 9,000 characters for the best program, 3,500
for an opened one); scores at 9 digits. Nothing else.
"""
from __future__ import annotations

import json

from lean import prompts as P
from lean import stores as S
from lean.archive import SHOWN, short
from lean.problems import setting

LINK_TYPES = ("refines", "contradicts", "requires", "combines-with", "explains")
KINDS = ("works", "fails", "mechanism", "question")


def result_lines(p, k=4):
    if not p.valid:
        return [p.error[:300]] + [l for l in p.feedback[1:2]]
    return p.feedback[:k]


def planned(plan):
    """A planned program's plan (a mutation's may hold only the guidance it cited)."""
    return bool(plan.get("hypothesis") or plan.get("change"))


def guided(plan):
    return f" | guidance: {', '.join(plan['guidance'])}" if plan.get("guidance") else ""


def outcome(p):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "seed"
    return "gain" if p.delta > 1e-9 else "no gain"


class Atlas:
    def __init__(self, run, open_k=6):
        self.run, self.open_k = run, open_k
        self.path = run.dir / "findings.jsonl"
        self.events = [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()] if self.path.exists() else []
        self.rebuild()

    # ---- the findings graph
    def rebuild(self):
        self.findings = {}
        for ev in self.events:
            if ev["op"] == "new":
                self.findings[ev["id"]] = {**ev, "evidence": list(ev["evidence"]), "links": list(ev.get("links", []))}
            elif ev["op"] == "evidence" and ev["id"] in self.findings:
                f = self.findings[ev["id"]]
                f["evidence"] += [p for p in ev["programs"] if p not in f["evidence"]]

    def _append(self, ev):
        self.events.append(ev)
        with self.path.open("a") as fh:
            fh.write(json.dumps(ev) + "\n")

    def status(self, f):
        outs = [outcome(self.run.archive.programs.get(p)) for p in f["evidence"]]
        gains = outs.count("gain")
        bad = outs.count("no gain") + outs.count("error")
        if f["kind"] == "question":
            return "open" if not (gains or bad) else f"tested ({gains} gained, {bad} didn't)"
        if f["kind"] == "fails":
            st = "supported" if bad and not gains else "mixed" if bad and gains else "refuted" if gains else "untested"
        else:
            st = "supported" if gains and gains >= bad else "mixed" if gains else "refuted" if bad else "untested"
        return f"{st}: {gains} gained, {bad} didn't"

    def best_gain(self, f):
        a = self.run.archive.programs
        ds = [a[p].delta for p in f["evidence"] if p in a and a[p].valid and a[p].delta is not None]
        return max(ds) if ds else None

    def citing(self, pid):
        return [fid for fid, f in self.findings.items() if pid in f["evidence"]]

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.9f}" if g is not None and f["kind"] != "fails" else ""
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        return f"{fid} [{f['kind']} · {self.status(f)}{gtxt}] {short(f['claim'], n)}" + (f" ({links})" if links else "")

    # ---- the map
    def tree(self, gen):
        a = self.run.archive
        include = set()
        for p in a.ranked()[:12] + [p for p in a.programs.values() if p.round == gen - 1]:
            include |= {q.id for q in a.lineage(p.id, depth=100)}
        kids = {}
        for p in a.programs.values():
            kids.setdefault(p.parent, []).append(p)
        lines = []

        def walk(p, depth):
            cites = self.citing(p.id)
            score = f"{p.score:.9f}" + (f" ({p.delta:+.9f})" if p.delta is not None else "") if p.valid else "FAILED"
            lines.append(f"{'  ' * min(depth, 12)}{p.id} g{p.round} {SHOWN.get(p.role, p.role)}: {score}: {short(p.idea, 70)}"
                         + (f" [{', '.join(cites[:4])}]" if cites else ""))
            ch = sorted(kids.get(p.id, []), key=lambda q: -(q.score if q.score is not None else -1))
            shown = [q for q in ch if q.id in include]
            hidden = [q for q in ch if q.id not in include]
            for q in shown:
                walk(q, depth + 1)
            if hidden:
                ok = [q for q in hidden if q.valid]
                best = f", best {max(q.score for q in ok):.9f}" if ok else ""
                lines.append(f"{'  ' * min(depth + 1, 12)}… {len(hidden)} more children ({len(hidden) - len(ok)} failed{best})")

        for root in kids.get(None, []):
            walk(root, 0)
        return "\n".join(lines)

    def window(self, gen):
        last = [p for p in self.run.archive.programs.values() if p.round == gen - 1]
        if not last:
            return "(none yet)"
        out = []
        for p in sorted(last, key=lambda q: q.id):
            pl = {k: v for k, v in (p.plan or {}).items() if k != "summary"}
            what = (f"hypothesis: {short(pl.get('hypothesis'), 200)} | change: {short(pl.get('change'), 220)} | "
                    f"predicted: {short(pl.get('prediction'), 120)}") if planned(pl) else f"mutation: {short(p.idea, 200)}"
            what += guided(pl)
            res = "\n    ".join(result_lines(p, 5))
            coder = f"\n    coder: {short(p.summary, 160)}" if p.summary and p.summary != p.idea else ""
            out.append(f"- {p.line()}\n    {what}{coder}\n    {res}")
        return "\n".join(out)

    def map(self, gen):
        fl = sorted(self.findings, key=lambda i: int(i[1:]))
        if len(fl) > 45:      # keep the newest and the best-supported
            fl = sorted(fl, key=lambda i: (self.status(self.findings[i]).startswith("supported"), int(i[1:])))[-45:]
            fl = sorted(fl, key=lambda i: int(i[1:]))
        findings = "\n".join(self.finding_line(i) for i in fl) or "(none yet)"
        return (f"## Map 1: the tree of attempts (indent = built on the line above; [F..] = findings citing it)\n"
                f"{self.tree(gen)}\n\n## Map 2: findings so far ({len(self.findings)}), status computed from measured "
                f"results\n{findings}\n\n## The last generation, in full\n{self.window(gen)}")

    # ---- opening items
    def open_program(self, pid):
        a = self.run.archive
        p = a.programs[pid]
        out = [f"### {p.line()}"]
        pl = {k: v for k, v in (p.plan or {}).items() if k != "summary"}
        if planned(pl):
            out.append(f"Plan: hypothesis: {pl.get('hypothesis')} | change: {pl.get('change')} | "
                       f"predicted: {pl.get('prediction')} | builds on: {pl.get('builds_on')}{guided(pl)}")
        else:
            out.append(f"Intent: {p.idea}{guided(pl)}")
        if p.summary:
            out.append(f"Coder's summary: {p.summary}")
        out.append("Result:\n  " + "\n  ".join(result_lines(p, 8)))
        if p.diff:
            out.append(f"Diff from {p.parent}:\n```diff\n{P.clip(p.diff, 1800)}\n```")
        out.append(f"Code:\n```python\n{P.clip(p.code, self.run.clip['opened'])}```")
        kids = [q for q in a.programs.values() if q.parent == pid]
        if kids:
            out.append("Its children: " + "; ".join(
                f"{q.id} {(f'{q.delta:+.9f}' if q.valid and q.delta is not None else 'FAILED')}: {short(q.idea, 70)}"
                for q in kids))
        c = self.citing(pid)
        if c:
            out.append("Findings citing it: " + "; ".join(self.finding_line(f, 100) for f in c))
        return "\n".join(out)

    def open_finding(self, fid):
        f = self.findings[fid]
        a = self.run.archive
        out = [f"### {self.finding_line(fid, 1000)}", "Evidence:"]
        for pid in f["evidence"]:
            p = a.programs.get(pid)
            if p:
                out.append(f"- {p.line()}: {short(p.idea, 140)}\n    "
                           + "\n    ".join(result_lines(p, 4)[1:] if p.valid else result_lines(p)))
        nb = [l["to"] for l in f["links"]] + [i for i, g in self.findings.items() if any(l["to"] == fid for l in g["links"])]
        if nb:
            out.append("Linked findings:")
            out += [f"- {self.finding_line(i, 200)}" for i in dict.fromkeys(nb) if i in self.findings]
        return "\n".join(out)

    def plan_prompt(self, gen, k, system):
        """The planner's view: header, the best program, the map, then (from generation 2) the items the planner
        chose to open. Returns (prompt, info). Reads the archive under the run's lock; the Navigator call is outside it."""
        run = self.run
        with run.lock:
            base = run.header() + "\n" + run.best_block(run.archive.best()) + "\n\n" + self.map(gen)
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", system, base + "\n\n" + P.NAVIGATOR_ASK.format(k=self.open_k), 0.4, 800)
            js = P.extract_json(nav) or {}
            js = js if isinstance(js, dict) else {}
            asked = [str(x).strip() for x in (js.get("open") or []) if isinstance(x, (str, int))][: self.open_k]
            why = str(js.get("why", ""))[:300]
            with run.lock:
                for item in asked:
                    if item in run.archive.programs:
                        opened.append(self.open_program(item))
                    elif item in self.findings:
                        opened.append(self.open_finding(item))
        user = base
        if opened:
            user += "\n\n## What you opened\n" + "\n\n".join(opened)
        with run.lock:
            user += "\n\n" + run.plan_tail(k, " or findings")
        return user, {"opened": asked, "open_why": why}

    # ---- the Distiller
    def update(self, gen, analysis, children):
        run = self.run
        index = "\n".join(self.finding_line(i, 220) for i in self.findings) or "(none yet)"
        rows = []
        for c in children:
            pl = {k: v for k, v in (c.plan or {}).items() if k != "summary"}
            what = (f"planned: {short(pl.get('hypothesis'), 240)} | change: {short(pl.get('change'), 260)} | "
                    f"predicted: {short(pl.get('prediction'), 140)} | builds on {pl.get('builds_on')}") if planned(pl) \
                else f"wide-loop mutation: {short(c.idea, 220)}"
            what += guided(pl)
            parent = run.archive.programs.get(c.parent)
            rows.append(f"### {c.line()}\n{what}\ncoder's summary: {short(c.summary, 200)}\n"
                        f"its base {c.parent}: {short(parent.idea, 120) if parent else '-'}\nresult:\n  "
                        + "\n  ".join(result_lines(c, 6))
                        + (f"\ndiff from its base:\n```diff\n{P.clip(c.diff, 1500)}\n```" if c.diff else ""))
        title = getattr(run.problem, "title", run.problem.name)
        user = (f"{title}\n\n## Findings so far\n{index}\n\n## The researcher's analysis this generation\n"
                f"{short(analysis, 900)}\n\n## Generation {gen}: every program and its result\n"
                + "\n\n".join(rows) + "\n\n" + setting(run.problem, "distiller_ask").format(gen=gen)
                + (S.DISTILLER_NOTE if run.guidance else ""))
        reply = run.call("distiller", P.DISTILLER_SYSTEM, user, 0.3, 3000)
        js = P.extract_json(reply) or {}
        js = js if isinstance(js, dict) else {}
        known = run.archive.programs
        added = 0
        for nf in (js.get("new") or [])[:6]:
            if not isinstance(nf, dict):
                continue
            ev = [str(p) for p in (nf.get("evidence") or []) if str(p) in known]
            kind = nf.get("kind") if nf.get("kind") in KINDS else "mechanism"
            claim = " ".join(str(nf.get("claim") or "").split())[:400]
            if not claim or (not ev and kind != "question"):
                continue
            links = [{"to": str(l.get("to")), "type": l.get("type")} for l in (nf.get("links") or [])
                     if isinstance(l, dict) and str(l.get("to")) in self.findings and l.get("type") in LINK_TYPES]
            fid = f"F{len([e for e in self.events if e['op'] == 'new']) + 1}"
            self._append({"op": "new", "id": fid, "gen": gen, "kind": kind, "claim": claim, "evidence": ev,
                          "links": links})
            added += 1
        attached = 0
        for e in js.get("evidence") or []:
            if isinstance(e, dict) and str(e.get("finding")) in self.findings:
                progs = [str(p) for p in (e.get("programs") or []) if str(p) in known]
                if progs:
                    self._append({"op": "evidence", "id": str(e["finding"]), "gen": gen, "programs": progs})
                    attached += len(progs)
        self.rebuild()
        return {"findings_added": added, "evidence_attached": attached}

    def truncate(self, gen_done):
        self.events = [e for e in self.events if e["gen"] <= gen_done]
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.events))
        self.rebuild()

    def stats(self):
        st = [self.status(f).split(":")[0] for f in self.findings.values()]
        return {"findings": len(self.findings), "supported": st.count("supported"), "refuted": st.count("refuted"),
                "mixed": st.count("mixed"), "links": sum(len(f["links"]) for f in self.findings.values())}
