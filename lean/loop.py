"""The loop: v4's with its Atlas memory, cleaned (docs/LEAN_V4.md lists every difference from helix4 and why each one
is safe).

One generation:
  1. MUTATE   `mutations` parents are sampled from all earlier programs (by rank, favouring programs with few
              children); for each, the mutator writes an improved version, shown one other strong program for ideas
  2. PLAN     meanwhile, the planner sees the problem, the best program (its code, its result and its last steps of
              ancestry) and the Atlas's map (the tree of attempts, the findings, the last generation in full), opens
              up to 6 items, and plans `planned` experiments, each on a base it chooses; a coder writes each one
  3. SCORE    every new program runs from its base's result, in its own process, under CPU, memory and time limits,
              and is checked and scored by code (lean/sandbox.py, or the problem's own evaluator)
  4. DISTIL   the Atlas's Distiller records what the generation taught, as findings citing the programs that show
              them; a finding's status is computed by code from the measured gains of its evidence
Every program is kept. Nothing is decided by a model except what to try and what the findings say. A stopped run
resumes from its last finished generation. `memory="none"` is v4's Control condition: no map, the 6 strongest
programs instead.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np

from lean import prompts as P
from lean.archive import Archive, Program, make_diff, short
from lean.atlas import Atlas
from lean.problems import load, setting
from lean.sandbox import evaluate
from lean import stores as S
from lean import scout as W


@dataclass
class Config:
    problem: str = "circles"
    params: dict = None           # the problem's parameters, e.g. {"n": 26}
    rounds: int = 50              # generations
    mutations: int = 3            # mutations per generation (v4's "wide")
    planned: int = 3              # planned experiments per generation (v4's "deep")
    budget: float = 30.0          # CPU seconds per program
    seed: int = 1
    effort: str = "low"           # the planner's thinking effort
    mem_mb: int = 1500
    scout: bool = False           # the Scout (lean/scout.py): web, code and paper search each generation (off: v4)
    eval_workers: int = 0         # at most this many programs evaluated at once (0: no limit, v4's behaviour); for
                                  # a machine with fewer cores than a generation has programs, so CPU times stay honest
    memory: str = "atlas"         # "atlas" (v4's best condition, started empty) or "none" (v4's Control)
    inspiration: str = "programs"  # a mutation's ideas: "programs" (v4: another strong program) or "guidance" (the
                                   # problem's guidance store only, so no program is shown as a model to copy)
    edits: bool = False           # coders reply with edits to the base (search/replace), or the whole program if the
                                  # change rewrites nearly all of it; v4: always the whole program
    mutation_plan: bool = False   # a mutation in two steps: a mutation planner (seeing what v4's mutator saw: its
                                  # parent, and the inspiration or the guidance; never the Atlas) chooses the change, then
                                  # the coder implements it; v4: one mutator decides and writes


THE_BASES = "the base's"


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
        self.round_now = max(self.round_done, 0)
        self.problem = load(self.cfg.problem, **(self.cfg.params or {}))
        self.entry = setting(self.problem, "entry")
        self.clip = setting(self.problem, "clip")
        self.archive = Archive(self.dir)
        self.lock = threading.Lock()
        self.task = threading.local()              # the program a thread is making (for the traces)
        self.scout = None                          # made after the archive is loaded (it reads the run folder)
        self.eval_gate = threading.BoundedSemaphore(self.cfg.eval_workers) if self.cfg.eval_workers > 0 else None
        self.calls_f = (self.dir / "calls.jsonl").open("a")
        if llm is None:
            from lean.llm import LLM
            llm = LLM()
        self.llm = llm
        self.llm.on_call = self.record
        if self.cfg.memory not in ("atlas", "none"):
            raise ValueError(f"memory must be 'atlas' or 'none', not {self.cfg.memory!r}")
        self.atlas = Atlas(self) if self.cfg.memory == "atlas" else None
        if self.cfg.inspiration not in ("programs", "guidance"):
            raise ValueError(f"inspiration must be 'programs' or 'guidance', not {self.cfg.inspiration!r}")
        # the stores (lean/stores.py): the context goes with the description to every agent; the guidance, if any
        context = (getattr(self.problem, "context", "") or "").strip()
        self.statement = self.problem.description + (f"\n\n{S.CONTEXT}{context}" if context else "")
        self.guidance = S.Guidance(getattr(self.problem, "guidance", "") or "")
        # forget an unfinished generation (on a fresh start, an unfinished generation 0: a run stopped while it scored
        # its starting programs would otherwise keep a second copy of them)
        self.archive.truncate(self.round_done)
        if self.atlas:
            self.atlas.truncate(self.round_done)
        if self.cfg.scout:
            self.scout = W.Scout(self)
            self.scout.truncate(self.round_done)
        for name in ("rounds.jsonl", "plans.jsonl"):
            self._rewrite(name, [r for r in self._read(name) if r["round"] <= self.round_done])
        if state:
            self.log(f"resuming after generation {self.round_done}")

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

    # ------------------------------------------------------------------ what the agents see (v4's views)
    def block(self, p, title, chars):
        fb = "\n".join(f"  {l}" for l in p.feedback)
        return f"## {title}: {p.line()}\nIts result:\n{fb}\n```python\n{P.clip(p.code, chars)}```"

    def best_block(self, b):
        fb = "\n".join(f"  {l}" for l in b.feedback)
        return (f"## The best program so far: {b.id} (score {b.score:.9f})\n"
                f"Its lineage: {self.archive.lineage_line(b.id)}\nIts result:\n{fb}\n"
                f"```python\n{P.clip(b.code, self.clip['best'])}```")

    def scoreboard(self, k=6):
        return "## The strongest programs (any program can be a base)\n" + "\n".join(
            f"- {p.line()}: {short(p.idea, 110)}" for p in self.archive.ranked()[:k])

    def header(self):
        note = setting(self.problem, "generation_note").format(budget=self.cfg.budget)
        return f"{self.statement}\n\n# Generation {self.round_now} of {self.cfg.rounds}\n{note}\n"

    def plan_prompt(self, k):
        """v4's Control view: the header, the best program, the 6 strongest programs. (The Atlas builds its own.)"""
        return f"{self.header()}\n{self.best_block(self.archive.best())}\n\n{self.scoreboard()}\n\n{self.plan_tail(k, '')}"

    def plan_tail(self, k, findings):
        """The end of the planner's view: the guidance store (if any), the scout's items (if on), then the reply format
        (call under the lock)."""
        return (self.guidance.whole(self.archive, self.round_now)
                + (self.scout.for_planner(self.round_now) if self.scout else "")
                + P.PLAN_FORMAT.format(k=k, findings=findings, guidance=(S.FIELD if self.guidance else "")
                                       + (W.FIELD if self.scout else "")))

    def task_note(self, whose):
        return setting(self.problem, "task_note").format(budget=self.cfg.budget, whose=whose)

    # ------------------------------------------------------------------ the agents
    def call(self, role, system, user, temperature, max_tokens, effort="none"):
        """A model call, tagged with its generation and task (the program it is for; none for the generation's own
        calls: planner, Navigator, Distiller), so every call's tokens and time can be tied to a program."""
        return self.llm.chat(role, system, user, temperature=temperature, max_tokens=max_tokens, effort=effort,
                             meta={"round": self.round_now, "task": getattr(self.task, "id", None)})

    def write_code(self, role, system, user, base=None):
        """The program in a coder's or mutator's reply, its summary, and how it came: "full" (the whole program) or
        "edits" (applied to `base`; only coders with `edits` on), "+retry" if it took a second call."""
        n = setting(self.problem, "reply_tokens")
        edits = self.cfg.edits and base is not None
        if edits:
            user = user.replace(P.CODE_FORMAT, P.EDIT_FORMAT)
        text = self.call(role, system, user, 0.5 if role == "coder" else 0.8, n)
        code, form, why = self.read_reply(text, base if edits else None)
        if code is None:
            retry = P.EDIT_RETRY.format(why=why) if edits else P.CODE_RETRY.format(entry=self.entry)
            text = self.call(role, system, user + retry, 0.4, n)
            code, form, why = self.read_reply(text, base if edits else None)
            form += "+retry"
        return code, P.extract_summary(text), form, text

    def read_reply(self, text, base):
        """(code, form, why not): edits applied to `base` when the reply has any, else its whole program."""
        if base is not None and P.EDIT_START in (text or ""):
            code, why = P.apply_edits(base.code, text)
            if code is not None and f"def {self.entry}" not in code:
                code, why = None, f"the edited program no longer defines {self.entry}"
            return code, "edits", why
        code = P.extract_code(text, self.entry)
        return code, "full", f"no edits and no complete ```python block defining {self.entry}"

    def plan(self, k):
        """The planner's experiments (v4's Researcher). An unreadable reply is asked for once more; an experiment on an
        unknown or failed base goes to the best program; experiments still missing become "improve the best program".
        Returns (analysis, experiments, info)."""
        system = setting(self.problem, "planner_system").format(k=k, budget=self.cfg.budget)
        if self.atlas:
            user, info = self.atlas.plan_prompt(self.round_now, k, system)
        else:
            with self.lock:                        # mutations may be adding programs meanwhile
                user, info = self.plan_prompt(k), {}
        info["prompt_chars"] = len(user)
        js = P.extract_json(self.call("planner", system, user, 0.7, 12000, self.cfg.effort))
        info["retried"] = not (isinstance(js, dict) and isinstance(js.get("experiments"), list) and js["experiments"])
        if info["retried"]:
            js = P.extract_json(self.call("planner", system, user + P.PLAN_RETRY, 0.5, 3500))
        js = js if isinstance(js, dict) else {}
        info["parsed"] = isinstance(js.get("experiments"), list)
        exps = []
        with self.lock:
            best = self.archive.best()
            for e in (js.get("experiments") if isinstance(js.get("experiments"), list) else [])[:k]:
                if isinstance(e, dict) and (e.get("change") or e.get("hypothesis")):
                    refs, cites, webs = e.get("builds_on"), S.ids(e.get("guidance")), W.ids(e.get("web"))
                    e = {x: str(e.get(x) or "").strip() for x in ("base", "hypothesis", "change", "prediction")}
                    e["builds_on"] = [str(x) for x in refs] if isinstance(refs, list) else ([str(refs)] if refs else [])
                    if self.guidance:
                        e["guidance"] = cites
                    if self.scout:
                        e["web"] = webs
                    b = self.archive.programs.get(e["base"])
                    if b is None or not b.valid:
                        e["base_asked"], e["base"] = e["base"], best.id
                    exps.append(e)
        while len(exps) < k:                       # an unreadable plan still spends the generation's budget
            exps.append({"base": best.id, "hypothesis": "(no plan: the planner's reply was unusable)",
                         "change": "Improve the base program in the way you judge most promising.", "prediction": "",
                         "builds_on": [], "fallback": True})
        return str(js.get("analysis") or ""), exps, info

    def planned_child(self, exp, role="planned"):
        base = self.archive.programs[exp["base"]]
        user = (f"{self.statement}\n\n{self.block(base, 'The base program', self.clip['base'])}\n\n"
                f"{self.guidance.cited(exp.get('guidance') or [])}"
                f"{self.scout.cited(exp.get('web') or []) if self.scout else ''}## The experiment to implement\nHypothesis: {exp['hypothesis']}\nChange: {exp['change']}\n"
                f"Prediction: {exp['prediction']}\n\nImplement this experiment as a change to the base program. "
                f"Keep what the base does well unless the experiment says otherwise. {self.task_note(THE_BASES)}"
                f"\n\n{P.CODE_FORMAT}")
        code, summary, form, _ = self.write_code("coder", setting(self.problem, "coder_system"), user, base)
        return self.child(role, base, code, exp["hypothesis"] or exp["change"], exp, summary, form)

    def mutation_view(self, parent, inspiration):
        """What a mutation's author sees (v4's mutator view): the program to improve, then the inspiration, then the
        guidance store (if any)."""
        user = f"{self.statement}\n\n{self.block(parent, 'The program to improve', self.clip['base'])}\n\n"
        if inspiration is not None:
            user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                     f"{P.clip(inspiration.code, self.clip['inspiration'])}```\n\n")
        with self.lock:                            # the guidance's records read the archive, which others write to
            user += self.guidance.whole(self.archive, self.round_now)
        if self.scout:                             # this mutator's direction from the web: one per mutation slot
            task = getattr(self.task, "id", None) or ""
            slot = int(task.rsplit("-m", 1)[1]) - 1 if "-m" in task else 0
            user += self.scout.for_mutator(slot)
        return user

    def mutation_child(self, parent, inspiration):
        if self.cfg.mutation_plan:
            return self.planned_mutation(parent, inspiration)
        user = (f"{self.mutation_view(parent, inspiration)}Write an improved version of the program to improve. "
                f"{self.task_note('its')}\n\n{P.CODE_FORMAT}" + (S.MUTATOR_LINE if self.guidance else "")
                + (W.MUTATOR_LINE if self.scout else ""))
        code, summary, form, text = self.write_code("mutator", setting(self.problem, "mutator_system"), user)
        cites = S.ids(" ".join(re.findall(r"GUIDANCE:\s*(.+)", text or ""))) if self.guidance else []
        plan = {"guidance": cites} if cites else {}
        webs = W.ids(" ".join(re.findall(r"WEB:\s*(.+)", text or ""))) if self.scout else []
        if webs:
            plan["web"] = webs
        return self.child("mutation", parent, code, summary or "(no summary)", plan, summary, form)

    def planned_mutation(self, parent, inspiration):
        """A mutation in two steps: the mutation planner chooses one change from what a mutator sees; the coder (the
        planned experiments' coder) implements it on the parent."""
        ask = P.MUTATION_PLAN_FORMAT.format(guidance=S.MUTATION_FIELD if self.guidance else "")
        user = f"{self.mutation_view(parent, inspiration)}{ask}"
        system = setting(self.problem, "mutation_planner_system")
        js = P.extract_json(self.call("mutation_planner", system, user, 0.8, 4000))
        if not (isinstance(js, dict) and (js.get("change") or js.get("hypothesis"))):
            js = P.extract_json(self.call("mutation_planner", system, user + P.PLAN_RETRY, 0.5, 4000))
        js = js if isinstance(js, dict) else {}
        exp = {x: str(js.get(x) or "").strip() for x in ("hypothesis", "change", "prediction")}
        exp["base"] = parent.id
        if self.guidance:
            exp["guidance"] = S.ids(js.get("guidance"))
        if not (exp["change"] or exp["hypothesis"]):          # an unreadable plan still spends the mutation
            exp.update(change="Improve the base program in the way you judge most promising.", fallback=True,
                       hypothesis="(no plan: the mutation planner's reply was unusable)")
        return self.planned_child(exp, role="mutation")

    def child(self, role, parent, code, idea, plan, summary, reply=""):
        p = Program(id="", round=self.round_now, role=role, parent=parent.id, idea=short(idea, 300), code=code or "",
                    plan=dict(plan or {}), summary=summary, reply=reply, trace={"task": getattr(self.task, "id", None)})
        if code is None:
            p.error = "no program in the model's reply"
            with self.lock:
                return self.archive.add(p)
        with self.lock:
            dup = self.archive.duplicate(code, parent.id)
        if dup:
            p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
            with self.lock:
                return self.archive.add(p)
        p.diff = make_diff(parent.code, code)
        if self.eval_gate:
            self.eval_gate.acquire()
        try:
            t0 = time.time()
            res = evaluate(self.problem, code, self.archive.construction(parent.id), self.cfg.budget, self.cfg.mem_mb)
        finally:
            if self.eval_gate:
                self.eval_gate.release()
        p.trace.update(eval_start=round(t0, 3), eval_end=round(time.time(), 3), eval_seconds=round(time.time() - t0, 3))
        if res.get("start_score") is None and parent.valid and res["valid"]:
            # a problem whose programs don't start from a construction (the VRP): a change is measured against the
            # base's score, and the first feedback line says so (v4's VRP plug-in did the same)
            res["start_score"], res["delta"] = parent.score, res["score"] - parent.score
            res["feedback"] = [res["feedback"][0] + f"; its base {parent.id} scored {parent.score:.9f} "
                               f"({res['delta']:+.9f})"] + res["feedback"][1:]
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu = res["feedback"], res["error"], res["cpu"]
        with self.lock:
            return self.archive.add(p, res.get("construction"))

    def safe(self, fn, *args, task=None):
        """Never lose the run to one crashed agent call: the crash is logged and kept as a failed program. `task` names
        the program being made (g<generation>-m<k> or -p<k>), for the traces."""
        self.task.id = task
        try:
            return fn(*args)
        except Exception as exc:                                         # noqa: BLE001
            self.log(f"generation {self.round_now}: {fn.__name__} crashed: {exc}\n{traceback.format_exc()}")
            base = args[0]["base"] if args and isinstance(args[0], dict) else getattr(args[0], "id", None)
            role = "planned" if fn.__name__ == "planned_child" else "mutation"
            with self.lock:
                return self.archive.add(Program(id="", round=self.round_now, role=role, parent=base,
                                                idea="(crashed)", code="", error=f"internal error: {exc}"))

    # ------------------------------------------------------------------ the loop
    def seed(self):
        self.round_now = 0
        p = Program(id="", round=0, role="seed", parent=None,
                    idea=getattr(self.problem, "seed_idea", "Code Zero: the trivial starting program"),
                    code=self.problem.code_zero)
        t0 = time.time()
        res = evaluate(self.problem, p.code, None, self.cfg.budget, self.cfg.mem_mb)
        p.trace = {"task": "g0-seed", "eval_start": round(t0, 3), "eval_end": round(time.time(), 3),
                   "eval_seconds": round(time.time() - t0, 3)}
        if not res["valid"]:
            raise RuntimeError(f"Code Zero failed: {res['error']} | " + " | ".join(res["feedback"][:6]))
        p.valid, p.score, p.feedback, p.cpu = True, res["score"], res["feedback"], res["cpu"]
        self.archive.add(p, res.get("construction"))
        self.log(f"generation 0: Code Zero scores {p.score:.9f}")
        # optional further starting programs (a problem's `extra_seeds`: [(idea, code), ...]); none by default, and
        # then generation 0 is exactly as before
        # (scored side by side, as a generation's children are; added in their given order)
        seeds = getattr(self.problem, "extra_seeds", []) or []
        with ThreadPoolExecutor(max_workers=max(1, len(seeds))) as ex:
            results = list(ex.map(lambda s: evaluate(self.problem, s[1], None, self.cfg.budget, self.cfg.mem_mb), seeds))
        for (idea, code), res in zip(seeds, results):
            q = Program(id="", round=0, role="seed", parent=None, idea=idea, code=code)
            if not res["valid"]:
                raise RuntimeError(f"a starting program failed: {res['error']} | " + " | ".join(res["feedback"][:6]))
            q.valid, q.score, q.feedback, q.cpu = True, res["score"], res["feedback"], res["cpu"]
            self.archive.add(q, res.get("construction"))
            self.log(f"generation 0: starting program {q.id} scores {q.score:.9f}")
        best = self.archive.ranked()[0]
        self._append("rounds.jsonl", {"round": 0, "best": best.score, "best_id": best.id})
        self.checkpoint(0)

    def round(self, r):
        self.round_now = r
        self.task.id = None                        # the planner, Navigator, Distiller, Scout: the generation's own calls
        t0, calls0 = time.time(), self.llm.calls
        scouted = {}
        if self.scout:                             # the search comes first: the planner and the mutators read it
            try:
                rec = self.scout.scout(r, self.cfg.mutations)
                scouted = {"queries": len(rec["queries"]), "items": len(rec["results"]), "cost_usd": rec["cost_usd"],
                           "errors": len(rec["errors"])}
            except Exception as exc:                                     # noqa: BLE001  (never lose the run)
                self.log(f"generation {r}: the scout crashed: {exc}\n{traceback.format_exc()}")
                self.scout.brief = {"deep": [], "wide": []}
                scouted = {"error": str(exc)[:300]}
        rng = random.Random(self.cfg.seed * 7919 + r)
        pool = [p for p in self.archive.programs.values() if p.valid and p.round < r]
        parents = [self.archive.sample_parent(rng, pool) for _ in range(self.cfg.mutations)]
        top = self.archive.ranked()[:5]
        analysis, exps, info = "", [], {}
        with ThreadPoolExecutor(max_workers=self.cfg.mutations + self.cfg.planned) as ex:
            futs = []
            for k, par in enumerate(parents, 1):
                others = [q for q in top if q.id != par.id]
                insp = rng.choice(others) if others and self.cfg.inspiration == "programs" else None
                futs.append(ex.submit(self.safe, self.mutation_child, par, insp, task=f"g{r}-m{k}"))
            if self.cfg.planned:
                try:
                    analysis, exps, info = self.plan(self.cfg.planned)
                except Exception as exc:                                 # noqa: BLE001
                    self.log(f"generation {r}: the planner crashed: {exc}\n{traceback.format_exc()}")
                    best = self.archive.best()
                    exps = [{"base": best.id, "hypothesis": "(no plan: the planner crashed)", "change":
                             "Improve the base program in the way you judge most promising.", "prediction": "",
                             "builds_on": [], "fallback": True} for _ in range(self.cfg.planned)]
                futs += [ex.submit(self.safe, self.planned_child, e, task=f"g{r}-p{k}") for k, e in enumerate(exps, 1)]
            kids = [f.result() for f in futs]
        mem = {}
        if self.atlas:
            try:
                mem = self.atlas.update(r, analysis, kids)
            except Exception as exc:                                     # noqa: BLE001  (never lose the run)
                self.log(f"generation {r}: the Distiller crashed: {exc}\n{traceback.format_exc()}")
                mem = {"error": str(exc)}
        self._append("plans.jsonl", {"round": r, "analysis": analysis, "experiments": exps, "info": info,
                                     "memory": mem})
        new_best = self.archive.best()
        row = {"round": r, "best": new_best.score, "best_id": new_best.id, "record": new_best.round == r,
               "record_role": new_best.role if new_best.round == r else None,
               "programs": len(kids), "failed": sum(1 for c in kids if not c.valid),
               "duplicates": sum(1 for c in kids if c.duplicate_of),
               "planned_best": max([c.score for c in kids if c.valid and c.role == "planned"], default=None),
               "mutation_best": max([c.score for c in kids if c.valid and c.role == "mutation"], default=None),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_asked" in e),
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "opened": info.get("opened"), "planner_prompt_chars": info.get("prompt_chars"),
               "calls": self.llm.calls - calls0, "seconds": round(time.time() - t0, 1),
               "t_start": round(t0, 3), "t_end": round(time.time(), 3), **({"scout": scouted} if self.scout else {}),
               **(self.atlas.stats() if self.atlas else {})}
        self._append("rounds.jsonl", row)
        self.checkpoint(r)
        self.log(f"generation {r}: best {new_best.score:.9f} ({new_best.id}, {new_best.role})"
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
                   "best_lineage": self.archive.lineage_line(best.id, depth=40),
                   "references": getattr(self.problem, "references", [])}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1))
        (self.dir / "best.py").write_text(best.code)
        c = self.archive.construction(best.id)
        if c is not None:
            np.save(self.dir / "best.npy", c)
        self.log(f"done: best {best.score:.9f} ({best.id}) after {self.round_done} generations, {len(progs)} programs")
        return summary
