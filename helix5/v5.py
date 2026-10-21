"""v5: the researcher. One continuing researcher with a theory, an agenda and a notebook, all versioned.

The design (docs/IDEAS.md, "The next build"; docs/V5_DESIGN.md):

- **Theory** (beliefs.jsonl): beliefs about what governs the score, each citing the programs that are its evidence.
  Code shows the measured outcome of every cited program and computes each belief's status; the model's claim alone
  never counts. A short theory summary is rewritten at each step-back review (every version kept).
- **Agenda** (agenda.jsonl): the purposes being pursued, each with a plan that says what to do depending on results.
  Every experiment belongs to an agenda item: every run has a purpose.
- **Notebook** (notebook.jsonl): one step per round (or review): the reasoning, a self-contained one-line gist, the
  operations applied, the experiments scheduled, and the earlier steps it builds on.
- **Versioned, never rewritten**: theory and agenda change only through explicit operations (add, revise, done, park,
  drop, reopen, branch), each with its reason, stored as events. The current state is the replay; every earlier
  version and every branch stays reachable through lookups. Untouched items stay word for word, so they cannot drift.
- **Constructed continuity**: when results come back, the researcher is put back at the steps that matter to them:
  the step that scheduled them, the steps that created and last revised the agenda items they belong to, and the
  steps those declared they build on. Links are recorded when a step is written (most of them by code: which step
  scheduled what, which step touched which item), so continuity never depends on a search succeeding. Near steps
  are shown in full, far ones as their gist (the fisheye).
- **Explicit lookups**: before deciding, the researcher may open steps, agenda items or beliefs with their full
  version history, programs, or search everything by words.
- **Step back** every `review_every` rounds: a review of the whole agenda and theory (prune, merge, close, reopen,
  correct), with a new theory summary.
- **Interrupts**: when the memoryless wide loop sets a new record, the round opens with it.
"""
from __future__ import annotations

import json
import re

from helix4.archive import short
from helix4.memory import best_block, header
from helix5 import prompts as P
from helix5.evaluate import GAIN_EPS, gain_label
from helix5.run import STALL_EPS

KINDS = ("works", "fails", "mechanism")
ITEM_OPS = ("add", "revise", "done", "park", "drop", "reopen", "branch")


def outcome(p):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "fresh"
    return "gain" if p.delta >= GAIN_EPS else "no gain"


def result_text(p):
    if p is None:
        return "(not run)"
    if not p.valid:
        return f"FAILED: {short(p.error, 160)}"
    if p.delta is None:
        return f"{p.score:.6f} (fresh start)"
    return f"{p.score:.6f} ({p.delta:+.6f} on its start, {gain_label(p.delta)})"


def jl(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


class Researcher:
    name = "v5"

    def __init__(self, run):
        self.run = run
        self.paths = {k: run.dir / f"{k}.jsonl" for k in ("notebook", "agenda", "beliefs")}
        self.events = {k: jl(p) for k, p in self.paths.items()}
        self.rebuild()

    # =========================================================================== the store
    def _append(self, kind, ev):
        self.events[kind].append(ev)
        with self.paths[kind].open("a") as f:
            f.write(json.dumps(ev) + "\n")

    def rebuild(self):
        self.steps, self.items, self.beliefs, self.summaries = {}, {}, {}, []
        for ev in self.events["notebook"]:
            if ev["op"] == "step":
                self.steps[ev["id"]] = {**ev, "eids": [], "exps": []}
            elif ev["op"] == "scheduled" and ev["step"] in self.steps:
                self.steps[ev["step"]]["eids"] = ev["eids"]
                self.steps[ev["step"]]["exps"] = ev["exps"]
                for e in ev["exps"]:
                    it = self.items.get(e.get("item"))
                    if it is not None and ev["step"] not in it["touched"]:
                        it["touched"].append(ev["step"])
            # items/beliefs are replayed in step order below
        for ev in self.events["agenda"]:
            self._apply_item(ev)
        for ev in self.events["beliefs"]:
            self._apply_belief(ev)
        # touched-by-scheduling needs items to exist: second pass
        for ev in self.events["notebook"]:
            if ev["op"] == "scheduled":
                for e in ev["exps"]:
                    it = self.items.get(e.get("item"))
                    if it is not None and ev["step"] not in it["touched"]:
                        it["touched"].append(ev["step"])
        for it in self.items.values():
            it["touched"].sort(key=lambda s: int(s[1:]))

    def _apply_item(self, ev):
        op, iid = ev["op"], ev["id"]
        ver = {k: ev.get(k) for k in ("gen", "step", "op", "purpose", "plan", "outcome", "why", "from")}
        if op in ("add", "branch"):
            self.items[iid] = {"id": iid, "purpose": ev.get("purpose", ""), "plan": ev.get("plan", ""), "status": "open",
                               "outcome": "", "created_gen": ev["gen"], "created_step": ev["step"], "from": ev.get("from"),
                               "touched": [ev["step"]], "versions": [ver]}
            return
        it = self.items.get(iid)
        if it is None:
            return
        if op == "revise":
            if ev.get("plan"):
                it["plan"] = ev["plan"]
            if ev.get("purpose"):
                it["purpose"] = ev["purpose"]
        elif op == "done":
            it["status"], it["outcome"] = "done", ev.get("outcome", "")
        elif op == "park":
            it["status"] = "parked"
        elif op == "drop":
            it["status"] = "dropped"
        elif op == "reopen":
            it["status"] = "open"
        it["versions"].append(ver)
        if ev["step"] not in it["touched"]:
            it["touched"].append(ev["step"])

    def _apply_belief(self, ev):
        op = ev["op"]
        if op == "summary":
            self.summaries.append(ev)
            return
        bid = ev["id"]
        ver = {k: ev.get(k) for k in ("gen", "step", "op", "statement", "confidence", "evidence", "add_evidence", "why")}
        if op == "add":
            self.beliefs[bid] = {"id": bid, "kind": ev.get("kind", "mechanism"), "statement": ev.get("statement", ""),
                                 "confidence": ev.get("confidence", "medium"), "evidence": list(ev.get("evidence") or []),
                                 "active": True, "versions": [ver]}
            return
        b = self.beliefs.get(bid)
        if b is None:
            return
        if op == "revise":
            for k in ("statement", "confidence"):
                if ev.get(k):
                    b[k] = ev[k]
            b["evidence"] += [p for p in (ev.get("add_evidence") or []) if p not in b["evidence"]]
        elif op == "drop":
            b["active"] = False
        b["versions"].append(ver)

    def next_id(self, prefix, existing):
        n = max([int(k[1:]) for k in existing] + [0])
        return f"{prefix}{n + 1}"

    # =========================================================================== views
    def program_of(self, eid):
        for p in self.run.archive.programs.values():
            if p.plan and p.plan.get("eid") == eid:
                return p
        return None

    def belief_status(self, b):
        outs = [outcome(self.run.archive.programs.get(p)) for p in b["evidence"]]
        gains, bad = outs.count("gain"), outs.count("no gain") + outs.count("error")
        if b["kind"] == "fails":
            st = "supported" if bad and not gains else "mixed" if bad and gains else "contradicted" if gains else "untested"
        else:
            st = "supported" if gains and gains >= bad else "mixed" if gains else "contradicted" if bad else "untested"
        return f"{st}: {gains} gained, {bad} didn't"

    def belief_line(self, b, n=260):
        return (f"{b['id']} [{b['kind']} · {b['confidence']} confidence · {self.belief_status(b)} · version "
                f"{len(b['versions'])}] {short(b['statement'], n)} (evidence: {', '.join(b['evidence'][:6]) or 'none'})")

    def theory_block(self):
        act = [b for b in self.beliefs.values() if b["active"]]
        out = ["## Your theory"]
        if self.summaries:
            s = self.summaries[-1]
            out.append(f"Summary (version {len(self.summaries)}, written at gen {s['gen']}): {s['text']}")
        out += [self.belief_line(b) for b in act] or ["(no beliefs yet)"]
        dropped = len(self.beliefs) - len(act)
        if dropped:
            out.append(f"({dropped} dropped beliefs; look them up by id to see them)")
        return "\n".join(out)

    def item_results(self, it):
        ps = [p for p in self.run.archive.programs.values() if p.plan and p.plan.get("item") == it["id"]]
        return ps

    def agenda_block(self):
        out = ["## Your agenda"]
        opened = [it for it in self.items.values() if it["status"] == "open"]
        for it in opened:
            ps = self.item_results(it)
            ok = [p for p in ps if p.valid]
            best = max(ok, key=lambda p: p.score) if ok else None
            out.append(f"{it['id']} [open, since gen {it['created_gen']}, {len(ps)} experiments"
                       + (f", best {best.score:.6f} ({best.id})" if best else "") + f", version {len(it['versions'])}]"
                       f"\n   purpose: {short(it['purpose'], 260)}\n   plan: {short(it['plan'], 420)}")
        if not opened:
            out.append("(no open items)")
        closed = [it for it in self.items.values() if it["status"] != "open"][-8:]
        for it in closed:
            out.append(f"{it['id']} [{it['status']}] {short(it['purpose'], 120)}"
                       + (f" -> {short(it['outcome'], 140)}" if it["outcome"] else ""))
        return "\n".join(out)

    def exp_lines(self, step, full=True, fb=6):
        out = []
        for e, eid in zip(step.get("exps", []), step.get("eids", [])):
            p = self.program_of(eid)
            tag = " [fresh start]" if e.get("fresh") else ""
            if full:
                out.append(f"- {p.id if p else '?'} for {e.get('item')} on {e.get('base')}{tag}: "
                           f"{short(e.get('hypothesis'), 200)}\n    change: {short(e.get('change'), 260)}\n"
                           f"    predicted: {short(e.get('prediction'), 140)} | if it gains: {short(e.get('if_gain'), 140)}"
                           f" | if not: {short(e.get('if_not'), 140)}\n    -> {result_text(p)}")
                if p is not None and p.feedback and fb:
                    out.append("       " + "\n       ".join(l for l in p.feedback[1:1 + fb]))
            else:
                out.append(f"- {p.id if p else '?'} ({e.get('item')}): {short(e.get('hypothesis'), 90)} -> {result_text(p)}")
        return out

    def step_full(self, s, fb=6):
        head = f"### {s['id']} (gen {s['gen']}, {s['kind']}" + (f", on {', '.join(s.get('focus') or [])}" if s.get("focus") else "") + ")"
        out = [head, f"You thought: {short(s.get('thinking'), 1400)}", f"Gist: {s.get('gist')}"]
        ops = s.get("applied") or []
        if ops:
            out.append("You changed: " + "; ".join(short(o, 160) for o in ops))
        lines = self.exp_lines(s, full=True, fb=fb)
        if lines:
            out.append("You scheduled, and what came back:")
            out += lines
        return "\n".join(out)

    def step_gist(self, s):
        return f"{s['id']} (gen {s['gen']}" + (f", {', '.join(s.get('focus') or [])}" if s.get("focus") else "") + f"): {s.get('gist')}"

    # =========================================================================== constructed continuity
    def continuity(self, gen, max_full=4, max_gist=12):
        """The steps this round continues from: chosen by links recorded at write time, never by a search."""
        if not self.steps:
            return [], [], []
        order = sorted(self.steps.values(), key=lambda s: int(s["id"][1:]))
        last = order[-1]
        last_round = next((s for s in reversed(order) if s["kind"] == "round"), last)
        focus = []
        for e in last_round.get("exps", []):
            if e.get("item") and e["item"] not in focus:
                focus.append(e["item"])
        full = [last_round["id"]]
        if last["id"] != last_round["id"]:
            full.append(last["id"])                                  # a review that happened after it
        for iid in focus:
            it = self.items.get(iid)
            if not it:
                continue
            for sid in reversed(it["touched"]):                      # the latest steps that touched this item
                if sid not in full and len(full) < max_full:
                    full.append(sid)
                    break
        gists = []
        for sid in full:
            for f in self.steps[sid].get("follows", []):
                if f in self.steps and f not in full and f not in gists:
                    gists.append(f)
        for iid in focus:
            it = self.items.get(iid)
            if it:
                for sid in [it["created_step"]] + it["touched"]:
                    if sid in self.steps and sid not in full and sid not in gists:
                        gists.append(sid)
        gists = sorted(gists, key=lambda s: -int(s[1:]))[:max_gist]
        return full, sorted(gists, key=lambda s: int(s[1:])), focus

    def continuity_block(self, gen):
        full, gists, focus = self.continuity(gen)
        if not full:
            return "## Where you are\nThis is your first round: nothing has been tried yet.", focus, []
        out = ["## Where you are: the steps this round continues from (chosen by their links to what came back)"]
        for iid in focus:
            it = self.items.get(iid)
            if it:
                out.append(f"You were working on {iid} ({it['status']}): {short(it['purpose'], 200)}\n   your plan: "
                           f"{short(it['plan'], 400)}")
        for sid in sorted(full, key=lambda s: int(s[1:])):
            # the step whose results just came back gets full feedback; older linked steps a short version
            out.append(self.step_full(self.steps[sid], fb=6 if sid == full[0] else 2))
        if gists:
            out.append("Earlier steps these build on (gists; look any up in full):")
            out += [self.step_gist(self.steps[s]) for s in gists]
        recent = sorted(self.steps.values(), key=lambda s: int(s["id"][1:]))[-6:]
        out.append("Your most recent steps, for orientation: " + " | ".join(f"{s['id']}: {short(s.get('gist'), 90)}" for s in recent))
        return "\n".join(out), focus, full + gists

    def wide_block(self, gen):
        prev = [p for p in self.run.archive.programs.values() if p.gen == gen - 1 and p.role == "wide"]
        if not prev:
            return ""
        hist = [h for h in self.run.history() if h["gen"] < gen - 1]
        record = max([h["best"] for h in hist] or [0])
        out = ["## The memoryless mutation loop, last generation"]
        for p in sorted(prev, key=lambda q: q.id):
            flag = ""
            if p.valid and p.score >= record + STALL_EPS:
                flag = "  <- INTERRUPT: a new record from the mutation loop; consider what it means for your agenda"
            out.append(f"- {p.id} from {p.parent}: {short(p.intent, 160)} -> {result_text(p)}{flag}")
        return "\n".join(out)

    # =========================================================================== lookups
    def lookup(self, q):
        q = q.strip()
        if q.lower().startswith("search:"):
            return self.search(q[7:].strip())
        if q in self.steps:
            s = self.steps[q]
            extra = f"\nIt builds on: {', '.join(s.get('follows') or []) or 'nothing'}"
            return self.step_full(s) + extra
        if q in self.items:
            it = self.items[q]
            out = [f"### {q} [{it['status']}] purpose: {it['purpose']}\nCurrent plan: {it['plan']}"
                   + (f"\nOutcome: {it['outcome']}" if it["outcome"] else "") + (f"\nBranched from {it['from']}" if it.get("from") else ""),
                   "Version history:"]
            for v in it["versions"]:
                out.append(f"- gen {v['gen']} {v['step']} {v['op']}: " + "; ".join(
                    f"{k}={short(v[k], 200)}" for k in ("purpose", "plan", "outcome", "why") if v.get(k)))
            ps = self.item_results(it)
            if ps:
                out.append("Its experiments: " + "; ".join(f"{p.id} {result_text(p)}" for p in ps[-10:]))
            return "\n".join(out)
        if q in self.beliefs:
            b = self.beliefs[q]
            out = [self.belief_line(b, 1000) + ("" if b["active"] else " [DROPPED]"), "Version history:"]
            for v in b["versions"]:
                out.append(f"- gen {v['gen']} {v['step']} {v['op']}: " + "; ".join(
                    f"{k}={short(v[k], 200)}" for k in ("statement", "confidence", "evidence", "add_evidence", "why") if v.get(k)))
            out.append("Evidence, measured: " + "; ".join(f"{p} {result_text(self.run.archive.programs.get(p))}" for p in b["evidence"]))
            return "\n".join(out)
        if q in self.run.archive.programs:
            return self.open_program(q)
        return f"{q}: nothing with that id."

    def open_program(self, pid):
        a = self.run.archive
        p = a.programs[pid]
        out = [f"### {p.line()}"]
        if p.plan:
            out.append(f"Planned ({p.plan.get('item')}, step {p.plan.get('step')}): {short(p.plan.get('hypothesis'), 300)} | change: "
                       f"{short(p.plan.get('change'), 400)}")
        else:
            out.append(f"Intent: {p.intent}")
        if p.summary:
            out.append(f"Coder's summary: {p.summary}")
        out.append("Result:\n  " + "\n  ".join(p.feedback[:9] if p.valid else [p.error] + p.feedback[1:3]))
        if p.diff:
            out.append(f"Diff from {p.parent}:\n```diff\n{P.clip(p.diff, 1800)}\n```")
        out.append(f"Code:\n```python\n{P.clip(p.code, 3500)}```")
        kids = [q for q in a.programs.values() if q.parent == pid]
        if kids:
            out.append("Its children: " + "; ".join(f"{q.id} {result_text(q)}" for q in kids[:12]))
        return "\n".join(out)

    def search(self, text, k=8):
        words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}
        if not words:
            return "search: no words to search for."
        docs = []
        for s in self.steps.values():
            docs.append((s["id"], f"{s.get('gist')} {s.get('thinking')}", self.step_gist(s)))
        for it in self.items.values():
            docs.append((it["id"], f"{it['purpose']} {it['plan']} {it['outcome']}", f"{it['id']} [{it['status']}] {short(it['purpose'], 150)}"))
        for b in self.beliefs.values():
            docs.append((b["id"], b["statement"], self.belief_line(b, 150)))
        for p in self.run.archive.programs.values():
            pl = p.plan or {}
            docs.append((p.id, f"{p.intent} {p.summary} {pl.get('change', '')}", f"{p.id}: {short(p.intent, 120)} -> {result_text(p)}"))
        scored = []
        for did, body, line in docs:
            toks = set(re.findall(r"[a-z0-9]+", str(body).lower()))
            hit = len(words & toks)
            if hit:
                scored.append((hit, did, line))
        scored.sort(key=lambda x: (-x[0], x[1]))
        if not scored:
            return f"search '{text}': nothing found."
        return f"search '{text}':\n" + "\n".join(f"- {line}" for _, _, line in scored[:k])

    # =========================================================================== one round
    def context(self, gen):
        run = self.run
        cont, focus, linked = self.continuity_block(gen)
        parts = [header(run, gen), best_block(run), run.progress_block(gen), self.theory_block(), self.agenda_block(), cont]
        wb = self.wide_block(gen)
        if wb:
            parts.append(wb)
        return "\n\n".join(parts), focus, linked

    def plan(self, gen):
        run = self.run
        info = {}
        if gen >= run.cfg.review_every and gen % run.cfg.review_every == 0 and self.steps:
            info["review"] = self.review(gen)
        system = P.RESEARCHER5_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget)
        ctx, focus, linked = self.context(gen)
        answers, asked = [], []
        if self.steps or run.archive.programs and gen > 1:
            reply = run.call("lookup", system, ctx + "\n\n" + P.LOOKUP_ASK.format(k=run.cfg.lookup_k),
                             temperature=0.4, max_tokens=800, effort="none", gen=gen)
            js = P.extract_json(reply) or {}
            asked = [str(x).strip() for x in (js.get("lookups") or []) if isinstance(x, (str, int))][: run.cfg.lookup_k]
            answers = [self.lookup(q) for q in asked]
        user = ctx
        if answers:
            user += "\n\n## What you looked up\n" + "\n\n".join(answers)
        stall = run.stall(gen)
        rule = P.ESCAPE_RULE.format(stall=stall) if stall >= run.cfg.stall_gens else ""
        user += "\n\n" + P.DECISION5_FORMAT.format(k=run.cfg.deep, rule=rule)
        plan, rinfo = run.researcher(system, user, gen)
        info.update(rinfo)
        info.update(lookups=asked, focus=focus, continuity=linked, stall=stall)
        if plan is None:
            return None, info
        plan["_lookups"] = asked
        step_id, applied, rejected, refmap = self.apply_step(gen, "round", plan, focus)
        exps = []
        open_ids = [i for i, it in self.items.items() if it["status"] == "open"]
        for e in plan.get("experiments") or []:
            if not isinstance(e, dict):
                continue
            item = str(e.get("item", "")).split()[0] if e.get("item") else ""
            item = refmap.get(item, item)
            if item not in self.items or self.items[item]["status"] != "open":
                item = self.default_item(gen, step_id, focus, open_ids)
            exps.append({**e, "item": item, "step": step_id})
        plan["experiments"] = exps
        plan["analysis"] = plan.get("thinking", "")
        info.update(step=step_id, applied=applied, rejected=rejected)
        return plan, info

    def default_item(self, gen, step_id, focus, open_ids):
        for iid in focus + open_ids:
            if iid in self.items and self.items[iid]["status"] == "open":
                return iid
        iid = self.next_id("A", self.items)
        self._append("agenda", {"op": "add", "id": iid, "gen": gen, "step": step_id,
                                "purpose": "Raise the score (created by the system: an experiment named no open agenda item)",
                                "plan": "Improve the best construction.", "why": "no agenda item given"})
        self._apply_item(self.events["agenda"][-1])
        return iid

    def apply_step(self, gen, kind, js, focus):
        """Validate and apply the operations of a decision or review; write the notebook step. Returns
        (step id, applied lines, rejected lines, ref map for items added in this step)."""
        step_id = self.next_id("S", self.steps)
        applied, rejected, refmap = [], [], {}
        for op in js.get("agenda") or []:
            if not isinstance(op, dict) or op.get("op") not in ITEM_OPS:
                rejected.append(f"agenda op {short(op, 80)}")
                continue
            kindop = op["op"]
            ev = {"op": kindop, "gen": gen, "step": step_id, "why": short(op.get("why"), 400)}
            if kindop in ("add", "branch"):
                if kindop == "branch" and op.get("from") not in self.items:
                    rejected.append(f"branch from unknown {op.get('from')}")
                    continue
                purpose = short(op.get("purpose"), 600)
                if not purpose:
                    rejected.append("agenda add without a purpose")
                    continue
                iid = self.next_id("A", self.items)
                ev.update(id=iid, purpose=purpose, plan=short(op.get("plan"), 1200), **({"from": op["from"]} if kindop == "branch" else {}))
                if op.get("ref"):
                    refmap[str(op["ref"])] = iid
                applied.append(f"{kindop} {iid}: {short(purpose, 100)}")
            else:
                iid = str(op.get("id"))
                if iid not in self.items:
                    rejected.append(f"{kindop} unknown item {iid}")
                    continue
                if kindop == "revise":
                    if not (op.get("plan") or op.get("purpose")):
                        rejected.append(f"revise {iid} with nothing to change")
                        continue
                    ev.update(plan=short(op.get("plan"), 1200), purpose=short(op.get("purpose"), 600))
                if kindop == "done":
                    ev["outcome"] = short(op.get("outcome"), 600)
                ev["id"] = iid
                applied.append(f"{kindop} {iid}" + (f": {short(op.get('outcome') or op.get('plan'), 100)}" if op.get('outcome') or op.get('plan') else ""))
            self._append("agenda", ev)
            self._apply_item(ev)
        known = self.run.archive.programs
        for op in js.get("beliefs") or []:
            if not isinstance(op, dict) or op.get("op") not in ("add", "revise", "drop"):
                rejected.append(f"belief op {short(op, 80)}")
                continue
            ev = {"op": op["op"], "gen": gen, "step": step_id, "why": short(op.get("why"), 400)}
            if op["op"] == "add":
                st = short(op.get("statement"), 500)
                ev_ids = [str(p) for p in (op.get("evidence") or []) if str(p) in known]
                if not st:
                    rejected.append("belief add without a statement")
                    continue
                bid = self.next_id("B", self.beliefs)
                ev.update(id=bid, statement=st, kind=op.get("kind") if op.get("kind") in KINDS else "mechanism",
                          confidence=str(op.get("confidence") or "medium")[:10], evidence=ev_ids)
                applied.append(f"belief {bid}: {short(st, 100)}")
            else:
                bid = str(op.get("id"))
                if bid not in self.beliefs:
                    rejected.append(f"{op['op']} unknown belief {bid}")
                    continue
                ev["id"] = bid
                if op["op"] == "revise":
                    ev.update(statement=short(op.get("statement"), 500) if op.get("statement") else None,
                              confidence=str(op.get("confidence"))[:10] if op.get("confidence") else None,
                              add_evidence=[str(p) for p in (op.get("add_evidence") or []) if str(p) in known])
                applied.append(f"{op['op']} {bid}")
            self._append("beliefs", ev)
            self._apply_belief(ev)
        if js.get("summary"):
            ev = {"op": "summary", "gen": gen, "step": step_id, "text": short(js["summary"], 1200)}
            self._append("beliefs", ev)
            self._apply_belief(ev)
            applied.append("new theory summary")
        declared = [str(s) for s in (js.get("follows") or []) if str(s) in self.steps]
        auto = []
        order = sorted(self.steps, key=lambda s: int(s[1:]))
        if order:
            auto.append(order[-1])                                    # the previous step, always
        for iid in focus:
            it = self.items.get(iid)
            if it:
                prior = [s for s in it["touched"] if s != step_id and s in self.steps]
                if prior:
                    auto.append(prior[-1])
        follows = list(dict.fromkeys(auto + declared))
        step = {"op": "step", "id": step_id, "gen": gen, "kind": kind, "focus": focus, "follows": follows,
                "declared": declared, "thinking": short(js.get("thinking"), 3000), "gist": short(js.get("gist"), 300),
                "applied": applied, "rejected": rejected, "lookups": js.get("_lookups", [])}
        self._append("notebook", step)
        self.steps[step_id] = {**step, "eids": [], "exps": []}
        for iid in set(focus):
            if iid in self.items and step_id not in self.items[iid]["touched"]:
                self.items[iid]["touched"].append(step_id)
        return step_id, applied, rejected, refmap

    def scheduled(self, gen, plan, exps):
        step_id = (plan or {}).get("experiments", [{}])[0].get("step") if plan and plan.get("experiments") else None
        if step_id is None or step_id not in self.steps:
            # the planner's reply was unusable: record a step so the experiments still have a place in the notebook
            step_id, _, _, _ = self.apply_step(gen, "round", {"thinking": "(no usable decision this round)",
                                                               "gist": "no usable decision; fallback experiments"}, [])
            item = self.default_item(gen, step_id, [], [i for i, it in self.items.items() if it["status"] == "open"])
            for e in exps:
                e.update(item=item, step=step_id)
        for e in exps:
            e.setdefault("step", step_id)
            if e.get("item") not in self.items:
                e["item"] = self.default_item(gen, step_id, [], [i for i, it in self.items.items() if it["status"] == "open"])
        ev = {"op": "scheduled", "gen": gen, "step": step_id, "eids": [e["eid"] for e in exps],
              "exps": [{k: e.get(k) for k in ("item", "base", "fresh", "forced_escape", "hypothesis", "change", "prediction",
                                              "if_gain", "if_not")} for e in exps]}
        self._append("notebook", ev)
        s = self.steps[step_id]
        s["eids"], s["exps"] = ev["eids"], ev["exps"]
        for e in exps:
            it = self.items.get(e["item"])
            if it is not None and step_id not in it["touched"]:
                it["touched"].append(step_id)

    def review(self, gen):
        run = self.run
        allitems = []
        for it in self.items.values():
            ps = self.item_results(it)
            allitems.append(f"{it['id']} [{it['status']}, {len(ps)} experiments, version {len(it['versions'])}] "
                            f"purpose: {short(it['purpose'], 220)} | plan: {short(it['plan'], 300)}"
                            + (f" | outcome: {short(it['outcome'], 200)}" if it["outcome"] else ""))
        beliefs = [self.belief_line(b) + ("" if b["active"] else " [DROPPED]") for b in self.beliefs.values()]
        recent = sorted(self.steps.values(), key=lambda s: int(s["id"][1:]))[-10:]
        user = (f"{run.problem.TITLE}\n\n{run.progress_block(gen)}\n\n## Your whole agenda\n" + ("\n".join(allitems) or "(empty)")
                + "\n\n## Your whole theory\n" + ("\n".join(beliefs) or "(empty)")
                + (f"\nCurrent summary: {self.summaries[-1]['text']}" if self.summaries else "")
                + "\n\n## Your last steps\n" + "\n".join(self.step_gist(s) for s in recent)
                + "\n\n" + P.REVIEW_ASK.format())
        system = P.RESEARCHER5_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget)
        js, rinfo = run.researcher(system, user, gen, max_tokens=6000, role="review", need=None)
        if not js:
            return {"ok": False}
        sid, applied, rejected, _ = self.apply_step(gen, "review", js, [])
        return {"ok": True, "step": sid, "applied": applied, "rejected": rejected, "seconds": rinfo.get("seconds")}

    def update(self, gen, plan, children):
        return {"steps": len(self.steps), "open_items": sum(1 for it in self.items.values() if it["status"] == "open")}

    def truncate(self, gen_done):
        for k in self.events:
            self.events[k] = [e for e in self.events[k] if e.get("gen", 0) <= gen_done]
            self.paths[k].write_text("".join(json.dumps(e) + "\n" for e in self.events[k]))
        self.rebuild()

    def stats(self):
        st = [it["status"] for it in self.items.values()]
        return {"steps": len(self.steps), "reviews": sum(1 for s in self.steps.values() if s["kind"] == "review"),
                "items_open": st.count("open"), "items_done": st.count("done"), "items_parked": st.count("parked"),
                "items_dropped": st.count("dropped"), "beliefs": sum(1 for b in self.beliefs.values() if b["active"]),
                "belief_versions": sum(len(b["versions"]) for b in self.beliefs.values()),
                "item_versions": sum(len(it["versions"]) for it in self.items.values())}
