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

DEFAULT_STOP = "3 experiments without a real gain"
DUE_AFTER = 3

KINDS = ("works", "fails", "mechanism", "conjecture")
# words that make a statement a claim about the problem's limits (optimum, ceiling, impossibility, closed form)
LIMIT_WORDS = re.compile(r"\b(optimal|optimum|optimality|maximum|supremum|ceiling|upper bound|best possible|"
                         r"impossible|global(ly)? (optimum|maximum|optimal)|closed[- ]form|true max)\b", re.I)
ITEM_OPS = ("add", "revise", "done", "park", "drop", "reopen", "branch")


def outcome(p):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "fresh"
    if p.delta >= GAIN_EPS and (p.plan or {}).get("shared_gain_with"):
        return "shared"          # siblings with different changes got the same score: not evidence for this change
    return "gain" if p.delta >= GAIN_EPS else "no gain"


def result_text(p):
    if p is None:
        return "(not run)"
    if not p.valid:
        return f"FAILED: {short(p.error, 160)}"
    if p.delta is None:
        return f"{p.score:.6f} (fresh start)"
    return f"{p.score:.6f} ({p.delta:+.6f} on its start, {gain_label(p.delta)}{shared_note(p)})"


def shared_note(p):
    sw = (p.plan or {}).get("shared_gain_with")
    return f"; the same score as {', '.join(sw)}: shared code, not this change" if sw else ""


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
        ver = {k: ev.get(k) for k in ("gen", "step", "op", "purpose", "plan", "stop", "outcome", "why", "from")}
        if op in ("add", "branch"):
            self.items[iid] = {"id": iid, "purpose": ev.get("purpose", ""), "plan": ev.get("plan", ""), "status": "open",
                               "stop": ev.get("stop") or DEFAULT_STOP, "outcome": "", "created_gen": ev["gen"],
                               "created_step": ev["step"], "from": ev.get("from"),
                               "touched": [ev["step"]] if ev["step"] != "system" else [], "versions": [ver]}
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
        if ev["step"] != "system" and ev["step"] not in it["touched"]:
            it["touched"].append(ev["step"])

    def _apply_belief(self, ev):
        op = ev["op"]
        if op == "summary":
            self.summaries.append(ev)
            return
        bid = ev["id"]
        ver = {k: ev.get(k) for k in ("gen", "step", "op", "kind", "statement", "confidence", "evidence", "add_evidence",
                                      "refuted_if", "challenge_outcome", "why")}
        if op == "add":
            self.beliefs[bid] = {"id": bid, "kind": ev.get("kind", "mechanism"), "statement": ev.get("statement", ""),
                                 "confidence": ev.get("confidence", "medium"), "evidence": list(ev.get("evidence") or []),
                                 "refuted_if": ev.get("refuted_if", ""), "challenges": [], "active": True, "versions": [ver]}
            return
        b = self.beliefs.get(bid)
        if b is None:
            return
        if op == "revise":
            for k in ("statement", "confidence", "refuted_if", "kind"):
                if ev.get(k):
                    b[k] = ev[k]
            b["evidence"] += [p for p in (ev.get("add_evidence") or []) if p not in b["evidence"]]
            if ev.get("challenge_outcome") in ("held", "failed"):
                b["challenges"].append({"gen": ev["gen"], "outcome": ev["challenge_outcome"], "why": ev.get("why", "")})
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

    def effective_confidence(self, b):
        """Conjectures stay at low confidence until they have survived two challenges."""
        if b["kind"] == "conjecture" and sum(1 for c in b["challenges"] if c["outcome"] == "held") < 2:
            return "low"
        return b["confidence"]

    def challenged_by(self, bid):
        return [p for p in self.run.archive.programs.values() if p.plan and p.plan.get("challenges") == bid]

    def belief_line(self, b, n=260):
        parts = [b["kind"], f"{self.effective_confidence(b)} confidence"]
        if b["kind"] in ("works", "fails"):
            parts.append(self.belief_status(b))
        ch = self.challenged_by(b["id"])
        held = sum(1 for c in b["challenges"] if c["outcome"] == "held")
        failed = sum(1 for c in b["challenges"] if c["outcome"] == "failed")
        parts.append(f"challenged {len(ch)}x" + (f" (held {held}, failed {failed})" if ch or b["challenges"] else ""))
        parts.append(f"version {len(b['versions'])}")
        line = f"{b['id']} [{' · '.join(parts)}] {short(b['statement'], n)} (evidence: {', '.join(b['evidence'][:6]) or 'none'})"
        if b.get("refuted_if"):
            line += f"\n      refuted if: {short(b['refuted_if'], 200)}"
        return line

    def challenge_candidates(self):
        """Active mechanisms and conjectures, least challenged and most confident first."""
        rank = {"high": 0, "medium": 1, "low": 2}
        act = [b for b in self.beliefs.values() if b["active"] and b["kind"] in ("mechanism", "conjecture")]
        return sorted(act, key=lambda b: (len(self.challenged_by(b["id"])), rank.get(b["confidence"], 1), b["id"]))

    def adjust_roles(self, gen, roles):
        """Every `challenge_every` rounds, the explore slot (or the last slot) becomes a challenge of a belief, if any
        mechanism or conjecture has not been challenged yet."""
        every = self.run.cfg.challenge_every
        if gen > 1 and every and gen % every == 0 and any(not self.challenged_by(b["id"]) for b in self.challenge_candidates()):
            i = len(roles) - 1 - roles[::-1].index("explore") if "explore" in roles else len(roles) - 1
            roles = list(roles)
            roles[i] = "challenge"
        return roles

    def thread_stats(self, it):
        ps = sorted([p for p in self.run.archive.programs.values() if p.plan and p.plan.get("item") == it["id"]
                     and p.role == "deep"], key=lambda p: (p.gen, p.id))
        gains = [p for p in ps if p.valid and ((p.delta is not None and p.delta >= GAIN_EPS)
                                               or (p.delta is None and p.score is not None and p.score >= self.line_best(p)))]
        since = 0
        for p in reversed(ps):
            if p in gains:
                break
            since += 1
        ok = [p for p in ps if p.valid]
        return {"n": len(ps), "gains": len(gains), "since_gain": since, "due": since >= DUE_AFTER,
                "best": max(ok, key=lambda p: p.score) if ok else None}

    def line_best(self, p):
        """For a fresh start (no delta): it counts as a gain only if it beats every program made before it."""
        before = [q.score for q in self.run.archive.valid() if q.gen < p.gen]
        return max(before) if before else 0

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
        out = ["## Your agenda (threads)"]
        opened = [it for it in self.items.values() if it["status"] == "open"]
        due = []
        for it in opened:
            st = self.thread_stats(it)
            flag = ""
            if st["due"]:
                due.append(it["id"])
                flag = (f"  <- DUE: {st['since_gain']} experiments without a real gain; close it (done), revise it with "
                        f"a genuinely new approach, or park it this round, or the system parks it")
            out.append(f"{it['id']} [open, since gen {it['created_gen']}, {st['n']} experiments, {st['gains']} real gains"
                       + (f", best {st['best'].score:.6f} ({st['best'].id})" if st["best"] else "")
                       + f", version {len(it['versions'])}]{flag}"
                       f"\n   question: {short(it['purpose'], 260)}\n   plan: {short(it['plan'], 420)}"
                       f"\n   stop: {short(it.get('stop') or DEFAULT_STOP, 160)}")
        if not opened:
            out.append("(no open items)")
        closed = [it for it in self.items.values() if it["status"] != "open"][-8:]
        for it in closed:
            out.append(f"{it['id']} [{it['status']}] {short(it['purpose'], 120)}"
                       + (f" -> {short(it['outcome'], 140)}" if it["outcome"] else ""))
        self._due_shown = due
        return "\n".join(out)

    def exp_lines(self, step, full=True, fb=6):
        out = []
        for e, eid in zip(step.get("exps", []), step.get("eids", [])):
            p = self.program_of(eid)
            tag = " [fresh start]" if e.get("fresh") else ""
            if full:
                ch = f" challenging {e.get('challenges')}" if e.get("challenges") else ""
                out.append(f"- {p.id if p else '?'} ({e.get('role', '?')}{ch}) for {e.get('item')} on {e.get('base')}{tag}: "
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
        slots, roles = run.portfolio_block(gen)
        if "challenge" in roles:
            cands = [b for b in self.challenge_candidates()][:4]
            slots += "\nBeliefs to challenge (least tested first): " + "; ".join(
                f"{b['id']} ({b['kind']}, challenged {len(self.challenged_by(b['id']))}x): {short(b['statement'], 140)}" for b in cands)
        parts.append(slots)
        return "\n\n".join(parts), focus, linked, roles

    def auto_park(self, gen):
        """Threads shown as due in the last round and left untouched by it are parked by their stop rule."""
        order = sorted((s for s in self.steps.values() if s["kind"] == "round"), key=lambda s: int(s["id"][1:]))
        if not order:
            return []
        last = order[-1]
        parked = []
        for iid in last.get("due_shown") or []:
            it = self.items.get(iid)
            if it is None or it["status"] != "open" or not self.thread_stats(it)["due"]:
                continue
            later = {sid for sid in self.steps if int(sid[1:]) >= int(last["id"][1:])}
            if any(v.get("step") in later for v in it["versions"]):
                continue                                             # the researcher acted on it (round or review)
            ev = {"op": "park", "id": iid, "gen": gen, "step": "system",
                  "why": f"stopped by its stop rule ({it.get('stop') or DEFAULT_STOP}); it was due and left untouched"}
            self._append("agenda", ev)
            self._apply_item(ev)
            parked.append(iid)
        return parked

    def plan(self, gen):
        run = self.run
        info = {}
        if gen >= run.cfg.review_every and gen % run.cfg.review_every == 0 and self.steps:
            info["review"] = self.review(gen)
        parked = self.auto_park(gen)
        if parked:
            info["auto_parked"] = parked
        system = P.RESEARCHER5_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget)
        self._due_shown = []
        ctx, focus, linked, roles = self.context(gen)
        due_shown = list(self._due_shown)
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
        user += "\n\n" + P.DECISION5_FORMAT.format(k=run.cfg.deep, roles=", ".join(roles), first_role=roles[0])
        plan, rinfo = run.researcher(system, user, gen)
        info.update(rinfo)
        info.update(lookups=asked, focus=focus, continuity=linked, stall=stall, roles=roles)
        if plan is None:
            return None, info
        plan["_lookups"] = asked
        plan["_due_shown"] = due_shown
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
            ch = str(e.get("challenges") or "").split()[0] if e.get("challenges") else ""
            e = {**e, "item": item, "step": step_id}
            if ch in self.beliefs:
                e["challenges"] = ch
            else:
                e.pop("challenges", None)
            exps.append(e)
        # a challenge slot must name a belief: if the researcher didn't, the least-tested one is named for it
        if "challenge" in roles:
            i = roles.index("challenge")
            cands = self.challenge_candidates()
            if i < len(exps) and not exps[i].get("challenges") and cands:
                exps[i]["challenges"] = cands[0]["id"]
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
        # refs ("n1") name items added in this same reply: give them their ids first, so that any text mentioning
        # them (plans, experiments) can be rewritten to the real ids
        nxt = int(self.next_id("A", self.items)[1:])
        for op in js.get("agenda") or []:
            if isinstance(op, dict) and op.get("op") in ("add", "branch") and (op.get("question") or op.get("purpose")):
                op["_id"] = f"A{nxt}"                      # every add gets its id up front: no collisions
                nxt += 1
                if op.get("ref"):
                    refmap[str(op["ref"])] = op["_id"]

        def sub(t):
            t = "" if t is None else str(t)
            for r, iid in refmap.items():
                t = re.sub(rf"\b{re.escape(r)}\b", iid, t)
            return t

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
                purpose = short(op.get("question") or op.get("purpose"), 600)
                if not purpose:
                    rejected.append("agenda add without a question")
                    continue
                ev["stop"] = short(op.get("stop"), 200) or DEFAULT_STOP
                iid = op.get("_id") or self.next_id("A", self.items)
                ev.update(id=iid, purpose=sub(purpose), plan=short(sub(op.get("plan")), 1200),
                          **({"from": op["from"]} if kindop == "branch" else {}))
                applied.append(f"{kindop} {iid}: {short(purpose, 100)}")
            else:
                iid = str(op.get("id"))
                if iid not in self.items:
                    rejected.append(f"{kindop} unknown item {iid}")
                    continue
                if kindop == "revise":
                    q = op.get("question") or op.get("purpose")
                    if not (op.get("plan") or q):
                        rejected.append(f"revise {iid} with nothing to change")
                        continue
                    ev.update(plan=short(sub(op.get("plan")), 1200), purpose=short(sub(q), 600),
                              stop=short(op.get("stop"), 200) if op.get("stop") else None)
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
                bkind = op.get("kind") if op.get("kind") in KINDS else "mechanism"
                refuted_if = short(op.get("refuted_if"), 300)
                if LIMIT_WORDS.search(st) and bkind != "conjecture":
                    bkind = "conjecture"                 # a claim about a limit is a conjecture, whatever it was called
                    refuted_if = refuted_if or "a construction that does better than this statement says is possible"
                    applied.append(f"(filed as a conjecture: a claim about the problem's limits)")
                if bkind in ("mechanism", "conjecture") and not refuted_if:
                    rejected.append(f"belief '{short(st, 60)}': a {bkind} must say what would refute it (refuted_if)")
                    continue
                if bkind in ("works", "fails") and not ev_ids:
                    rejected.append(f"belief '{short(st, 60)}': an observation must cite the programs that show it")
                    continue
                bid = self.next_id("B", self.beliefs)
                ev.update(id=bid, statement=st, kind=bkind, confidence=str(op.get("confidence") or "medium")[:10],
                          evidence=ev_ids, refuted_if=refuted_if)
                applied.append(f"belief {bid} ({bkind}): {short(st, 100)}")
            else:
                bid = str(op.get("id"))
                if bid not in self.beliefs:
                    rejected.append(f"{op['op']} unknown belief {bid}")
                    continue
                ev["id"] = bid
                if op["op"] == "revise":
                    st = short(op.get("statement"), 500) if op.get("statement") else None
                    ev.update(statement=st, confidence=str(op.get("confidence"))[:10] if op.get("confidence") else None,
                              add_evidence=[str(p) for p in (op.get("add_evidence") or []) if str(p) in known],
                              refuted_if=short(op.get("refuted_if"), 300) if op.get("refuted_if") else None,
                              challenge_outcome=op.get("challenge_outcome") if op.get("challenge_outcome") in ("held", "failed") else None)
                    if st and LIMIT_WORDS.search(st) and self.beliefs[bid]["kind"] != "conjecture":
                        ev["kind"] = "conjecture"
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
        for e in js.get("experiments") or []:
            if isinstance(e, dict):
                for k in ("hypothesis", "change", "prediction", "if_gain", "if_not"):
                    if e.get(k):
                        e[k] = sub(e[k])
        step = {"op": "step", "id": step_id, "gen": gen, "kind": kind, "focus": focus, "follows": follows,
                "declared": declared, "thinking": short(sub(js.get("thinking")), 3000), "gist": short(sub(js.get("gist")), 300),
                "applied": applied, "rejected": rejected, "lookups": js.get("_lookups", []),
                "due_shown": js.get("_due_shown", []), "came_back": js.get("came_back") if isinstance(js.get("came_back"), list) else []}
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
              "exps": [{k: e.get(k) for k in ("item", "role", "challenges", "base", "fresh", "hypothesis", "change",
                                              "prediction", "if_gain", "if_not")} for e in exps]}
        self._append("notebook", ev)
        s = self.steps[step_id]
        s["eids"], s["exps"] = ev["eids"], ev["exps"]
        for e in exps:
            it = self.items.get(e["item"])
            if it is not None and step_id not in it["touched"]:
                it["touched"].append(step_id)

    def review(self, gen):
        run = self.run
        self._due_shown = []
        agenda = self.agenda_block()
        due = list(self._due_shown)
        closed = [it for it in self.items.values() if it["status"] != "open"]
        beliefs = [self.belief_line(b) + ("" if b["active"] else " [DROPPED]") for b in self.beliefs.values()]
        recent = sorted(self.steps.values(), key=lambda s: int(s["id"][1:]))[-10:]
        lines = run.lines()
        user = (f"{run.problem.TITLE}\n\n{run.progress_block(gen)}\nLines so far: {len(lines)}\n\n{agenda}\n"
                + (f"(and {len(closed)} closed threads in all)\n" if closed else "")
                + "\n## Your whole theory\n" + ("\n".join(beliefs) or "(empty)")
                + (f"\nCurrent summary: {self.summaries[-1]['text']}" if self.summaries else "")
                + "\n\n## Your last steps\n" + "\n".join(self.step_gist(s) for s in recent)
                + "\n\n" + P.REVIEW_ASK.format())
        system = P.RESEARCHER5_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget)
        js, rinfo = run.researcher(system, user, gen, max_tokens=8000, role="review", need=None)
        if not js:
            return {"ok": False}
        js["_due_shown"] = due
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
