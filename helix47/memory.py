"""v4.7's Atlas: helix4's Atlas (helix4/memory.py), with the planner's view organised by line (docs/V47_DESIGN.md).

What the planner sees each generation, instead of v4's view (the best program, the tree from Code Zero, the newest
45 findings):
- For each active line: its best program and result, where it started, how it moved over its last generations
  (against its own previous best, not against the record), the honest room above it, and its last generation in full.
- The closed lines by name, with why they were closed, but not their scores.
- The findings, balanced: the best and newest "works" and "mechanism" findings and the open questions of the whole
  search; failures only from the active lines (the newest few); the failures of closed lines grouped into one line
  each ("Line L1 (closed): 389 failures, facts about its constructions"). In v4, at generation 140, all 45 findings
  on the map were failures, many reading "the point is confirmed saturated".
- Gains have a noise floor (`gain_floor`, relative): v4 counted +1e-9, so polishing kept "succeeding".
- No countdown ("Generation 140", not "of 150"); an opened finding shows its 12 newest pieces of evidence.
"""
from __future__ import annotations

from collections import Counter

from helix4 import prompts as P4
from helix4.archive import short
from helix4.memory import Atlas, LINK_TYPES, KINDS
from helix47 import prompts as P

DISTILLER_EXTRA = (" Each program belongs to a line (shown as [line Lx]). A failure is a fact about the construction "
                   "it was tried on: say which line and base program, and don't generalise it to the whole problem.")


def rel_floor(cfg, ref):
    return cfg.gain_floor * max(abs(ref or 0.0), 1e-12)


def outcome(p, cfg):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "seed"
    return "gain" if p.delta > rel_floor(cfg, p.start_score) else "no gain"


class Atlas47(Atlas):
    name = "v47"

    # ---- statuses, with the noise floor
    def status(self, f):
        outs = [outcome(self.run.archive.programs.get(p), self.run.cfg) for p in f["evidence"]]
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
        """(line id, base program id) a finding was tested on: the most common among its evidence."""
        a = self.run.archive
        ev = [a.programs[p] for p in f["evidence"] if p in a.programs]
        if not ev:
            return None, None
        line = Counter(self.run.line_of(p) for p in ev).most_common(1)[0][0]
        bases = [p.parent for p in ev if p.parent]
        return line, (Counter(bases).most_common(1)[0][0] if bases else None)

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.5f}" if g is not None and f["kind"] != "fails" else ""
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        line, base = self.scope(f)
        where = f" · line {line}" if line else ""
        if f["kind"] == "fails" and base:
            where += f", tried on {base}'s construction"
        return f"{fid} [{f['kind']} · {self.status(f)}{gtxt}{where}] {short(f['claim'], n)}" + (f" ({links})" if links else "")

    # ---- the balanced findings
    def findings_view(self, limit=None):
        cfg, run = self.run.cfg, self.run
        limit = limit or cfg.map_findings
        active = {ln["id"] for ln in run.active_lines()}
        ids = sorted(self.findings, key=lambda i: int(i[1:]))
        works = [i for i in ids if self.findings[i]["kind"] in ("works", "mechanism")]
        fails = [i for i in ids if self.findings[i]["kind"] == "fails"]
        questions = [i for i in ids if self.findings[i]["kind"] == "question" and self.status(self.findings[i]) == "open"]
        by_gain = sorted(works, key=lambda i: -(self.best_gain(self.findings[i]) or 0.0))
        keep_works = list(dict.fromkeys(by_gain[: cfg.map_works_best] + works[-cfg.map_works_new:]))
        keep_q = questions[-cfg.map_questions:]
        active_fails = [i for i in fails if self.scope(self.findings[i])[0] in active]
        keep_fails = active_fails[-cfg.map_fails:]
        rest = limit - len(keep_works) - len(keep_q) - len(keep_fails)
        if rest > 0:
            keep_works += [i for i in reversed(works) if i not in keep_works][:rest]
        shown = sorted(set(keep_works + keep_q + keep_fails), key=lambda i: int(i[1:]))
        text = "\n".join(self.finding_line(i) for i in shown) or "(none yet)"
        groups = {}
        for i in fails:
            if i not in keep_fails:
                groups.setdefault(self.scope(self.findings[i])[0], []).append(i)
        summary = []
        for line, fs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            state = "active" if line in active else "closed"
            summary.append(f"- Line {line} ({state}): {len(fs)} more failures (e.g. {', '.join(fs[-3:])}), facts "
                           f"about that line's constructions, not about the problem")
        if summary:
            text += "\nOlder failures, grouped by line:\n" + "\n".join(summary[:8])
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
                out.append(f"- [line {self.run.line_of(p)}] {p.line()}: {short(p.intent, 140)}\n    "
                           + "\n    ".join(p.feedback[1:4] if p.valid else [p.error[:300]]))
        nb = list(dict.fromkeys([l["to"] for l in f["links"]]
                                + [i for i, g in self.findings.items() if any(l["to"] == fid for l in g["links"])]))
        if nb:
            out.append("Linked findings:")
            out += [f"- {self.finding_line(i, 200)}" for i in nb[-12:] if i in self.findings]
            if len(nb) > 12:
                out.append(f"({len(nb) - 12} more linked findings not shown)")
        return "\n".join(out)

    # ---- the lines
    def header(self, gen):
        run = self.run
        if hasattr(run, "gen_header"):          # a problem plug-in with its own wording (e.g. the VRP)
            return run.gen_header(gen)
        return (f"{run.problem_text}\n\n# Generation {gen}\nEach program gets {run.cfg.budget:.0f} s of CPU and starts "
                f"from its base's construction.\n")

    def line_block(self, ln, k, gen):
        run, a = self.run, self.run.archive
        best = a.programs.get(ln["best_id"])
        moves = run.line_moves(ln)
        out = [f"## Line {ln['id']}: {k} experiment{'s' if k > 1 else ''} this generation",
               f"Started at generation {ln['started']} from {ln['source']}. Its best: {best.id} ({best.score:.6f})."]
        if moves:
            out.append("Its best, generation by generation (against its own previous best): " + "; ".join(moves))
        ub = run.upper_bound
        if ub is not None and best.score is not None and ub > best.score:
            out.append(f"The proven upper bound is {ub:g}: up to {100 * (ub - best.score) / ub:.1f}% of the range is "
                       f"open above this line's best.")
        fb = "\n".join(f"  {l}" for l in best.feedback)
        out.append(f"### Its best program: {best.line()}\nIts result:\n{fb}\n```python\n"
                   f"{P4.clip(best.code, run.cfg.line_code_chars)}```")
        recent = [p for p in a.programs.values() if p.gen == gen - 1 and run.line_of(p) == ln["id"]]
        if recent:
            rows = []
            for p in sorted(recent, key=lambda q: q.id):
                pl = p.plan or {}
                what = (f"hypothesis: {short(pl.get('hypothesis'), 200)} | change: {short(pl.get('change'), 220)}"
                        if pl.get("hypothesis") else f"{p.role}: {short(p.intent, 200)}")
                res = "\n    ".join(p.feedback[:4] if p.valid else [p.error[:300]])
                rows.append(f"- {p.line()}\n    {what}\n    {res}")
            out.append("### Its last generation, in full\n" + "\n".join(rows))
        return "\n".join(out)

    def closed_block(self):
        closed = self.run.closed_lines()
        if not closed:
            return ""
        return "## Closed lines (their programs stay available as bases; their findings are in the map)\n" + "\n".join(
            f"- {ln['id']}: started at generation {ln['started']} from {ln['source']}, closed at generation "
            f"{ln['ended']} ({ln['why']})" for ln in closed[-8:])

    def plan(self, gen, alloc):
        run = self.run
        k = sum(alloc.values())
        lines = {ln["id"]: ln for ln in run.active_lines()}
        parts = [self.header(gen)]
        parts += [self.line_block(lines[lid], n, gen) for lid, n in alloc.items()]
        cb = self.closed_block()
        if cb:
            parts.append(cb)
        findings, shown = self.findings_view()
        parts.append(f"## Findings of the whole search ({len(self.findings)} in all, {shown} shown; status computed "
                     f"from measured results; a gain counts only above the noise floor of {run.cfg.gain_floor:g} "
                     f"relative)\n{findings}")
        base = "\n\n".join(parts)
        system = run.researcher_system(k)
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", system, base + "\n\n" + P4.NAVIGATOR_ASK.format(k=run.cfg.open_k),
                           temperature=0.4, max_tokens=800, effort="none", gen=gen)
            js = P4.extract_json(nav) or {}
            asked = [str(x).strip() for x in (js.get("open") or []) if isinstance(x, (str, int))][: run.cfg.open_k]
            why = str(js.get("why", ""))[:300]
            for item in asked:
                if item in run.archive.programs:
                    opened.append(self.open_program(item))
                elif item in self.findings:
                    opened.append(self.open_finding(item))
        user = base
        if opened:
            user += "\n\n## What you opened\n" + "\n\n".join(opened)
        allocation = ", ".join(f"{n} for line {lid}" for lid, n in alloc.items())
        user += "\n\n" + P.PLAN_FORMAT.format(k=k, allocation=allocation)
        plan, info = run.researcher(user, gen, system=system)
        info.update(opened=asked, open_why=why, allocation=alloc)
        return plan, info

    # ---- the distiller (helix4's, with each program's line)
    def update(self, gen, plan, children):
        run = self.run
        ids = sorted(self.findings, key=lambda i: int(i[1:]))
        index = "\n".join(self.finding_line(i, 220) for i in ids) or "(none yet)"
        if len(index) > 60000:      # the Distiller needs the ids and the recent ones, not all of them in full
            index = "\n".join(self.finding_line(i, 120) for i in ids[-250:])
        rows = []
        for c in children:
            pl = c.plan or {}
            what = (f"planned: {short(pl.get('hypothesis'), 240)} | change: {short(pl.get('change'), 260)} | "
                    f"predicted: {short(pl.get('prediction'), 140)} | builds on {pl.get('builds_on')}"
                    if pl.get("hypothesis") else f"{c.role}: {short(c.intent, 220)}")
            parent = run.archive.programs.get(c.parent)
            pscore = f" ({parent.score:.6f})" if parent is not None and parent.valid else ""
            rows.append(f"### [line {run.line_of(c)}] {c.line()}\n{what}\ncoder's summary: {short(c.summary, 200)}\n"
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
