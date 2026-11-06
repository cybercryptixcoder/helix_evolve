"""The loop. One round:

  1. MUTATE   `mutations` programs: each takes a parent and asks the model for a better version of it
              (parent: the best program, or one sampled from all programs by rank; optionally shown another strong
              program for ideas)
  2. PLAN     if `planned` > 0: the planner sees the problem, the best program, the strongest programs and (if
              `notes`) the notes of what was tried and what it gave, and plans that many experiments, each on a base
              program it chooses; a coder writes each one
  3. SCORE    every new program runs from its parent's result, under a CPU limit, and is checked and scored by code
  4. NOTE     if `notes`: one line per program (what it tried, what it gave) is added to the notes
  5. RESTART  if `restart` = K > 0 and the current line hasn't improved its own best for K rounds, a new line
              starts from Code Zero; from then on every parent and base comes from the new line (the old lines are
              kept, and the run's record is the best of all lines)

Everything the run does is written as it happens (see README): a stopped run resumes from its last finished round.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np

from lean import prompts as P
from lean.archive import Archive, Program, short
from lean.problems import load
from lean.sandbox import evaluate


@dataclass
class Config:
    problem: str = "circles"
    params: dict = None           # the problem's parameters, e.g. {"n": 26}
    rounds: int = 50
    mutations: int = 3            # mutation programs per round
    planned: int = 3              # planned experiments per round (0: no planner)
    parents: str = "population"   # where mutations start: "best", or "population" (sampled by rank)
    inspiration: bool = True      # show each mutation another strong program for ideas
    notes: bool = True            # keep notes of what was tried and what it gave, for the planner
    notes_chars: int = 20000      # past this, older rounds keep only their gains
    budget: float = 30.0          # CPU seconds per program
    seed: int = 1
    effort: str = "low"           # the planner's thinking effort
    mem_mb: int = 1500
    restart: int = 0              # start a new line from Code Zero after this many rounds without a gain (0: never)
    restart_gain: float = 1e-6    # a gain smaller than this (relative to the line's best) doesn't count as one


class Run:
    def __init__(self, out, cfg=None, llm=None, log=print):
        self.dir = Path(out)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = log
        state_f = self.dir / "state.json"
        state = json.loads(state_f.read_text()) if state_f.exists() else None
        if state:
            known = {f.name for f in fields(Config)}
            stored = Config(**{k: v for k, v in state["config"].items() if k in known})
            if cfg is not None:
                stored.rounds = cfg.rounds              # only the length of a run may change on resume
            cfg = stored
        self.cfg = cfg or Config()
        self.round_done = state["round_done"] if state else -1
        self.problem = load(self.cfg.problem, **(self.cfg.params or {}))
        self.archive = Archive(self.dir)
        self.lock = threading.Lock()
        self.calls_f = (self.dir / "calls.jsonl").open("a")
        if llm is None:
            from lean.llm import LLM
            llm = LLM()
        self.llm = llm
        self.llm.on_call = self.record
        self.notes = [json.loads(l) for l in (self.dir / "notes.jsonl").read_text().splitlines()
                      if l.strip()] if (self.dir / "notes.jsonl").exists() else []
        if state:
            self.archive.truncate(self.round_done)
            if self.notes:
                self.notes = [n for n in self.notes if n["round"] <= self.round_done]
                self._rewrite("notes.jsonl", self.notes)
            self._rewrite("rounds.jsonl", [r for r in self._read("rounds.jsonl") if r["round"] <= self.round_done])
            self.log(f"resuming after round {self.round_done}")

    # ------------------------------------------------------------------ files
    def _read(self, name):
        f = self.dir / name
        return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []

    def _rewrite(self, name, rows):
        (self.dir / name).write_text("".join(json.dumps(r) + "\n" for r in rows))

    def _append(self, name, row):
        with self.lock, (self.dir / name).open("a") as f:
            f.write(json.dumps(row, default=float) + "\n")

    def record(self, call):
        with self.lock:
            self.calls_f.write(json.dumps({"t": round(time.time(), 1), **call}) + "\n")
            self.calls_f.flush()

    def checkpoint(self, r):
        self.round_done = r
        tmp = self.dir / "state.tmp"
        tmp.write_text(json.dumps({"round_done": r, "config": asdict(self.cfg), "t": time.time()}, indent=1))
        os.replace(tmp, self.dir / "state.json")

    # ------------------------------------------------------------------ lines (restarts)
    @property
    def lineage(self):
        return self.archive.lineages()

    def head(self):
        """The current line's best program: what the planner improves on and the default base."""
        return self.archive.best(self.lineage)

    def stalled(self):
        """Rounds since the current line last improved its own best by more than `restart_gain` (relative): slow
        polishing of a poor region doesn't keep a line alive."""
        progs = [p for p in self.archive.programs.values() if p.lineage == self.lineage and p.valid]
        best, last = None, 0
        for p in sorted(progs, key=lambda p: p.id):
            if best is None or p.score > best + self.cfg.restart_gain * abs(best):
                best, last = p.score, p.round
            best = max(best, p.score)
        return self.round_done - last

    # ------------------------------------------------------------------ views
    def block(self, p, title, chars=12000):
        fb = "\n".join(f"  {l}" for l in p.feedback)
        return f"## {title}: {p.line()}\nIts result:\n{fb}\n```python\n{P.clip(p.code, chars)}```"

    def scoreboard(self, k=6):
        return "## The strongest programs (any of them can be a base)\n" + "\n".join(
            f"- {p.line()}: {short(p.idea, 110)}" for p in self.archive.ranked(self.lineage)[:k])

    def notes_view(self):
        """Every round's lines; past `notes_chars`, the oldest rounds keep only their gains."""
        def text(n, full):
            lines = n["lines"] if full else [l for l in n["lines"] if l.get("gain")]
            body = "\n".join(l["text"] for l in lines)
            rest = len(n["lines"]) - len(lines)
            return (f"### Round {n['round']}" + (f": {n['analysis']}" if full and n.get("analysis") else "")
                    + (f"\n{body}" if body else "") + (f"\n({rest} more without gain)" if rest else ""))
        full = [True] * len(self.notes)
        out = "\n".join(text(n, f) for n, f in zip(self.notes, full))
        i = 0
        while len(out) > self.cfg.notes_chars and i < len(self.notes) - 3:
            full[i] = False
            i += 1
            out = "\n".join(text(n, f) for n, f in zip(self.notes, full))
        return out or "(nothing yet)"

    # ------------------------------------------------------------------ the agents
    def call(self, role, system, user, temperature, max_tokens, effort="none"):
        return self.llm.chat(role, system, user, temperature=temperature, max_tokens=max_tokens, effort=effort,
                             meta={"round": self.round_now})

    def write_code(self, role, system, user):
        text = self.call(role, system, user, 0.5 if role == "coder" else 0.8, 12000)
        code = P.extract_code(text)
        if code is None:
            text = self.call(role, system, user + "\n\n(Your previous reply had no complete ```python block defining "
                             "construct. Reply with the full program.)", 0.4, 12000)
            code = P.extract_code(text)
        return code, P.extract_summary(text)

    def plan(self, k):
        with self.lock:                            # mutations may be adding programs meanwhile
            best, user = self.head(), self.plan_prompt(k)
        system = P.PLANNER_SYSTEM.format(k=k, budget=self.cfg.budget)
        js = P.extract_json(self.call("planner", system, user, 0.7, 6000, self.cfg.effort)) or {}
        exps = []
        with self.lock:
            for e in (js.get("experiments") or [])[:k]:
                if isinstance(e, dict) and (e.get("change") or e.get("hypothesis")):
                    e = {x: str(e.get(x) or "").strip() for x in ("base", "hypothesis", "change", "prediction")}
                    b = self.archive.programs.get(e["base"])
                    if b is None or not b.valid or b.lineage != self.lineage:
                        e["base_asked"], e["base"] = e["base"], best.id
                    exps.append(e)
        while len(exps) < k:                       # an unreadable plan still spends the round's budget
            exps.append({"base": best.id, "hypothesis": "(no plan: the planner's reply was unreadable)",
                         "change": "Improve the base program in the way you judge most promising.", "prediction": ""})
        return str(js.get("analysis") or ""), exps

    def plan_prompt(self, k):
        best = self.head()
        user = (f"{self.problem.description}\n\n# Round {self.round_now} of {self.cfg.rounds}\nEach program gets "
                f"{self.cfg.budget:.0f} s of CPU and starts from its base's result.\n\n"
                f"{self.block(best, 'The best program so far')}\n\n{self.scoreboard()}")
        if self.cfg.notes:
            user += f"\n\n## Notes: every experiment so far and what it gave, oldest first\n{self.notes_view()}"
        return user + "\n\n" + P.PLAN_FORMAT.format(k=k)

    def planned_child(self, exp):
        base = self.archive.programs[exp["base"]]
        user = (f"{self.problem.description}\n\n{self.block(base, 'The base program', 30000)}\n\n"
                f"## The experiment to implement\nHypothesis: {exp['hypothesis']}\nChange: {exp['change']}\n"
                f"Prediction: {exp['prediction']}\n\nImplement it as a change to the base program. budget_seconds will "
                f"be {self.cfg.budget:.0f}; `start` will be the base's result.\n\n{P.CODE_FORMAT}")
        code, summary = self.write_code("coder", P.CODER_SYSTEM, user)
        return self.child("planned", base, code, exp["hypothesis"] or exp["change"], exp, summary)

    def mutation_child(self, parent, inspiration):
        user = f"{self.problem.description}\n\n{self.block(parent, 'The program to improve', 30000)}\n\n"
        if inspiration is not None:
            user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                     f"{P.clip(inspiration.code, 8000)}```\n\n")
        user += (f"Write an improved version of the program to improve. budget_seconds will be {self.cfg.budget:.0f}; "
                 f"`start` will be its result.\n\n{P.CODE_FORMAT}")
        code, summary = self.write_code("mutator", P.MUTATOR_SYSTEM, user)
        return self.child("mutation", parent, code, summary or "(no summary)", {}, summary)

    def child(self, role, parent, code, idea, plan, summary):
        p = Program(id="", round=self.round_now, role=role, parent=parent.id, idea=short(idea, 300), code=code or "",
                    plan={**plan, "summary": summary} if plan else {}, lineage=parent.lineage)
        if code is None:
            p.error = "no program in the model's reply"
            return self.archive.add(p)
        with self.lock:
            dup = self.archive.duplicate(code, parent.id)
        if dup:
            p.error, p.duplicate_of = f"identical to {dup}: not run again", dup
            with self.lock:
                return self.archive.add(p)
        res = evaluate(self.problem, code, self.archive.construction(parent.id), self.cfg.budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu = res["feedback"], res["error"], res["cpu"]
        with self.lock:
            return self.archive.add(p, res["construction"])

    def safe(self, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:                                         # noqa: BLE001  (never lose the run)
            import traceback
            self.log(f"round {self.round_now}: {fn.__name__} crashed: {exc}\n{traceback.format_exc()}")
            return None

    # ------------------------------------------------------------------ the loop
    def seed(self, lineage=0):
        if lineage == 0:
            self.round_now = 0
        p = Program(id="", round=self.round_now, role="seed", parent=None, idea="Code Zero: the trivial starting program",
                    code=self.problem.code_zero, lineage=lineage)
        res = evaluate(self.problem, p.code, None, self.cfg.budget, self.cfg.mem_mb)
        if not res["valid"]:
            raise RuntimeError(f"Code Zero failed: {res['error']}")
        p.valid, p.score, p.feedback, p.cpu = True, res["score"], res["feedback"], res["cpu"]
        self.archive.add(p, res["construction"])
        if lineage == 0:
            self._append("rounds.jsonl", {"round": 0, "best": p.score, "best_id": p.id})
            self.checkpoint(0)
        return p

    def round(self, r):
        self.round_now = r
        t0, calls0 = time.time(), self.llm.calls
        rng = random.Random(self.cfg.seed * 7919 + r)
        restarted = None
        if self.cfg.restart and self.stalled() >= self.cfg.restart:
            with self.lock:
                restarted = self.seed(self.lineage + 1).id       # a new line from Code Zero, in this round
        pool = [p for p in self.archive.programs.values() if p.valid and p.lineage == self.lineage]
        best = self.head()
        if self.cfg.parents == "best":
            parents = [best] * self.cfg.mutations
        else:
            parents = [self.archive.sample_parent(rng, pool) for _ in range(self.cfg.mutations)]
        top = self.archive.ranked(self.lineage)[:5]
        analysis = ""
        with ThreadPoolExecutor(max_workers=self.cfg.mutations + self.cfg.planned) as ex:
            futs = []
            for par in parents:
                others = [q for q in top if q.id != par.id]
                insp = rng.choice(others) if (self.cfg.inspiration and others) else None
                futs.append(ex.submit(self.safe, self.mutation_child, par, insp))
            if self.cfg.planned:
                out = self.safe(self.plan, self.cfg.planned)
                analysis, exps = out if out else ("", [])
                futs += [ex.submit(self.safe, self.planned_child, e) for e in exps]
            kids = [k for k in (f.result() for f in futs) if k is not None]
        if self.cfg.notes:
            lines = []
            for c in kids:
                res = (f"{c.score:.9f} ({c.delta:+.9f})" if c.valid and c.delta is not None else
                       f"FAILED: {short(c.error, 100)}")
                what = f"planned: {short(c.plan.get('change'), 220)}" if c.role == "planned" else \
                    f"mutation: {short(c.idea, 220)}"
                lines.append({"text": f"- {c.id} from {c.parent}: {what} -> {res}",
                              "gain": bool(c.valid and (c.delta or 0) > 0)})
            note = {"round": r, "analysis": short(analysis, 500), "lines": lines}
            self.notes.append(note)
            self._append("notes.jsonl", note)
        new_best = self.archive.best()
        row = {"round": r, "best": new_best.score, "best_id": new_best.id, "record": new_best.round == r,
               "record_role": new_best.role if new_best.round == r else None,
               "programs": len(kids), "failed": sum(1 for c in kids if not c.valid),
               "planned_best": max([c.score for c in kids if c.valid and c.role == "planned"], default=None),
               "mutation_best": max([c.score for c in kids if c.valid and c.role == "mutation"], default=None),
               "calls": self.llm.calls - calls0, "seconds": round(time.time() - t0, 1),
               "line": self.lineage, "line_best": self.head().score, "restarted": restarted}
        self._append("rounds.jsonl", row)
        self.checkpoint(r)
        self.log(f"round {r}: best {new_best.score:.9f} ({new_best.id}, {new_best.role})"
                 + (f"; line {self.lineage}{' (NEW)' if restarted else ''} at {self.head().score:.9f}"
                    if self.cfg.restart else "")
                 + (" RECORD" if row["record"] else "") + f"; {row['failed']}/{len(kids)} failed; "
                 f"{row['seconds']:.0f} s")
        return row

    def go(self):
        if self.round_done < 0:
            self.seed()
        deadline = float(os.environ.get("HELIX_DEADLINE", "0") or 0)
        for r in range(self.round_done + 1, self.cfg.rounds + 1):
            if deadline and time.time() > deadline:
                self.log("deadline passed: stopping")
                break
            self.round(r)
        return self.finish()

    def finish(self):
        best = self.archive.best()
        progs = list(self.archive.programs.values())
        summary = {"best": best.score, "best_id": best.id, "rounds": self.round_done, "programs": len(progs),
                   "valid": sum(p.valid for p in progs), "calls": self.llm.calls, "tokens_in": self.llm.tokens_in,
                   "tokens_out": self.llm.tokens_out, "config": asdict(self.cfg),
                   "references": self.problem.references}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1))
        (self.dir / "best.py").write_text(best.code)
        c = self.archive.construction(best.id)
        if c is not None:
            np.save(self.dir / "best.npy", c)
        self.log(f"done: best {best.score:.9f} ({best.id}) after {self.round_done} rounds, {len(progs)} programs")
        return summary
