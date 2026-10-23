"""v7's Atlas: helix4's Atlas with v4.7's measurement fixes, v4's tree view kept, and the planner's brief built from
slots (docs/V7_DESIGN.md).

- Gains count only above the run's floor (Run.floor: a small relative floor, raised to the evaluator's measured
  noise on a noisy problem); statuses use it.
- A failure is shown with the construction it was tried on; the map keeps the best and newest "works"/"mechanism"
  findings and the open questions, the newest failures, and groups older failures by construction.
- The header has no countdown and, when the problem has a proven bound, the honest room left.
- The tree of attempts (Map 1) is v4's, so the planner still sees the whole search.
"""
from __future__ import annotations

from collections import Counter

from helix4 import prompts as P4
from helix4.archive import short
from helix4.memory import Atlas, LINK_TYPES, KINDS
from helix7 import prompts as P

DISTILLER_EXTRA = (" Each program is on the main line or on a side track (shown as [track ...]). A failure is a fact "
                   "about the construction it was tried on: say which (its base program and score), and don't "
                   "generalise it to the whole problem.")


def outcome(p, run):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "seed"
    return "gain" if p.delta > run.floor(p.start_score) else "no gain"


class Atlas7(Atlas):
    name = "v7"

    def status(self, f):
        outs = [outcome(self.run.archive.programs.get(p), self.run) for p in f["evidence"]]
        gains = outs.count("gain")
        bad = outs.count("no gain") + outs.count("error")
        if f["kind"] == "question":
            return "open" if not (gains or bad) else f"tested ({gains} gained, {bad} didn't)"
        if f["kind"] == "fails":
            st = "held" if bad and not gains else "mixed" if bad and gains else "refuted" if gains else "untested"
            return f"{st}: {bad} didn't gain, {gains} did"
        st = "supported" if gains and gains >= bad else "mixed" if gains else "refuted" if bad else "untested"
        return f"{st}: {gains} gained, {bad} didn't"

    def scope(self, f):
        """(base program id, its score): the construction a finding was mostly tested on."""
        a = self.run.archive
        bases = [a.programs[p].parent for p in f["evidence"] if p in a.programs and a.programs[p].parent]
        if not bases:
            return None, None
        pid = Counter(bases).most_common(1)[0][0]
        b = a.programs.get(pid)
        return pid, (b.score if b is not None and b.valid else None)

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.5f}" if g is not None and f["kind"] != "fails" else ""
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        where = ""
        if f["kind"] == "fails":
            pid, sc = self.scope(f)
            if pid:
                where = f" · tried on {pid}'s construction" + (f" ({sc:.6f})" if sc is not None else "")
        return f"{fid} [{f['kind']} · {self.status(f)}{gtxt}{where}] {short(f['claim'], n)}" + (f" ({links})" if links else "")

    def findings_view(self, limit=None):
        cfg = self.run.cfg
        limit = limit or cfg.map_findings
        ids = sorted(self.findings, key=lambda i: int(i[1:]))
        works = [i for i in ids if self.findings[i]["kind"] in ("works", "mechanism")]
        fails = [i for i in ids if self.findings[i]["kind"] == "fails"]
        questions = [i for i in ids if self.findings[i]["kind"] == "question" and self.status(self.findings[i]) == "open"]
        by_gain = sorted(works, key=lambda i: -(self.best_gain(self.findings[i]) or 0.0))
        keep_works = list(dict.fromkeys(by_gain[: cfg.map_works_best] + works[-cfg.map_works_new:]))
        keep_q = questions[-cfg.map_questions:]
        keep_fails = fails[-cfg.map_fails:]
        rest = limit - len(keep_works) - len(keep_q) - len(keep_fails)
        if rest > 0:
            keep_works += [i for i in reversed(works) if i not in keep_works][:rest]
        shown = sorted(set(keep_works + keep_q + keep_fails), key=lambda i: int(i[1:]))
        text = "\n".join(self.finding_line(i) for i in shown) or "(none yet)"
        groups = {}
        for i in fails:
            if i not in keep_fails:
                _, sc = self.scope(self.findings[i])
                groups.setdefault(f"{sc:.4f}" if sc is not None else None, []).append(i)
        summary = [f"- {len(fs)} more failures tried on {'the construction scoring ' + k if k else 'various constructions'} "
                   f"(e.g. {', '.join(fs[-3:])}): facts about that construction, not about the problem"
                   for k, fs in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:8]]
        if summary:
            text += "\nOlder failures, grouped by the construction they were tried on:\n" + "\n".join(summary)
        return text, len(shown)

    def open_finding(self, fid):
        f = self.findings[fid]
        a = self.run.archive
        out = [f"### {self.finding_line(fid, 1000)}", "Evidence:"]
        ev, k = f["evidence"], self.run.cfg.open_evidence
        if len(ev) > k:
            out.append(f"({len(ev) - k} older pieces of evidence not shown)")
        for pid in ev[-k:]:
            p = a.programs.get(pid)
            if p:
                out.append(f"- {p.line()}: {short(p.intent, 140)}\n    "
                           + "\n    ".join(p.feedback[1:4] if p.valid else [p.error[:300]]))
        nb = list(dict.fromkeys([l["to"] for l in f["links"]]
                                + [i for i, g in self.findings.items() if any(l["to"] == fid for l in g["links"])]))
        if nb:
            out.append("Linked findings:")
            out += [f"- {self.finding_line(i, 200)}" for i in nb[-12:] if i in self.findings]
        return "\n".join(out)

    # ---- the view
    def header(self, gen):
        run = self.run
        if hasattr(run, "gen_header"):
            return run.gen_header(gen)
        txt = (f"{run.problem_text}\n\n# Generation {gen}\nEach program gets {run.cfg.budget:.0f} s of CPU and starts "
               f"from its base's construction.\n")
        best, ub = run.archive.best(), run.upper_bound
        if ub is not None and best is not None and best.score is not None and ub > best.score:
            txt += (f"The proven upper bound is {ub:g}; the best score so far is {best.score:.6f}, so up to "
                    f"{100 * (ub - best.score) / ub:.1f}% of the range is still open.\n")
        return txt

    def lineage_gains(self, pid, depth=60):
        parts, flat = [], 0
        for p in self.run.archive.lineage(pid, depth=depth):
            if p.score is None:
                continue
            if p.parent and p.delta is not None and outcome(p, self.run) != "gain":
                flat += 1
                continue
            if flat:
                parts.append(f"({flat} steps without a gain)")
                flat = 0
            what = f" ({p.delta:+.6f}: {short(p.intent, 60)})" if p.parent and p.delta is not None else ""
            parts.append(f"{p.id} {p.score:.6f}{what}")
        if flat:
            parts.append(f"({flat} steps without a gain)")
        return " -> ".join(parts[-8:])

    def best_block(self):
        b = self.run.archive.best()
        fb = "\n".join(f"  {l}" for l in b.feedback)
        return (f"## The best program so far: {b.id} (score {b.score:.6f}, track {self.run.track_of(b)})\n"
                f"The steps that built it (gains only): {self.lineage_gains(b.id)}\nIts result:\n{fb}\n"
                f"```python\n{P4.clip(b.code, self.run.best_code_chars())}```")

    def tree(self, gen, top=12, depth=100):
        """helix4's tree of attempts, marking where a side track starts, with the bests of the live and newest side
        tracks included; cut down when it grows past `tree_chars`."""
        text = self._tree(gen, top, depth)
        if len(text) > self.run.cfg.tree_chars:
            text = self._tree(gen, 6, 40)
        return P4.clip(text, self.run.cfg.tree_chars) if len(text) > self.run.cfg.tree_chars else text

    def _tree(self, gen, top, depth):
        run, a = self.run, self.run.archive
        include = set()
        tracks = sorted(run.tracks.values(), key=lambda t: -t["opened"])
        marks = [t["best_id"] for t in tracks if t.get("best_id") and (run.live(t) or t in tracks[:4])]
        for pid in [p.id for p in a.ranked()[:top]] + [p.id for p in a.programs.values() if p.gen == gen - 1] + marks:
            include |= {q.id for q in a.lineage(pid, depth=depth)}
        kids = {}
        for p in a.programs.values():
            kids.setdefault(p.parent, []).append(p)
        lines = []

        def walk(p, d):
            cites = self.citing(p.id)
            score = f"{p.score:.6f}" + (f" ({p.delta:+.6f})" if p.delta is not None else "") if p.valid else "FAILED"
            par = a.programs.get(p.parent) if p.parent else None
            tid = run.track_of(p)
            mark = f" · starts track {tid}" if par is not None and run.track_of(par) != tid and p.role != "alt" else ""
            lines.append(f"{'  ' * min(d, 12)}{p.id} g{p.gen} {p.role}: {score}: {short(p.intent, 70)}{mark}"
                         + (f" [{', '.join(cites[:4])}]" if cites else ""))
            ch = sorted(kids.get(p.id, []), key=lambda q: -(q.score or -1))
            shown = [q for q in ch if q.id in include]
            hidden = [q for q in ch if q.id not in include]
            for q in shown:
                walk(q, d + 1)
            if hidden:
                ok = [q for q in hidden if q.valid]
                best = f", best {max(q.score for q in ok):.6f}" if ok else ""
                lines.append(f"{'  ' * min(d + 1, 12)}… {len(hidden)} more children ({len(hidden) - len(ok)} failed{best})")

        for root in kids.get(None, []):
            walk(root, 0)
        return "\n".join(lines)

    def window(self, gen):
        run = self.run
        last = [p for p in run.archive.programs.values() if p.gen == gen - 1]
        if not last:
            return "(none yet)"
        out = []
        for p in sorted(last, key=lambda q: q.id):
            pl = p.plan or {}
            kind = pl.get("kind") or ("alternative" if p.role == "alt" else "mutation" if p.role == "wide" else p.role)
            what = (f"hypothesis: {short(pl.get('hypothesis'), 200)} | change: {short(pl.get('change'), 220)} | "
                    f"target: {short(pl.get('prediction'), 120)}") if pl.get("hypothesis") else f"{short(p.intent, 200)}"
            res = "\n    ".join(p.feedback[:5] if p.valid else [p.error[:300]] + p.feedback[1:2])
            coder = f"\n    coder: {short(p.summary, 160)}" if p.summary and p.summary != p.intent else ""
            out.append(f"- [{run.track_of(p)} · {kind}] {p.line()}\n    {what}{coder}\n    {res}")
        return "\n".join(out)

    def open_program(self, pid):
        a = self.run.archive
        p = a.programs[pid]
        pl = p.plan or {}
        out = [f"### [track {self.run.track_of(p)}] {p.line()}"]
        if pl.get("hypothesis"):
            out.append(f"Plan ({pl.get('kind', 'main')}): hypothesis: {pl.get('hypothesis')} | change: {pl.get('change')} "
                       f"| target: {pl.get('prediction')} | builds on: {pl.get('builds_on')}")
        else:
            out.append(f"Intent: {p.intent}")
        if p.summary:
            out.append(f"Coder's summary: {p.summary}")
        out.append("Result:\n  " + "\n  ".join(p.feedback[:8] if p.valid else [p.error[:300]] + p.feedback[1:2]))
        if p.diff:
            out.append(f"Diff from {p.parent}:\n```diff\n{P4.clip(p.diff, 1800)}\n```")
        out.append(f"Code:\n```python\n{P4.clip(p.code, 3500)}```")
        kids = [q for q in a.programs.values() if q.parent == pid]
        if kids:
            out.append("Its children: " + "; ".join(
                f"{q.id} {(f'{q.delta:+.6f}' if q.valid and q.delta is not None else 'FAILED')}: {short(q.intent, 70)}"
                for q in kids[-15:]) + (f" ({len(kids) - 15} earlier children not shown)" if len(kids) > 15 else ""))
        c = self.citing(pid)
        if c:
            out.append("Findings citing it: " + "; ".join(self.finding_line(f, 100) for f in c[-10:]))
        return "\n".join(out)

    def map(self, gen):
        findings, shown = self.findings_view()
        fl = max(self.run.cfg.gain_floor, self.run.noise)
        return (f"## Map 1: the tree of attempts (indent = built on the line above; [F..] = findings citing it)\n"
                f"{self.tree(gen)}\n\n## Map 2: findings ({len(self.findings)} in all, {shown} shown; status computed "
                f"from measured results; a gain counts only above {fl:.2g} relative, the noise floor)\n{findings}\n\n"
                f"## The last generation, in full\n{self.window(gen)}")

    def plan(self, gen, slots, brief):
        run = self.run
        k = len(slots)
        base = self.header(gen) + "\n" + self.best_block() + "\n\n" + self.map(gen) + "\n\n" + brief
        system = run.researcher_system(k)
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", system, base + "\n\n" + P4.NAVIGATOR_ASK.format(k=run.cfg.open_k),
                           temperature=0.4, max_tokens=800, effort="none", gen=gen)
            js = P4.extract_json(nav) or {}
            asked = list(dict.fromkeys(str(x).strip() for x in (js.get("open") or [])
                                       if isinstance(x, (str, int))))[: run.cfg.open_k]
            why = str(js.get("why", ""))[:300]
            for item in asked:
                if item in run.archive.programs:
                    opened.append(self.open_program(item))
                elif item in self.findings:
                    opened.append(self.open_finding(item))
        user = base
        if opened:
            user += "\n\n## What you opened\n" + "\n\n".join(opened)
        revive = any(s["kind"] == "revive" for s in slots)
        user += "\n\n" + P.PLAN_FORMAT.format(k=k, revive_field=', "revives": "<finding id, revive slot only>"' if revive else "")
        plan, info = run.researcher(user, gen, system=system)
        info.update(opened=asked, open_why=why)
        return plan, info

    # ---- the distiller (helix4's, with each program's track)
    def update(self, gen, plan, children):
        run = self.run
        ids = sorted(self.findings, key=lambda i: int(i[1:]))
        index = "\n".join(self.finding_line(i, 220) for i in ids) or "(none yet)"
        if len(index) > 60000:
            index = "\n".join(self.finding_line(i, 120) for i in ids[-250:])
        rows = []
        for c in children:
            pl = c.plan or {}
            what = (f"planned ({pl.get('kind', 'main')}): {short(pl.get('hypothesis'), 240)} | change: "
                    f"{short(pl.get('change'), 260)} | predicted: {short(pl.get('prediction'), 140)}"
                    if pl.get("hypothesis") else f"{c.role}: {short(c.intent, 220)}")
            parent = run.archive.programs.get(c.parent)
            pscore = f" ({parent.score:.6f})" if parent is not None and parent.valid else ""
            rows.append(f"### [track {run.track_of(c)}] {c.line()}\n{what}\ncoder's summary: {short(c.summary, 200)}\n"
                        f"its base {c.parent}{pscore}: {short(parent.intent, 120) if parent else '-'}\nresult:\n  "
                        + "\n  ".join(c.feedback[:6] if c.valid else [c.error[:300]] + c.feedback[1:2])
                        + (f"\ndiff from its base:\n```diff\n{P4.clip(c.diff, 1500)}\n```" if c.diff else ""))
        user = (f"{run.problem.TITLE}\n\n## Findings so far\n{index}\n\n## The researcher's analysis this generation\n"
                f"{short((plan or {}).get('analysis'), 900)}\n\n## Generation {gen}: every program and its result\n"
                + "\n\n".join(rows) + "\n\n" + P4.DISTILLER_ASK.format(gen=gen) + DISTILLER_EXTRA)
        reply = run.call("distiller", P4.DISTILLER_SYSTEM, user, temperature=0.3, max_tokens=3000, effort="none", gen=gen)
        js = P4.extract_json(reply) or {}
        known = run.archive.programs
        added = attached = 0
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
            self._append({"op": "new", "id": fid, "gen": gen, "kind": kind, "claim": claim, "evidence": ev, "links": links})
            added += 1
        for e in js.get("evidence") or []:
            if isinstance(e, dict) and str(e.get("finding")) in self.findings:
                progs = [str(p) for p in (e.get("programs") or []) if str(p) in known]
                if progs:
                    self._append({"op": "evidence", "id": str(e["finding"]), "gen": gen, "programs": progs})
                    attached += len(progs)
        self.rebuild()
        return {"findings_added": added, "evidence_attached": attached}

    def stats(self):
        st = [self.status(f).split(":")[0] for f in self.findings.values()]
        return {"findings": len(self.findings), "supported": st.count("supported"), "held": st.count("held"),
                "refuted": st.count("refuted"), "mixed": st.count("mixed"),
                "links": sum(len(f["links"]) for f in self.findings.values())}
