"""What the Researcher sees of the past: the one thing that differs between the three conditions.

- Control: the standard prompt of evolution systems (AlphaEvolve-style): the best program, its feedback, and the
  strongest programs as a scoreboard. No history, no notes of its own.
- Journal (idea A, appended context): the control view plus a chronological journal, appended every generation:
  the Researcher's own analysis, each experiment's plan, what it did and what it gained, and the wide loop's
  mutations. When it grows past `journal_chars`, the oldest part is compacted by an LLM into a running summary; the
  latest generations stay verbatim.
- Atlas (idea B, structured memory, after Avy): three layers. The immutable log (every program and plan); the tree
  of attempts (who built on whom, what each change did); a graph of findings: claims written by a Distiller after
  each generation, each citing the programs that are its evidence, linked by type (refines, contradicts, requires,
  combines-with, explains). The status of a finding (supported, mixed, refuted) is computed by code from the
  measured gains of its evidence, never taken from the LLM. The Researcher navigates in two steps: it sees a map
  (the pruned tree, the findings index, and the last generation in full, the "recent window" that Avy lacked), opens
  up to 6 items, then plans.
"""
from __future__ import annotations

import json
from pathlib import Path

from helix4 import prompts as P
from helix4.archive import short

LINK_TYPES = ("refines", "contradicts", "requires", "combines-with", "explains")
KINDS = ("works", "fails", "mechanism", "question")


# ---------------------------------------------------------------------------------------------- shared views
def program_header(p):
    return p.line()


def best_block(run):
    b = run.archive.best()
    fb = "\n".join(f"  {l}" for l in b.feedback)
    return (f"## The best program so far: {b.id} (score {b.score:.6f})\n"
            f"Its lineage: {run.archive.lineage_line(b.id)}\nIts result:\n{fb}\n"
            f"```python\n{P.clip(b.code, 9000)}```")


def scoreboard(run, k=6):
    lines = [f"- {p.line()}: {short(p.intent, 110)}" for p in run.archive.ranked()[:k]]
    return "## The strongest programs (any program can be a base)\n" + "\n".join(lines)


def header(run, gen):
    return (f"{run.problem.DESCRIPTION}\n\n# Generation {gen} of {run.cfg.gens}\n"
            f"Each program gets {run.cfg.budget:.0f} s of CPU and starts from its base's construction.\n")


def result_lines(p, k=4):
    if not p.valid:
        return [p.error[:300]] + [l for l in p.feedback[1:2]]
    return p.feedback[:k]


def outcome(p):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "seed"
    return "gain" if p.delta > 1e-9 else "no gain"


class Memory:
    name = "base"

    def __init__(self, run):
        self.run = run

    def plan(self, gen):
        """Returns (plan dict or None, info dict)."""
        user = self.context(gen) + "\n\n" + P.PLAN_FORMAT.format(k=self.run.cfg.deep, findings="")
        return self.run.researcher(user, gen, step="plan")

    def context(self, gen):
        return header(self.run, gen) + "\n" + best_block(self.run) + "\n\n" + scoreboard(self.run)

    def update(self, gen, plan, children):
        pass

    def truncate(self, gen_done):
        pass

    def stats(self):
        return {}


class Control(Memory):
    name = "control"


# ---------------------------------------------------------------------------------------------- journal
class Journal(Memory):
    name = "journal"

    def __init__(self, run):
        super().__init__(run)
        self.path = run.dir / "journal.jsonl"
        self.sum_path = run.dir / "journal_summary.json"
        self.entries = [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()] if self.path.exists() else []
        self.summary = json.loads(self.sum_path.read_text()) if self.sum_path.exists() else {"upto_gen": 0, "text": "", "compactions": 0}

    def view(self):
        recent = [e for e in self.entries if e["gen"] > self.summary["upto_gen"]]
        parts = []
        if self.summary["text"]:
            parts.append(f"### Summary of generations 1-{self.summary['upto_gen']} (compacted)\n{self.summary['text']}")
        parts += [e["text"] for e in recent]
        return "\n\n".join(parts) if parts else "(empty: this is the first generation)"

    def context(self, gen):
        return (super().context(gen) + "\n\n## Your research journal: your own analyses and every result so far, "
                "oldest first\n" + self.view())

    def entry(self, gen, plan, children):
        out = [f"### Generation {gen}"]
        if plan and plan.get("analysis"):
            out.append(f"Your analysis then: {short(plan['analysis'], 900)}")
        deep = [c for c in children if c.role == "deep"]
        wide = [c for c in children if c.role == "wide"]
        if deep:
            out.append("Your experiments:")
            for c in deep:
                pl = c.plan or {}
                res = "; ".join(result_lines(c, 4)[1:] if c.valid else result_lines(c))
                score = f"{c.score:.6f} ({c.delta:+.6f} on its start)" if c.valid and c.delta is not None else "FAILED"
                out.append(f"- {c.id} from {c.parent}: hypothesis: {short(pl.get('hypothesis'), 220)} | change: "
                           f"{short(pl.get('change'), 260)} | predicted: {short(pl.get('prediction'), 120)}\n"
                           f"  -> {score}. {short(res, 360)} | coder: {short(c.summary, 160)}")
        if wide:
            out.append("Mutations from the wide loop (no plan):")
            for c in wide:
                score = f"{c.score:.6f} ({c.delta:+.6f})" if c.valid and c.delta is not None else f"FAILED: {short(c.error, 120)}"
                out.append(f"- {c.id} from {c.parent}: {short(c.intent, 200)} -> {score}")
        return "\n".join(out)

    def update(self, gen, plan, children):
        e = {"gen": gen, "text": self.entry(gen, plan, children)}
        self.entries.append(e)
        with self.path.open("a") as f:
            f.write(json.dumps(e) + "\n")
        if len(self.view()) > self.run.cfg.journal_chars:
            self.compact(gen)

    def compact(self, gen):
        keep = self.run.cfg.journal_keep
        old = [e for e in self.entries if self.summary["upto_gen"] < e["gen"] <= gen - keep]
        if not old:
            return
        text = (f"Earlier summary:\n{self.summary['text']}\n\n" if self.summary["text"] else "") + "\n\n".join(e["text"] for e in old)
        limit = self.run.cfg.journal_summary_chars
        reply = self.run.call("compactor", P.COMPACTOR_SYSTEM, P.COMPACTOR_ASK.format(chars=limit, text=text),
                              temperature=0.3, max_tokens=3000, effort="none", gen=gen)
        new = (reply or "").strip()
        if not new:          # no model: keep the first line of each result, mechanically
            new = "\n".join(l for l in text.splitlines() if l.startswith(("###", "- ")))
        self.summary = {"upto_gen": old[-1]["gen"], "text": new[: int(limit * 1.3)],
                        "compactions": self.summary["compactions"] + 1}
        self.sum_path.write_text(json.dumps(self.summary, indent=1))

    def truncate(self, gen_done):
        self.entries = [e for e in self.entries if e["gen"] <= gen_done]
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.entries))
        if self.summary["upto_gen"] > gen_done:
            self.summary = {"upto_gen": 0, "text": "", "compactions": self.summary["compactions"]}
            self.sum_path.write_text(json.dumps(self.summary, indent=1))

    def stats(self):
        return {"journal_chars": len(self.view()), "compactions": self.summary["compactions"],
                "summary_upto_gen": self.summary["upto_gen"]}


# ---------------------------------------------------------------------------------------------- atlas
class Atlas(Memory):
    name = "atlas"

    def __init__(self, run):
        super().__init__(run)
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
        ds = [self.run.archive.programs[p].delta for p in f["evidence"]
              if p in self.run.archive.programs and self.run.archive.programs[p].valid
              and self.run.archive.programs[p].delta is not None]
        return max(ds) if ds else None

    def citing(self, pid):
        return [fid for fid, f in self.findings.items() if pid in f["evidence"]]

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        g = self.best_gain(f)
        gtxt = f", best {g:+.5f}" if g is not None and f["kind"] != "fails" else ""
        links = "; ".join(f"{l['type']} {l['to']}" for l in f["links"])
        return f"{fid} [{f['kind']} · {self.status(f)}{gtxt}] {short(f['claim'], n)}" + (f" ({links})" if links else "")

    # ---- the map
    def tree(self, gen):
        a = self.run.archive
        include = set()
        for p in a.ranked()[:12] + [p for p in a.programs.values() if p.gen == gen - 1]:
            include |= {q.id for q in a.lineage(p.id, depth=100)}
        kids = {}
        for p in a.programs.values():
            kids.setdefault(p.parent, []).append(p)
        lines = []

        def walk(p, depth):
            cites = self.citing(p.id)
            score = f"{p.score:.6f}" + (f" ({p.delta:+.6f})" if p.delta is not None else "") if p.valid else "FAILED"
            lines.append(f"{'  ' * min(depth, 12)}{p.id} g{p.gen} {p.role}: {score}: {short(p.intent, 70)}"
                         + (f" [{', '.join(cites[:4])}]" if cites else ""))
            ch = sorted(kids.get(p.id, []), key=lambda q: -(q.score or -1))
            shown = [q for q in ch if q.id in include]
            hidden = [q for q in ch if q.id not in include]
            for q in shown:
                walk(q, depth + 1)
            if hidden:
                ok = [q for q in hidden if q.valid]
                best = f", best {max(q.score for q in ok):.6f}" if ok else ""
                lines.append(f"{'  ' * min(depth + 1, 12)}… {len(hidden)} more children ({len(hidden) - len(ok)} failed{best})")

        for root in kids.get(None, []):
            walk(root, 0)
        return "\n".join(lines)

    def window(self, gen):
        last = [p for p in self.run.archive.programs.values() if p.gen == gen - 1]
        if not last:
            return "(none yet)"
        out = []
        for p in sorted(last, key=lambda q: q.id):
            pl = p.plan or {}
            what = (f"hypothesis: {short(pl.get('hypothesis'), 200)} | change: {short(pl.get('change'), 220)} | "
                    f"predicted: {short(pl.get('prediction'), 120)}") if pl else f"mutation: {short(p.intent, 200)}"
            res = "\n    ".join(result_lines(p, 5))
            coder = f"\n    coder: {short(p.summary, 160)}" if p.summary and p.summary != p.intent else ""
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
        if p.plan:
            out.append(f"Plan: hypothesis: {p.plan.get('hypothesis')} | change: {p.plan.get('change')} | "
                       f"predicted: {p.plan.get('prediction')} | builds on: {p.plan.get('builds_on')}")
        else:
            out.append(f"Intent: {p.intent}")
        if p.summary:
            out.append(f"Coder's summary: {p.summary}")
        out.append("Result:\n  " + "\n  ".join(result_lines(p, 8)))
        if p.diff:
            out.append(f"Diff from {p.parent}:\n```diff\n{P.clip(p.diff, 2500)}\n```")
        out.append(f"Code:\n```python\n{P.clip(p.code, 4000)}```")
        kids = [q for q in a.programs.values() if q.parent == pid]
        if kids:
            out.append("Its children: " + "; ".join(
                f"{q.id} {(f'{q.delta:+.6f}' if q.valid and q.delta is not None else 'FAILED')}: {short(q.intent, 70)}" for q in kids))
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
                out.append(f"- {p.line()}: {short(p.intent, 140)}\n    " + "\n    ".join(result_lines(p, 4)[1:] if p.valid else result_lines(p)))
        nb = [l["to"] for l in f["links"]] + [i for i, g in self.findings.items() if any(l["to"] == fid for l in g["links"])]
        if nb:
            out.append("Linked findings:")
            out += [f"- {self.finding_line(i, 200)}" for i in dict.fromkeys(nb) if i in self.findings]
        return "\n".join(out)

    def plan(self, gen):
        run = self.run
        base = header(run, gen) + "\n" + best_block(run) + "\n\n" + self.map(gen)
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", P.RESEARCHER_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget),
                           base + "\n\n" + P.NAVIGATOR_ASK.format(k=run.cfg.open_k), temperature=0.4,
                           max_tokens=800, effort="none", gen=gen)
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
        user += "\n\n" + P.PLAN_FORMAT.format(k=run.cfg.deep, findings=" or findings")
        plan, info = run.researcher(user, gen, step="plan")
        info.update(opened=asked, open_why=why)
        return plan, info

    # ---- the distiller
    def update(self, gen, plan, children):
        run = self.run
        index = "\n".join(self.finding_line(i, 220) for i in self.findings) or "(none yet)"
        rows = []
        for c in children:
            pl = c.plan or {}
            what = (f"planned: {short(pl.get('hypothesis'), 240)} | change: {short(pl.get('change'), 260)} | "
                    f"predicted: {short(pl.get('prediction'), 140)} | builds on {pl.get('builds_on')}") if pl else \
                f"wide-loop mutation: {short(c.intent, 220)}"
            parent = run.archive.programs.get(c.parent)
            rows.append(f"### {c.line()}\n{what}\ncoder's summary: {short(c.summary, 200)}\n"
                        f"its base {c.parent}: {short(parent.intent, 120) if parent else '-'}\nresult:\n  "
                        + "\n  ".join(result_lines(c, 6)) + (f"\ndiff from its base:\n```diff\n{P.clip(c.diff, 1500)}\n```" if c.diff else ""))
        user = (f"{run.problem.TITLE}\n\n## Findings so far\n{index}\n\n## The researcher's analysis this generation\n"
                f"{short((plan or {}).get('analysis'), 900)}\n\n## Generation {gen}: every program and its result\n"
                + "\n\n".join(rows) + "\n\n" + P.DISTILLER_ASK.format(gen=gen))
        reply = run.call("distiller", P.DISTILLER_SYSTEM, user, temperature=0.3, max_tokens=3000, effort="none", gen=gen)
        js = P.extract_json(reply) or {}
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
            self._append({"op": "new", "id": fid, "gen": gen, "kind": kind, "claim": claim, "evidence": ev, "links": links})
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


MODES = {"control": Control, "journal": Journal, "atlas": Atlas}
