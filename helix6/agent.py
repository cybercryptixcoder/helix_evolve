"""v6: the agentic stream. One research agent runs each round and decides how the round's compute is spent.

Every round it gets the compute of one v4 generation: `units` evaluation units of `budget` seconds each (6 × 30 s).
It spends them with actions:
- experiment: a Coder changes a method (a base program) as planned; the program runs on a chosen state (any
  program's construction, or from scratch) for 1-3 units;
- mutate: k Mutator variants of a state's own program, run on that state (a halo on demand), or of a donor method
  transplanted onto it; 1 unit each;
- continue: run a program again from its own construction for 1-3 more units, with no new code, so an investment
  (a new resolution, a long schedule) can mature. In v4, 20 of 54 planned experiments in generations 21-40 ran out of
  time and their work was thrown away.
Units it leaves unspent go to mutations of the record (the halo).

It keeps, as append-only logs:
- the findings graph, the kinds-of-change table and the scoped statuses of v4.6 (helix6/atlas.py), written by the
  Distiller after every round;
- a theory: mechanisms and conjectures, each with what would refute it. Limit claims are always conjectures held at
  low confidence (v5's guard, which kept all six v4.5/v5 runs out of the textbook trap);
- threads: questions it is pursuing. Each action names its thread. A thread is DUE when its last 3 actions together
  raised the record by less than TAIL_EPS (a rate-of-return stop rule; v5's "3 experiments without a real gain" could
  not end a slow polishing tail). A due thread must be closed or revised; ignored for 2 rounds, the system parks it;
- its own last 3 decisions, with what came of each action.

One thinking call decides the round (capped, as in v5), after a non-thinking call chooses what to open (Atlas's
two-step navigation).
"""
from __future__ import annotations

import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

from helix4.archive import short
from helix4.memory import best_block, header
from helix5.v5 import LIMIT_WORDS
from helix6 import prompts as P
from helix6.atlas import AtlasIdeas
from helix6.evaluate import GAIN_EPS

ACTIONS = ("experiment", "mutate", "continue")

AGENT_SYSTEM = """You run a research programme: an evolutionary search for better programs, steered by you. Each \
round you have {units} units of compute (each {budget:.0f} s of CPU for one program) and you decide how to spend \
them. Programs and their constructions are kept forever; any program's code is a METHOD and any program's \
construction is a STATE, and any method can run on any state.

Your actions:
- experiment (1-3 units): a coder changes a method (a base program) the way you describe, and it runs on a state you \
choose (default: the best construction; "none": from scratch). Use it for an idea that needs new code. Give it the \
units it needs: a high-resolution or long-schedule idea needs 2-3 units, or it runs out of time.
- mutate (1 unit each): a memoryless mutator writes variants of a state's own program and runs them on that state: \
cheap variations around a construction. With "method", the mutator instead adapts another program's method to that \
state (a transplant).
- continue (1-3 units): run a program again, unchanged, from its own construction, for more time. Use it when a \
program ran out of time with its idea unfinished (INCONCLUSIVE, or still improving at the end), or when a new state \
(a new resolution, a fresh line) needs more polishing before it can compete. It costs no code.
Units you leave unspent go to mutations of the best program.

You keep a theory (mechanisms and conjectures, each saying what would refute it) and threads (the questions you are \
pursuing; each action names its thread). A thread is DUE when its last 3 actions (over at least 2 rounds) together \
raised the record by less than {tail}: close it with what you learned, or revise it with a genuinely different approach. A due thread you \
ignore is parked by the system.

How to spend a round: keep depth where the record is rising; when it only creeps, change the kind of move rather than \
tuning the same one: a different method on the best state, the best method on another state, a reformulation, a \
fresh line, or time for an unfinished idea. A few well-funded actions beat many starved ones.

""" + P.STRUCTURE + "\n\n" + P.EVIDENCE + "\n\n" + P.SCORE_SCALE

AGENT_FORMAT = """## Your decision for this round

Reply with one JSON object and nothing else:
```json
{{"analysis": "what came back, what you now believe, and how you are spending the round (at most 150 words)",
 "theory": [{{"op": "add", "kind": "mechanism", "statement": "...", "refuted_if": "...", "why": "..."}},
            {{"op": "revise", "id": "H2", "statement": "...", "confidence": "low|medium|high", "why": "..."}},
            {{"op": "drop", "id": "H3", "why": "..."}}],
 "threads": [{{"op": "open", "ref": "t1", "question": "...", "stop": "..."}},
             {{"op": "revise", "id": "T2", "question": "...", "why": "..."}},
             {{"op": "close", "id": "T3", "outcome": "what was learned"}}],
 "actions": [
  {{"do": "experiment", "thread": "T1 or t1", "base": "<program id>", "state": "best | <program id> | none",
    "units": 2, "kind": "<kind of change, reuse one from the table if the same>",
    "hypothesis": "...", "change": "exactly what the coder should change", "prediction": "..."}},
  {{"do": "mutate", "thread": "T2", "state": "<program id>", "method": "<optional program id>", "count": 2}},
  {{"do": "continue", "thread": "T1", "program": "<program id>", "units": 1}}
 ]}}
```
Theory and thread operations are optional ([] when nothing changes). Actions use at most {units} units in all \
(experiment and continue: 1-3 each; mutate: 1 per variant). Use ids exactly as shown."""


class Agent(AtlasIdeas):
    name = "v6"

    def __init__(self, run):
        super().__init__(run)
        self.th_path = run.dir / "threads.jsonl"
        self.hy_path = run.dir / "theory.jsonl"
        self.th_events = self._load(self.th_path)
        self.hy_events = self._load(self.hy_path)
        self.rebuild_agent()

    @staticmethod
    def _load(path):
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def _log(self, path, events, ev):
        events.append(ev)
        with path.open("a") as f:
            f.write(json.dumps(ev) + "\n")

    # ---------------------------------------------------------------- theory and threads (event logs)
    def rebuild_agent(self):
        self.threads, self.theory = {}, {}
        for ev in self.th_events:
            t = self.threads.get(ev["id"])
            if ev["op"] == "open":
                self.threads[ev["id"]] = {"id": ev["id"], "question": ev.get("question", ""), "stop": ev.get("stop", ""),
                                          "status": "open", "since": ev["gen"], "revised": ev["gen"], "version": 1,
                                          "outcome": "", "due_since": None}
            elif t is not None:
                if ev["op"] == "revise":
                    t.update({k: ev[k] for k in ("question", "stop") if ev.get(k)}, revised=ev["gen"],
                             version=t["version"] + 1, status="open", due_since=None)
                elif ev["op"] in ("close", "park"):
                    t.update(status="closed" if ev["op"] == "close" else "parked", outcome=ev.get("outcome", ""))
                elif ev["op"] == "due":
                    t["due_since"] = ev["gen"]
        for ev in self.hy_events:
            h = self.theory.get(ev["id"])
            if ev["op"] == "add":
                self.theory[ev["id"]] = {"id": ev["id"], "kind": ev["kind"], "statement": ev["statement"],
                                         "refuted_if": ev.get("refuted_if", ""), "confidence": ev.get("confidence", "low"),
                                         "status": "active", "since": ev["gen"], "version": 1}
            elif h is not None:
                if ev["op"] == "revise":
                    h.update({k: ev[k] for k in ("statement", "refuted_if", "confidence") if ev.get(k)},
                             version=h["version"] + 1)
                elif ev["op"] == "drop":
                    h["status"] = "dropped"

    def thread_programs(self, tid):
        return [p for p in self.run.archive.programs.values() if self.run.meta.get(p.id, {}).get("thread") == tid]

    def thread_stats(self, tid):
        t = self.threads[tid]
        ps = sorted(self.thread_programs(tid), key=lambda p: p.gen)
        since = [p for p in ps if p.gen >= t["revised"]]
        actions = sorted({self.run.meta.get(p.id, {}).get("action_id") for p in since if self.run.meta.get(p.id, {}).get("action_id")})
        last3 = actions[-3:]
        rise = 0.0
        for aid in last3:
            kids = [p for p in since if self.run.meta.get(p.id, {}).get("action_id") == aid and p.valid]
            r = next((self.run.meta[p.id].get("record_before") for p in kids
                      if self.run.meta.get(p.id, {}).get("record_before") is not None), None)
            top = max((p.score for p in kids), default=None)
            if r is not None and top is not None and top > r + GAIN_EPS:
                rise += top - r
        best = max((p.score for p in ps if p.valid), default=None)
        rounds = {int(a[1:].split("a")[0]) for a in last3 if a.startswith("g") and "a" in a[1:]}
        return {"actions": len(actions), "programs": len(ps), "rise_last3": rise, "best": best,
                "due": len(actions) >= 3 and len(rounds) >= 2 and rise < self.run_tail_eps()}

    def run_tail_eps(self):
        from helix6.run import TAIL_EPS
        return TAIL_EPS

    def threads_block(self, gen):
        out = ["## Your threads"]
        open_ = [t for t in self.threads.values() if t["status"] == "open"]
        for t in open_:
            s = self.thread_stats(t["id"])
            due = " · DUE: close it or revise it with a different approach" if s["due"] else ""
            best = f", best {s['best']:.6f}" if s["best"] is not None else ""
            out.append(f"{t['id']} [open since gen {t['since']}, {s['actions']} actions, {s['programs']} programs"
                       f"{best}, record rise over its last 3 actions {s['rise_last3']:+.6f}{due}]\n   question: "
                       f"{short(t['question'], 300)}\n   stop: {short(t['stop'], 160)}")
        closed = [t for t in self.threads.values() if t["status"] != "open"][-8:]
        if closed:
            out.append("Closed or parked: " + "; ".join(f"{t['id']} ({t['status']}): {short(t['question'], 80)} -> "
                                                         f"{short(t['outcome'], 120)}" for t in closed))
        if not open_ and not closed:
            out.append("(none yet: open threads for the questions you pursue)")
        return "\n".join(out)

    def theory_block(self):
        act = [h for h in self.theory.values() if h["status"] == "active"]
        if not act:
            return "## Your theory\n(empty)"
        return "## Your theory\n" + "\n".join(
            f"{h['id']} [{h['kind']} · {h['confidence']} · v{h['version']}] {short(h['statement'], 260)}"
            + (f"\n   refuted if: {short(h['refuted_if'], 200)}" if h.get("refuted_if") else "") for h in act)

    def auto_park(self, gen):
        for t in list(self.threads.values()):
            if t["status"] != "open":
                continue
            s = self.thread_stats(t["id"])
            if s["due"] and t.get("due_since") is None:
                self._log(self.th_path, self.th_events, {"op": "due", "id": t["id"], "gen": gen})
            elif s["due"] and t.get("due_since") is not None and gen - t["due_since"] >= 2:
                self._log(self.th_path, self.th_events, {"op": "park", "id": t["id"], "gen": gen,
                                                         "outcome": "parked by the system: due for 2 rounds and not acted on"})
        self.rebuild_agent()

    def apply_ops(self, gen, decision):
        refs = {}
        notes = []
        n_t = len([e for e in self.th_events if e["op"] == "open"])
        for op in (decision.get("threads") or [])[:6]:
            if not isinstance(op, dict):
                continue
            kind = op.get("op")
            if kind == "open" and op.get("question"):
                n_t += 1
                tid = f"T{n_t}"
                refs[str(op.get("ref") or tid)] = tid
                self._log(self.th_path, self.th_events, {"op": "open", "id": tid, "gen": gen,
                                                         "question": short(op["question"], 400),
                                                         "stop": short(op.get("stop") or "3 actions without a real rise", 200)})
            elif kind in ("revise", "close", "park") and str(op.get("id")) in self.threads:
                ev = {"op": kind, "id": str(op["id"]), "gen": gen}
                for k in ("question", "stop", "outcome"):
                    if op.get(k):
                        ev[k] = short(op[k], 400)
                self._log(self.th_path, self.th_events, ev)
            else:
                notes.append(f"thread op ignored: {short(json.dumps(op), 120)}")
        n_h = len([e for e in self.hy_events if e["op"] == "add"])
        for op in (decision.get("theory") or [])[:6]:
            if not isinstance(op, dict):
                continue
            kind = op.get("op")
            if kind == "add" and op.get("statement"):
                n_h += 1
                stmt = short(op["statement"], 400)
                hk = op.get("kind") if op.get("kind") in ("mechanism", "conjecture") else "mechanism"
                conf = op.get("confidence") if op.get("confidence") in ("low", "medium", "high") else "low"
                if LIMIT_WORDS.search(stmt):
                    hk, conf = "conjecture", "low"
                self._log(self.hy_path, self.hy_events, {"op": "add", "id": f"H{n_h}", "gen": gen, "kind": hk,
                                                         "statement": stmt, "confidence": conf,
                                                         "refuted_if": short(op.get("refuted_if") or "not stated", 300)})
            elif kind in ("revise", "drop") and str(op.get("id")) in self.theory:
                ev = {"op": kind, "id": str(op["id"]), "gen": gen}
                for k in ("statement", "refuted_if", "confidence"):
                    if op.get(k):
                        ev[k] = short(op[k], 400)
                if kind == "revise" and ev.get("statement") and LIMIT_WORDS.search(ev["statement"]):
                    ev["confidence"] = "low"
                self._log(self.hy_path, self.hy_events, ev)
        self.rebuild_agent()
        return refs, notes

    # ---------------------------------------------------------------- the states the agent can build on
    def states_block(self, gen, k=10):
        a = self.run.archive
        best = a.best()
        rows, seen = [], set()

        def add(p, why):
            if p is not None and p.valid and p.id not in seen and a.construction(p.id) is not None:
                seen.add(p.id)
                rows.append(f"- {p.id} {p.score:.6f} (N={p.n}, gen {p.gen}): {why}")

        add(best, "the best construction")
        for root, ps in sorted(self.run.lines(before_gen=gen).items(), key=lambda kv: -max(q.score for q in kv[1]))[:5]:
            top = max(ps, key=lambda q: q.score)
            add(top, f"best of the line started by {root}")
        for p in sorted([p for p in a.programs.values() if p.gen == gen - 1 and p.valid], key=lambda q: -q.score)[:3]:
            add(p, "from the last round")
        for p in [p for p in a.programs.values() if p.gen >= gen - 2 and self.run.meta.get(p.id, {}).get("inconclusive")]:
            add(p, "INCONCLUSIVE: its idea ran out of time (its own construction is its start's)")
        return "## States you can build on (any program id is allowed)\n" + "\n".join(rows[:k])

    def recent_decisions(self, gen, k=3):
        path = self.run.dir / "plans.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
        rows = [r for r in rows if gen - k <= r["gen"] < gen]
        if not rows:
            return ""
        out = ["## Your recent decisions, and what came of them"]
        progs = list(self.run.archive.programs.values())
        for r in rows:
            out.append(f"### Round {r['gen']}\nYou wrote: {short((r.get('plan') or {}).get('analysis'), 600)}")
            for act in r.get("experiments") or []:
                kids = [p for p in progs if self.run.meta.get(p.id, {}).get("action_id") == act.get("aid")]
                res = "; ".join(f"{p.id} {self.result_text(p)}" for p in kids) or "(no result)"
                what = act.get("do")
                if what == "experiment":
                    desc = f"experiment [{act.get('kind') or '-'}, {act.get('units')} u] {act.get('base')} on {act.get('state') or 'scratch'}: {short(act.get('hypothesis'), 140)}"
                elif what == "mutate":
                    desc = f"mutate ×{act.get('count')} on {act.get('state')}" + (f" with the method of {act.get('method')}" if act.get("method") else "")
                else:
                    desc = f"continue {act.get('program')} for {act.get('units')} u"
                out.append(f"- [{act.get('thread') or '-'}] {desc}\n  -> {res}")
        return "\n".join(out)

    # ---------------------------------------------------------------- the round
    def validate(self, gen, decision, refs):
        """Actions -> jobs, within the round's units. Unspent units go to mutations of the record."""
        a = self.run.archive
        best = a.best()
        U = self.run.cfg.units
        jobs, used = [], 0
        for i, act in enumerate((decision or {}).get("actions") or []):
            if not isinstance(act, dict) or act.get("do") not in ACTIONS:
                continue
            do = act["do"]
            thread = refs.get(str(act.get("thread")), str(act.get("thread") or ""))
            thread = thread if thread in self.threads else ""
            aid = f"g{gen}a{i}"
            if do == "experiment":
                units = clamp_int(act.get("units"), 1, 3, 1)
                if used + units > U:
                    units = U - used
                if units <= 0:
                    break
                base = a.programs.get(str(act.get("base", "")).strip())
                base = base if base is not None and base.valid and base.code.strip() else best
                st = str(act.get("state", "best")).strip()
                fresh = st.lower() in ("none", "scratch", "fresh", "null")
                state = None if fresh else a.programs.get(st)
                if not fresh and not (state is not None and state.valid and a.construction(state.id) is not None):
                    state = best
                jobs.append({"do": "experiment", "aid": aid, "thread": thread, "base": base.id,
                             "state": None if fresh else state.id, "fresh": fresh, "units": units,
                             "seconds": units * self.run.cfg.budget, "kind": " ".join(str(act.get("kind") or "").split())[:60],
                             "hypothesis": act.get("hypothesis"), "change": act.get("change"),
                             "prediction": act.get("prediction"), "builds_on": []})
                used += units
            elif do == "mutate":
                count = clamp_int(act.get("count"), 1, U, 1)
                count = min(count, U - used)
                if count <= 0:
                    break
                state = a.programs.get(str(act.get("state", "")).strip())
                state = state if state is not None and state.valid and a.construction(state.id) is not None else best
                method = a.programs.get(str(act.get("method", "")).strip()) if act.get("method") else None
                method = method if method is not None and method.valid and method.code.strip() else None
                jobs.append({"do": "mutate", "aid": aid, "thread": thread, "state": state.id,
                             "method": method.id if method else None, "count": count, "units": count})
                used += count
            elif do == "continue":
                units = clamp_int(act.get("units"), 1, 3, 1)
                units = min(units, U - used)
                if units <= 0:
                    break
                prog = a.programs.get(str(act.get("program", "")).strip())
                if prog is None or not prog.valid or not prog.code.strip() or a.construction(prog.id) is None:
                    continue
                jobs.append({"do": "continue", "aid": aid, "thread": thread, "program": prog.id, "units": units,
                             "seconds": units * self.run.cfg.budget})
                used += units
            if used >= U:
                break
        if used < U:
            jobs.append({"do": "mutate", "aid": f"g{gen}auto", "thread": "", "state": best.id, "method": None,
                         "count": U - used, "units": U - used, "auto": True})
        return jobs

    def run_jobs(self, gen, jobs, record_before, rng):
        run, a = self.run, self.run.archive
        tasks = []
        for j in jobs:
            meta = {"action_id": j["aid"], "thread": j.get("thread") or "", "record_before": record_before}
            if j["do"] == "experiment":
                exp = {**j, "eid": j["aid"]}
                tasks.append(("deep", exp, meta))
            elif j["do"] == "mutate":
                state = a.programs[j["state"]]
                front, _ = run.frontier(gen)
                for n in range(j["count"]):
                    if j.get("method"):
                        parent, tr = a.programs[j["method"]], True
                    else:
                        parent, tr = state, False
                    insp = a.best() if parent.id != a.best().id else next((q for q in front if q.id != parent.id), None)
                    tasks.append(("wide", (parent, state, tr, insp), meta))
            else:
                tasks.append(("continue", j, meta))
        out = []
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(tasks)))) as ex:
            futs = []
            for kind, arg, meta in tasks:
                if kind == "deep":
                    futs.append((ex.submit(self.deep_job, gen, arg, meta)))
                elif kind == "wide":
                    parent, state, tr, insp = arg
                    futs.append(ex.submit(self.wide_job, gen, parent, state, tr, insp, meta))
                else:
                    futs.append(ex.submit(self.continue_job, gen, arg, meta))
            out = [f.result() for f in futs]
        return out

    def deep_job(self, gen, exp, meta):
        p = self.run.deep_child6(gen, exp)
        self.run.set_meta(p, **meta)
        return p

    def wide_job(self, gen, parent, state, tr, insp, meta):
        p = self.run.wide_child6(gen, parent, state, insp, tr)
        self.run.set_meta(p, **meta)
        return p

    def continue_job(self, gen, job, meta):
        prog = self.run.archive.programs[job["program"]]
        return self.run.child6(gen, "continue", prog, prog.code, f"continue {prog.id} for {job['seconds']:.0f} s more",
                               {}, "(same code, run again from its own construction)", state=prog,
                               seconds=job["seconds"], meta={**meta, "continued": prog.id}, allow_same=True)

    def context(self, gen):
        run = self.run
        parts = [header(run, gen).replace("starts from its base's construction", "runs on the state you choose"),
                 best_block(run), run.progress_block(gen), self.states_block(gen), self.theory_block(),
                 self.threads_block(gen), self.map(gen)]
        rd = self.recent_decisions(gen)
        if rd:
            parts.append(rd)
        return "\n\n".join(parts)

    def round(self, gen):
        run = self.run
        t0, calls0 = time.time(), run.llm.calls
        rng = random.Random(run.cfg.seed * 7919 + gen)
        pool = [p for p in run.archive.valid() if p.gen < gen]
        record_before = max(p.score for p in pool)
        self.auto_park(gen)
        system = AGENT_SYSTEM.format(units=run.cfg.units, budget=run.cfg.budget, tail=self.run_tail_eps())
        base = self.context(gen)
        opened, asked, why = [], [], ""
        if gen > 1:
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
        user = base + ("\n\n## What you opened\n" + "\n\n".join(opened) if opened else "") + "\n\n" + \
            AGENT_FORMAT.format(units=run.cfg.units)
        decision, info = run.researcher(system, user, gen, role="agent", need="actions")
        decision = decision or {}
        refs, notes = self.apply_ops(gen, decision)
        jobs = self.validate(gen, decision, refs)
        children = self.run_jobs(gen, jobs, record_before, rng)
        info.update(opened=asked, open_why=why, notes=notes, tail=run.tail_status(gen))
        extra = {"actions": [j["do"] for j in jobs], "units": [j["units"] for j in jobs],
                 "auto_units": sum(j["units"] for j in jobs if j.get("auto")),
                 "threads_open": sum(1 for t in self.threads.values() if t["status"] == "open"),
                 "theory_active": sum(1 for h in self.theory.values() if h["status"] == "active")}
        return run.finish_generation(gen, t0, calls0, record_before, decision, info, jobs, children, extra=extra)

    def truncate(self, gen_done):
        super().truncate(gen_done)
        for path, events in ((self.th_path, self.th_events), (self.hy_path, self.hy_events)):
            events[:] = [e for e in events if e["gen"] <= gen_done]
            path.write_text("".join(json.dumps(e) + "\n" for e in events))
        self.rebuild_agent()

    def stats(self):
        st = super().stats()
        st.update(threads=len(self.threads), threads_open=sum(1 for t in self.threads.values() if t["status"] == "open"),
                  theory=sum(1 for h in self.theory.values() if h["status"] == "active"))
        return st


def clamp_int(x, lo, hi, default):
    try:
        v = int(round(float(x)))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def fake_decision(user):
    ids = re.findall(r"\bp\d{4}\b", user)
    base = ids[0] if ids else "p0001"
    ts = re.findall(r"\bT\d+\b", user)
    hs = re.findall(r"\bH\d+\b", user)
    threads = [{"op": "open", "ref": "t1", "question": "fake question", "stop": "3 actions"}]
    if ts:
        threads.append({"op": "revise", "id": ts[0], "question": "revised fake question", "why": "fake"})
    theory = [{"op": "add", "kind": "mechanism", "statement": "fake mechanism", "refuted_if": "a fake result"},
              {"op": "add", "kind": "mechanism", "statement": "this is the global optimum", "refuted_if": "x"}]
    if hs:
        theory.append({"op": "revise", "id": hs[0], "confidence": "medium", "why": "fake"})
    actions = [{"do": "experiment", "thread": "t1", "base": base, "state": "best", "units": 2, "kind": "fake kind a",
                "hypothesis": "fake hypothesis", "change": "perturb heights", "prediction": "small gain"},
               {"do": "experiment", "thread": ts[0] if ts else "t1", "base": base, "state": "none", "units": 1,
                "kind": "fake fresh", "hypothesis": "fresh", "change": "from scratch", "prediction": "lower"},
               {"do": "mutate", "thread": "t1", "state": base, "count": 1},
               {"do": "continue", "thread": "t1", "program": base, "units": 1}]
    return "```json\n" + json.dumps({"analysis": "fake round", "theory": theory, "threads": threads,
                                     "actions": actions}) + "\n```"
