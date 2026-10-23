"""v4.7's Atlas: helix4's Atlas (helix4/memory.py) with the false-ceiling fixes of docs/V47_DESIGN.md.

- Gains have a noise floor (fix 4): a change counts as a gain only if it beats its start by more than `gain_floor`
  (relative). v4 counted +1e-9, so polishing kept "succeeding" and its findings stayed "supported".
- Failures are scoped and the map is balanced (fix 3). A failure is a fact about the construction it was tried on,
  so each "fails" finding is shown with that construction, and the map groups failures by construction instead of
  listing the newest 45 (at generation 140 of the v4 run, all 45 findings on the map were failures, many reading
  "the point is confirmed saturated"). The map always keeps the best "works" and "mechanism" findings and the open
  questions.
- The lineage of the best program shows the steps that gained, and counts the rest (v4 showed rows of "+0.00000").
- The header has no countdown ("Generation 140", not "of 150"), and states the honest room left when the problem
  has a proven bound (ac2: R <= 1 by Hoelder, which the problem text already says).
- Opening a finding shows its 12 newest pieces of evidence, not all of them (v4's opened items reached 262,000
  characters of a 311,000-character prompt).
- The challenger line gets its own view (challenger_view): its line, the shared findings, and no overall record.
"""
from __future__ import annotations

import json
from collections import Counter

from helix4 import prompts as P4
from helix4.archive import short
from helix4.memory import Atlas, LINK_TYPES, KINDS
from helix47 import prompts as P

DISTILLER_EXTRA = (" A failure is a fact about the construction it was tried on: say which (its base program and "
                   "score), and don't generalise it to the whole problem.")


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

    # ---- statuses with the noise floor
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
        """The construction a finding was tested on: the most common base of its evidence (id, score), or None."""
        a = self.run.archive
        bases = [a.programs[p].parent for p in f["evidence"] if p in a.programs and a.programs[p].parent]
        if not bases:
            return None
        pid = Counter(bases).most_common(1)[0][0]
        p = a.programs.get(pid)
        return (pid, p.score if p is not None and p.valid else None)

    def basin_key(self, f):
        sc = self.scope(f)
        if sc is None or sc[1] is None:
            return None
        return f"{sc[1]:.4f}"

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.5f}" if g is not None and f["kind"] != "fails" else ""
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        where = ""
        if f["kind"] == "fails":
            sc = self.scope(f)
            if sc is not None:
                where = f" · tried on {sc[0]}'s construction" + (f" ({sc[1]:.6f})" if sc[1] is not None else "")
        return f"{fid} [{f['kind']} · {self.status(f)}{gtxt}{where}] {short(f['claim'], n)}" + (f" ({links})" if links else "")

    # ---- the balanced map
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
        if rest > 0:      # room left: more of the newest works, then questions
            more = [i for i in reversed(works) if i not in keep_works][:rest]
            keep_works += more
        shown = sorted(set(keep_works + keep_q + keep_fails), key=lambda i: int(i[1:]))
        lines = [self.finding_line(i) for i in shown]
        hidden_fails = [i for i in fails if i not in keep_fails]
        groups = {}
        for i in hidden_fails:
            groups.setdefault(self.basin_key(self.findings[i]), []).append(i)
        summary = []
        for key, fs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            gens = [self.findings[i]["gen"] for i in fs]
            where = f"the construction scoring {key}" if key else "various constructions"
            summary.append(f"- {len(fs)} more failures tried on {where} (generations {min(gens)}-{max(gens)}; e.g. "
                           f"{', '.join(fs[-3:])}): facts about that construction, not about the problem")
        text = "\n".join(lines) or "(none yet)"
        if summary:
            text += "\nOlder failures, grouped by the construction they were tried on:\n" + "\n".join(summary[:8])
        return text, len(shown)

    def map(self, gen):
        findings, shown = self.findings_view()
        return (f"## Map 1: the tree of attempts (indent = built on the line above; [F..] = findings citing it)\n"
                f"{self.tree(gen)}\n\n## Map 2: findings ({len(self.findings)} in all, {shown} shown; status computed "
                f"from measured results; a gain counts only above the noise floor of {self.run.cfg.gain_floor:g} "
                f"relative)\n{findings}\n\n## The last generation, in full\n{self.window(gen)}")

    def open_finding(self, fid):
        f = self.findings[fid]
        a = self.run.archive
        out = [f"### {self.finding_line(fid, 1000)}", "Evidence:"]
        ev = f["evidence"]
        k = self.run.cfg.open_evidence
        if len(ev) > k:
            out.append(f"({len(ev) - k} older pieces of evidence not shown)")
        for pid in ev[-k:]:
            p = a.programs.get(pid)
            if p:
                out.append(f"- {p.line()}: {short(p.intent, 140)}\n    " + "\n    ".join(
                    (p.feedback[1:4] if p.valid else [p.error[:300]])))
        nb = [l["to"] for l in f["links"]] + [i for i, g in self.findings.items() if any(l["to"] == fid for l in g["links"])]
        nb = list(dict.fromkeys(nb))
        if nb:
            out.append("Linked findings:")
            out += [f"- {self.finding_line(i, 200)}" for i in nb[-12:] if i in self.findings]
            if len(nb) > 12:
                out.append(f"({len(nb) - 12} more linked findings not shown)")
        return "\n".join(out)

    # ---- the header and the best program
    def header(self, gen):
        run = self.run
        txt = (f"{run.problem_text}\n\n# Generation {gen}\nEach program gets {run.cfg.budget:.0f} s of CPU and starts from "
               f"its base's construction.\n")
        ub = getattr(run, "upper_bound", None)
        best = run.archive.best()
        if ub is not None and best is not None and best.score is not None and ub > best.score:
            txt += (f"The proven upper bound is {ub:g}; the best score so far is {best.score:.6f}, so up to "
                    f"{100 * (ub - best.score) / ub:.1f}% of the range is still open.\n")
        return txt

    def lineage_gains(self, pid, depth=40):
        a = self.run.archive
        steps = a.lineage(pid, depth=depth)
        parts, flat = [], 0
        for p in steps:
            if p.score is None:
                continue
            if p.parent and p.delta is not None and outcome(p, self.run.cfg) != "gain":
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
        return (f"## The best program so far: {b.id} (score {b.score:.6f})\n"
                f"The steps that built it (gains only): {self.lineage_gains(b.id)}\nIts result:\n{fb}\n"
                f"```python\n{P4.clip(b.code, 14000)}```")

    # ---- planning (the main line)
    def plan(self, gen, k=None, stalled=0):
        run = self.run
        k = k or run.cfg.deep
        base = self.header(gen) + "\n" + self.best_block() + "\n\n" + self.map(gen)
        if run.line is not None:
            base += f"\n\n{run.line_summary()}"
        opened, why, asked = [], "", []
        system = P.RESEARCHER_SYSTEM.format(k=k, budget=run.cfg.budget)
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
        step = stalled >= run.cfg.stall_gens and k >= 2
        user += "\n\n" + P.PLAN_FORMAT.format(
            k=k, findings=" or findings", step_field=P.STEP_FIELD if step else "",
            step_rule=P.STEP_RULE.format(stalled=stalled, step_gain=f"{run.cfg.step_gain:g} relative",
                                         mult=run.cfg.step_budget_mult) if step else "")
        plan, info = run.researcher(user, gen, system=system)
        info.update(opened=asked, open_why=why, step_asked=step)
        return plan, info

    # ---- the challenger's view
    def challenger_view(self, gen, line, options=None):
        run = self.run
        a = run.archive
        out = [f"{run.problem_text}\n\n# Generation {gen}: challenger line {line['id']}"]
        progs = [p for p in a.programs.values() if (p.plan or {}).get("line") == line["id"]]
        if progs:
            best = a.programs.get(line["best_id"])
            out.append(f"## Your line so far ({len(progs)} programs since generation {line['started']}); its best: "
                       f"{best.id} {best.score:.6f}" if best else "## Your line so far")
            for p in sorted(progs, key=lambda q: q.id)[-12:]:
                res = "; ".join((p.feedback[:2] if p.valid else [p.error[:200]]))
                out.append(f"- {p.line()}: {short(p.intent, 160)}\n    {res}")
            if best is not None:
                fb = "\n".join(f"  {l}" for l in best.feedback)
                out.append(f"## Your line's best program: {best.id}\nIts result:\n{fb}\n```python\n"
                           f"{P4.clip(best.code, 9000)}```")
        if options:
            out.append(P.CHALLENGER_START.format(options="\n".join(options)))
        findings, _ = self.findings_view(limit=run.cfg.challenger_findings)
        out.append(f"## What the whole search has learned (findings; failures name the construction they were tried "
                   f"on)\n{findings}")
        return "\n\n".join(out)

    # ---- the distiller (helix4's, with the scoping sentence)
    def update(self, gen, plan, children):
        run = self.run
        index = "\n".join(self.finding_line(i, 220) for i in self.findings) or "(none yet)"
        if len(index) > 60000:      # the Distiller needs the ids, not the whole history in full
            index = "\n".join(self.finding_line(i, 120) for i in sorted(self.findings, key=lambda i: int(i[1:]))[-250:])
        rows = []
        for c in children:
            pl = c.plan or {}
            what = (f"planned: {short(pl.get('hypothesis'), 240)} | change: {short(pl.get('change'), 260)} | "
                    f"predicted: {short(pl.get('prediction'), 140)} | builds on {pl.get('builds_on')}") if pl.get("hypothesis") else \
                f"{c.role}: {short(c.intent, 220)}"
            parent = run.archive.programs.get(c.parent)
            pscore = f" ({parent.score:.6f})" if parent is not None and parent.valid else ""
            rows.append(f"### {c.line()}\n{what}\ncoder's summary: {short(c.summary, 200)}\n"
                        f"its base {c.parent}{pscore}: {short(parent.intent, 120) if parent else '-'}\nresult:\n  "
                        + "\n  ".join((c.feedback[:6] if c.valid else [c.error[:300]] + c.feedback[1:2]))
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
