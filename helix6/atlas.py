"""Atlas, reorganised around ideas (v4.6; v6 uses it too). Builds on v4.5's Atlas+ (helix5/v45.py).

What changes, and why (docs/TRACE_STUDY.md):
- A table of the kinds of change tried (each planned experiment names its kind; code counts how often each kind was
  tried, its real gains, its best gain, its inconclusive runs, when it was last tried). v4's map listed only the
  newest ~45 findings, and by generation 30 those were knob tweaks; the idea-level findings had dropped out of view.
- Key findings stay visible: the map shows the findings with the biggest measured gains of all time, then the latest.
- INCONCLUSIVE results (the start returned unchanged after the whole budget) count neither for nor against a finding.
- Each finding shows the state its evidence was tested on (code-computed), so a result on a weak construction is not
  read as a law about the best one.
- The Distiller merges into existing findings (at most 4 new ones per generation, none if nothing is new), tags each
  finding with its kind of change, and records ideas rather than settings.
- A leaner prompt: the best program's code is shown once; opened findings show their 8 latest pieces of evidence.
"""
from __future__ import annotations

from helix4.archive import short
from helix4.memory import LINK_TYPES, best_block, header
from helix5.v45 import AtlasPlus
from helix6 import prompts as P
from helix6.evaluate import GAIN_EPS, gain_label

KINDS = ("works", "fails", "mechanism", "question")


def norm_kind(s):
    return " ".join(str(s or "").lower().replace("_", " ").split())[:60]


class AtlasIdeas(AtlasPlus):
    name = "v46"

    # ---- outcomes: real gains, shared gains and inconclusive runs are told apart
    def outcome(self, p):
        if p is None:
            return "missing"
        if not p.valid:
            return "error"
        m = self.run.meta.get(p.id, {})
        if p.delta is None:
            return "fresh"
        if m.get("inconclusive"):
            return "inconclusive"
        if p.delta >= GAIN_EPS and (p.plan or {}).get("shared_gain_with"):
            return "shared"
        return "gain" if p.delta >= GAIN_EPS else "no gain"

    def status(self, f):
        outs = [self.outcome(self.run.archive.programs.get(p)) for p in f["evidence"]]
        gains, bad, inc = outs.count("gain"), outs.count("no gain") + outs.count("error"), outs.count("inconclusive")
        extra = f", {inc} inconclusive" if inc else ""
        if f["kind"] == "question":
            return ("open" if not (gains or bad) else f"tested ({gains} gained, {bad} didn't)") + extra
        if f["kind"] == "fails":
            st = "supported" if bad and not gains else "mixed" if bad and gains else "refuted" if gains else "untested"
        else:
            st = "supported" if gains and gains >= bad else "mixed" if gains else "refuted" if bad else "untested"
        return f"{st}: {gains} gained, {bad} didn't{extra}"

    def scope(self, f):
        """The state the finding's latest evidence ran on (code-computed)."""
        for pid in reversed(f["evidence"]):
            p = self.run.archive.programs.get(pid)
            if p is None or not p.valid:
                continue
            st = self.run.meta.get(pid, {}).get("state") or p.parent
            sp = self.run.archive.programs.get(st) if st else None
            if p.delta is None:
                return "from scratch"
            if sp is not None and sp.valid:
                return f"on {sp.id} ({sp.score:.6f}, N={sp.n})"
        return ""

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.5f}" if g is not None and f["kind"] != "fails" else ""
        tag = f" «{f['tag']}»" if f.get("tag") else ""
        sc = self.scope(f)
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        return (f"{fid}{tag} [{f['kind']} · {self.status(f)}{gtxt}{' · ' + sc if sc else ''}] {short(f['claim'], n)}"
                + (f" ({links})" if links else ""))

    # ---- the kinds of change, counted by code from the planned experiments
    def kinds(self, before_gen=None):
        out = {}
        for p in self.run.archive.programs.values():
            if before_gen is not None and p.gen >= before_gen:
                continue
            m = self.run.meta.get(p.id, {})
            k = norm_kind(m.get("kind"))
            if not k:
                continue
            d = out.setdefault(k, {"tried": 0, "gains": 0, "best": None, "inconclusive": 0, "failed": 0, "last": 0,
                                   "ids": []})
            d["tried"] += 1
            d["last"] = max(d["last"], p.gen)
            d["ids"].append(p.id)
            o = self.outcome(p)
            if o == "gain":
                d["gains"] += 1
            elif o == "inconclusive":
                d["inconclusive"] += 1
            elif o == "error":
                d["failed"] += 1
            if p.valid and p.delta is not None:
                d["best"] = p.delta if d["best"] is None else max(d["best"], p.delta)
        return out

    def kinds_table(self, gen, k=22):
        ks = self.kinds(before_gen=gen)
        if not ks:
            return "(no planned experiments yet)"
        rows = sorted(ks.items(), key=lambda kv: (-kv[1]["last"], -(kv[1]["best"] or -1)))
        lines = ["kind of change | tried | real gains | best gain | inconclusive | failed | last tried (gen)"]
        for name, d in rows[:k]:
            best = f"{d['best']:+.6f}" if d["best"] is not None else "-"
            lines.append(f"{name} | {d['tried']} | {d['gains']} | {best} | {d['inconclusive']} | {d['failed']} | {d['last']}")
        if len(rows) > k:
            lines.append(f"(+ {len(rows) - k} older kinds: " + ", ".join(n for n, _ in rows[k:k + 15]) + ")")
        return "\n".join(lines)

    def tags(self):
        seen = []
        for f in self.findings.values():
            t = norm_kind(f.get("tag"))
            if t and t not in seen:
                seen.append(t)
        for name in self.kinds():
            if name not in seen:
                seen.append(name)
        return seen

    # ---- the map
    def map(self, gen):
        ids = sorted(self.findings, key=lambda i: int(i[1:]))
        key = sorted([i for i in ids if self.findings[i]["kind"] in ("works", "mechanism")
                      and (self.best_gain(self.findings[i]) or 0) >= 1e-3],
                     key=lambda i: -(self.best_gain(self.findings[i]) or 0))[:8]
        recent = [i for i in ids if i not in key][-18:]
        fl = "\n".join(self.finding_line(i) for i in sorted(key, key=lambda i: int(i[1:]))) or "(none yet)"
        rl = "\n".join(self.finding_line(i) for i in recent) or "(none yet)"
        return (f"## Map 1: the tree of attempts (indent = built on the line above; [F..] = findings citing it)\n"
                f"{self.tree(gen)}\n\n## Map 2: the kinds of change tried so far (counted by code from the planned "
                f"experiments)\n{self.kinds_table(gen)}\n\n## Map 3: findings ({len(self.findings)} in all), status "
                f"computed from measured results\nKey findings (the biggest measured gains):\n{fl}\nLatest findings:\n{rl}"
                f"\n\n## The last generation, in full\n{self.window(gen)}")

    def window(self, gen):
        last = [p for p in self.run.archive.programs.values() if p.gen == gen - 1]
        if not last:
            return "(none yet)"
        out = []
        for p in sorted(last, key=lambda q: q.id):
            pl = p.plan or {}
            m = self.run.meta.get(p.id, {})
            where = self.run.state_note(p)
            if pl.get("hypothesis") or pl.get("change"):
                what = (f"kind: {m.get('kind') or '-'} | {m.get('seconds', self.run.cfg.budget):.0f} s | hypothesis: "
                        f"{short(pl.get('hypothesis'), 200)} | change: {short(pl.get('change'), 220)} | predicted: "
                        f"{short(pl.get('prediction'), 120)}")
            else:
                what = f"mutation: {short(p.intent, 200)}"
            res = "\n    ".join(p.feedback[:5] if p.valid else [p.error[:300]] + p.feedback[1:2])
            coder = f"\n    coder: {short(p.summary, 160)}" if p.summary and p.summary != p.intent else ""
            out.append(f"- {p.line()}{where}\n    {what}{coder}\n    {res}")
        return "\n".join(out)

    # ---- opening items (no duplicated code; evidence lists capped)
    def open_program(self, pid):
        best = self.run.archive.best()
        text = super().open_program(pid)
        if pid == best.id and "Code:\n```python" in text:
            head, rest = text.split("Code:\n```python", 1)
            after = rest.split("```", 1)[1] if "```" in rest else ""
            text = head + "Code: (shown above, as the best program)" + after
        return text

    def open_finding(self, fid):
        f = self.findings[fid]
        if len(f["evidence"]) <= 8:
            return super().open_finding(fid)
        full = f["evidence"]
        try:
            f["evidence"] = full[-8:]
            text = super().open_finding(fid)
        finally:
            f["evidence"] = full
        return text.replace("Evidence:", f"Evidence (the latest 8 of {len(full)}):", 1)

    # ---- its own recent reasoning, with what came of each bet
    def recent_reasoning(self, gen, k=3):
        import json
        path = self.run.dir / "plans.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
        rows = [r for r in rows if gen - k <= r["gen"] < gen]
        if not rows:
            return ""
        by_eid = {p.plan.get("eid"): p for p in self.run.archive.programs.values() if p.plan and p.plan.get("eid")}
        out = ["## Your recent reasoning, and what came of it"]
        for r in rows:
            pl = r.get("plan") or {}
            out.append(f"### Generation {r['gen']}\nYou wrote: {short(pl.get('analysis'), 700)}")
            for e in r.get("experiments", []):
                p = by_eid.get(e.get("eid"))
                st = "from scratch" if e.get("fresh") else f"on {e.get('state')}"
                res = "(no result)" if p is None else self.result_text(p)
                out.append(f"- {p.id if p else '?'} [{e.get('kind') or '-'}, {e.get('seconds', 30):.0f} s] {e.get('base')} {st}: "
                           f"bet: {short(e.get('hypothesis'), 160)}\n  if it gains: {short(e.get('if_gain'), 120)} | "
                           f"if not: {short(e.get('if_not'), 120)}\n  -> {res}")
        return "\n".join(out)

    def result_text(self, p):
        if not p.valid:
            return f"FAILED: {short(p.error, 140)}"
        if p.delta is None:
            return f"{p.score:.6f} (fresh start)"
        if self.run.meta.get(p.id, {}).get("inconclusive"):
            return f"{p.score:.6f} (INCONCLUSIVE: unchanged after its whole budget)"
        return f"{p.score:.6f} ({p.delta:+.6f}, {gain_label(p.delta)})"

    # ---- planning
    def plan(self, gen):
        run = self.run
        total, lo = run.cfg.deep_seconds, run.cfg.min_seconds
        system = P.RESEARCHER46_SYSTEM.format(k=run.cfg.deep, total=total, lo=lo)
        base = (header(run, gen) + "\n" + best_block(run) + "\n\n" + run.progress_block(gen) + "\n\n" + self.map(gen))
        rr = self.recent_reasoning(gen)
        if rr:
            base += "\n\n" + rr
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", system, base + "\n\n" + P.NAVIGATOR46_ASK.format(k=run.cfg.open_k),
                           temperature=0.4, max_tokens=800, effort="none", gen=gen)
            js = P.extract_json(nav) or {}
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
        user += "\n\n" + P.PLAN46_FORMAT.format(k=run.cfg.deep, total=total, lo=lo)
        plan, info = run.researcher(system, user, gen)
        info.update(opened=asked, open_why=why, tail=run.tail_status(gen))
        return plan, info

    # ---- the Distiller: merge first, tag, ideas over settings, never count inconclusive runs as failures
    def update(self, gen, plan, children):
        run = self.run
        index = "\n".join(self.finding_line(i, 220) for i in self.findings) or "(none yet)"
        rows = []
        for c in children:
            pl = c.plan or {}
            m = run.meta.get(c.id, {})
            what = (f"planned [{m.get('kind') or '-'}, {m.get('seconds', run.cfg.budget):.0f} s]: "
                    f"{short(pl.get('hypothesis'), 240)} | change: {short(pl.get('change'), 260)} | predicted: "
                    f"{short(pl.get('prediction'), 140)}") if (pl.get("hypothesis") or pl.get("change")) else \
                (f"continued for {m.get('seconds', run.cfg.budget):.0f} s more (same code)" if c.role == "continue"
                 else f"wide-loop mutation: {short(c.intent, 220)}")
            res = c.feedback[:6] if c.valid else [c.error[:300]] + c.feedback[1:2]
            rows.append(f"### {c.line()}{run.state_note(c)}\n{what}\ncoder's summary: {short(c.summary, 200)}\nresult:\n  "
                        + "\n  ".join(res) + (f"\ndiff from its base:\n```diff\n{P.clip(c.diff, 1500)}\n```" if c.diff else ""))
        tags = ", ".join(self.tags()[:40]) or "(none yet)"
        user = (f"{run.problem.TITLE}\n\n## Findings so far\n{index}\n\n## The researcher's analysis this generation\n"
                f"{short((plan or {}).get('analysis'), 900)}\n\n## Generation {gen}: every program and its result\n"
                + "\n\n".join(rows) + "\n\n" + P.DISTILLER46_ASK.format(gen=gen, tags=tags))
        reply = run.call("distiller", P.DISTILLER46_SYSTEM, user, temperature=0.3, max_tokens=3000, effort="none", gen=gen)
        js = P.extract_json(reply) or {}
        known = run.archive.programs
        added = 0
        for nf in (js.get("new") or [])[:4]:
            if not isinstance(nf, dict):
                continue
            ev = [str(p) for p in (nf.get("evidence") or []) if str(p) in known]
            kind = nf.get("kind") if nf.get("kind") in KINDS else "mechanism"
            claim = " ".join(str(nf.get("claim") or "").split())[:400]
            if not claim or (not ev and kind != "question"):
                continue
            if kind == "fails" and ev and all(run.meta.get(p, {}).get("inconclusive") for p in ev):
                kind = "question"           # an untested idea is not a failed one
            links = [{"to": str(l.get("to")), "type": l.get("type")} for l in (nf.get("links") or [])
                     if isinstance(l, dict) and str(l.get("to")) in self.findings and l.get("type") in LINK_TYPES]
            fid = f"F{len([e for e in self.events if e['op'] == 'new']) + 1}"
            self._append({"op": "new", "id": fid, "gen": gen, "kind": kind, "tag": norm_kind(nf.get("tag")),
                          "claim": claim, "evidence": ev, "links": links})
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

    def scheduled(self, gen, plan, exps):
        pass

    def stats(self):
        st = super().stats()
        st["kinds"] = len(self.kinds())
        return st
