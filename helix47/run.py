"""One Helix v4.7 run: v4 (helix4/run.py, Atlas memory) with the false ceiling removed (docs/V47_DESIGN.md).

    python -m helix47.run --seed 1 --gens 30 --out runs/v47/v47-s1
    python -m helix47.run --out runs/v47/v47-s1                 # resumes (state.json is there)
    python -m helix47.run --gens 2 --fake --out /tmp/x          # no model calls

While the search is moving, a generation is v4's: the wide loop (3 Mutator children from sampled parents) and the
deep loop (the Researcher plans 3 experiments, Coders write them), all run, scored and recorded; the Atlas Distiller
records findings. What changes always:
  1. a program may hand back an alternative construction, which is scored and kept as its own program (role "alt"),
     so a new idea that hasn't beaten its start yet isn't erased (in v4, 72% of late children returned their start
     unchanged);
  2. gains count only above a noise floor (`gain_floor`, relative), in the findings, the history and the feedback;
  3. the memory map is balanced and failures are scoped to the construction they were tried on (helix47/memory.py);
  4. the prompts ask for targets rather than confirm-or-refute predictions, drop the countdown, state the honest
     room left, and allow up to `max_n` steps (helix47/prompts.py).
What changes once the search has stalled (the best rose by less than `stall_gain` relative over `stall_gens`
generations), and only then, so that a run that is climbing is left alone:
  5. one of the planned experiments is a step-change, with `step_budget_mult` times the budget;
  6. one deep slot goes to a challenger line: a lineage started fresh or from an alternative or another branch,
     planned by its own planner, which sees its line and the shared findings but not the overall record, and is
     judged against its own previous best. A line ends when it takes the record (merged), when it hasn't gained for
     `line_patience` generations, or after `line_max_gens`; a new one starts if the search is still stalled.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from helix4 import prompts as P4
from helix4.archive import Archive, Program, make_diff, short
from helix4.llm import FakeLLM, LLM
from helix4.run import Run as Run4, fake_answer as fake_answer4
from helix47 import prompts as P
from helix47.evaluate import evaluate
from helix47.memory import Atlas47, outcome, rel_floor

UPPER_BOUNDS = {"ac2": 1.0}          # proven bounds that the problem text already states (ac2: Hoelder)


@dataclass
class Config:
    condition: str = "v47"
    seed: int = 1
    gens: int = 20
    deep: int = 3
    wide: int = 3
    budget: float = 30.0
    researcher_effort: str = "low"
    journal_chars: int = 24000       # unused (Atlas only); kept so helix4's code paths find them
    journal_keep: int = 4
    journal_summary_chars: int = 4000
    open_k: int = 6
    mem_mb: int = 1500
    problem: str = "ac2"
    label: str = ""
    # ---- v4.7
    gain_floor: float = 1e-6         # a change is a gain only above this (relative to its start's score)
    stall_gain: float = 2e-4         # stalled: the best rose by less than this (relative) over stall_gens generations
    stall_gens: int = 3
    step_gain: float = 1e-3          # what a step-change experiment aims for (relative)
    step_budget_mult: float = 2.0    # budget of step-change and challenger experiments, times `budget`
    line_patience: int = 4           # a challenger line ends after this many generations without a gain
    line_max_gens: int = 12
    alt_min_ratio: float = 0.9       # an alternative is kept if it scores at least this times its start's score
    max_n: int = 1_000_000           # the largest construction allowed (v4: 200,000)
    map_findings: int = 45
    map_fails: int = 12
    map_works_best: int = 12
    map_works_new: int = 8
    map_questions: int = 6
    open_evidence: int = 12
    challenger_findings: int = 30


class ProblemView:
    """The problem module, with v4.7's text and size limit (the module itself is left unchanged)."""

    _lock = threading.Lock()

    def __init__(self, mod, max_n):
        self._mod = mod
        self.max_n = max(int(max_n), int(getattr(mod, "MAX_N", 0) or 0))
        self.DESCRIPTION = self._text(mod.DESCRIPTION)

    def __getattr__(self, name):
        return getattr(self._mod, name)

    def _text(self, t):
        old = getattr(self._mod, "MAX_N", None)
        if old:
            t = t.replace(f"{old:,}", f"{self.max_n:,}")
        t = t.replace("Building on it is allowed and expected: improving a good `start` is the main way progress is made.",
                      "Building on it is one way to make progress; building a different construction is another. Both "
                      "are scored the same way.")
        return t

    def check(self, arr):
        if not hasattr(self._mod, "MAX_N"):
            return self._mod.check(arr)
        with self._lock:
            old = self._mod.MAX_N
            self._mod.MAX_N = self.max_n
            try:
                return self._mod.check(arr)
            finally:
                self._mod.MAX_N = old


class Run(Run4):
    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print):
        self.dir = Path(out)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.log = log
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
        if state:
            known = {f.name for f in fields(Config)}
            cfg = Config(**{k: v for k, v in state["config"].items() if k in known})
            self.gen_done = state["gen_done"]
        else:
            cfg = cfg or Config()
            self.gen_done = -1
        if gens:
            cfg.gens = gens
        self.cfg = cfg
        self.name = cfg.label or self.dir.name
        self.problem = ProblemView(importlib.import_module(f"helix4.problems.{cfg.problem}"), cfg.max_n)
        self.problem_text = self.problem.DESCRIPTION
        self.upper_bound = UPPER_BOUNDS.get(cfg.problem)
        self.archive = Archive(self.dir)
        self.lock = threading.Lock()
        self.trace_lock = threading.Lock()
        self.trace = (self.dir / "trace.jsonl").open("a")
        self.llm = llm if llm is not None else LLM(on_call=self.record)
        if getattr(self.llm, "on_call", None) is None:
            self.llm.on_call = self.record
        self.memory = Atlas47(self)
        self.line, self.lines_closed = None, []
        if state:
            dropped = self.archive.truncate(self.gen_done)
            self.memory.truncate(self.gen_done)
            for f in ("plans.jsonl", "history.jsonl", "lines.jsonl"):
                self._truncate_jsonl(self.dir / f)
            self._load_lines()
            self.log(f"[{self.name}] resuming after generation {self.gen_done} (dropped {dropped} programs of the unfinished one)")

    # ---------------------------------------------------------------- bookkeeping
    def _jsonl(self, name):
        p = self.dir / name
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def _load_lines(self):
        rows = self._jsonl("lines.jsonl")
        if rows:
            self.line, self.lines_closed = rows[-1].get("active"), rows[-1].get("closed", [])

    def floor(self, ref):
        return rel_floor(self.cfg, ref)

    def best_curve(self):
        return [h["best"] for h in self._jsonl("history.jsonl")]

    def stalled_for(self):
        """How many generations in a row the search has been stalled (the best rose by less than stall_gain,
        relative, over the last stall_gens generations), counted up to the last finished generation."""
        b, k = self.best_curve(), self.cfg.stall_gens
        n = 0
        for i in range(len(b) - 1, k - 1, -1):
            if b[i] - b[i - k] < self.cfg.stall_gain * max(abs(b[i - k]), 1e-12):
                n += 1
            else:
                break
        return n + (k - 1 if n else 0)

    # ---------------------------------------------------------------- roles
    def researcher(self, user, gen, step="plan", system=None, role="researcher", k=None):
        system = system or P.RESEARCHER_SYSTEM.format(k=k or self.cfg.deep, budget=self.cfg.budget)
        t0 = time.time()
        text = self.call(role, system, user, temperature=0.7, max_tokens=12000, effort=self.cfg.researcher_effort, gen=gen)
        plan = P4.extract_json(text)
        retried = False
        if not (isinstance(plan, dict) and isinstance(plan.get("experiments"), list) and plan["experiments"]):
            retried = True
            text = self.call(role, system, user + "\n\n(Your previous reply could not be read. Reply with the "
                             "JSON object only.)", temperature=0.5, max_tokens=3500, effort="none", gen=gen)
            plan = P4.extract_json(text)
            if not (isinstance(plan, dict) and isinstance(plan.get("experiments"), list)):
                plan = None
        return plan, {"prompt_chars": len(user), "parsed": plan is not None, "retried": retried,
                      "seconds": round(time.time() - t0, 1)}

    def experiments(self, plan, k=None, step=False):
        k = k or self.cfg.deep
        best = self.archive.best()
        out = []
        for e in (plan or {}).get("experiments", [])[:k]:
            if not isinstance(e, dict) or not (e.get("change") or e.get("hypothesis")):
                continue
            base = str(e.get("base", "")).strip()
            p = self.archive.programs.get(base)
            step_flag = e.get("step") is True or str(e.get("step")).lower() == "true"
            e = {key: e.get(key) for key in ("base", "hypothesis", "change", "prediction", "builds_on")}
            if p is None or not p.valid:
                e["base_requested"], e["base"] = base, best.id
            if not isinstance(e.get("builds_on"), list):
                e["builds_on"] = [str(e["builds_on"])] if e.get("builds_on") else []
            if step and step_flag and not any(x.get("step") for x in out):
                e["step"] = True
            out.append(e)
        while len(out) < k:
            out.append({"base": best.id, "hypothesis": "(no plan: the researcher's reply was unusable)",
                        "change": "Improve the base program in the way you judge most promising.",
                        "prediction": "", "builds_on": [], "fallback": True})
        if step and not any(x.get("step") for x in out):       # the step-change slot is structural, not optional
            out[-1]["step"], out[-1]["step_assigned"] = True, True
        return out

    def program_block(self, p, title):
        fb = "\n".join(f"  {l}" for l in p.feedback)
        return f"## {title}: {p.line()}\nIts result:\n{fb}\n```python\n{P4.clip(p.code, 30000)}```"

    def write_code(self, role, system, user, gen):
        """helix4's, with room for a long program in the reply (16k tokens; v4's 9k cut off long programs)."""
        text = self.call(role, system, user, temperature=0.5 if role == "coder" else 0.8, max_tokens=16000,
                         effort="none", gen=gen)
        code = P4.extract_code(text)
        if code is None:
            text = self.call(role, system, user + "\n\n(Your previous reply had no complete ```python block defining "
                             "construct. Reply with the full program.)", temperature=0.4, max_tokens=16000,
                             effort="none", gen=gen)
            code = P4.extract_code(text)
        return code, P4.extract_summary(text)

    def child(self, gen, role, parent, code, intent, plan, summary, budget=None):
        budget = budget or self.cfg.budget
        p = Program(id="", gen=gen, role=role, parent=parent.id, intent=intent, code=code or "", plan=plan or {},
                    summary=summary)
        if code is None:
            p.error = "no program in the model's reply"
            return self.add(p), None
        dup = self.archive.duplicate(code, parent.id)
        if dup:
            p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
            return self.add(p), None
        p.diff = make_diff(parent.code, code)
        res = evaluate(self.problem, code, self.archive.construction(parent.id), budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        if p.valid and p.delta is not None and 0 < p.delta <= self.floor(p.start_score) and p.feedback:
            p.feedback = [p.feedback[0] + " (below the noise floor: counts as no gain)"] + p.feedback[1:]
        alt = res.get("alternative")
        alt_note = None
        if p.valid and alt is not None:
            ref = p.start_score if p.start_score is not None else p.score
            if alt["score"] >= self.cfg.alt_min_ratio * ref:
                alt_note = alt
                p.feedback = p.feedback + [f"it also handed back an alternative construction scoring {alt['score']:.6f}, "
                                           f"kept as its own program"]
            else:
                p.feedback = p.feedback + [f"its alternative construction scored {alt['score']:.6f}, below "
                                           f"{self.cfg.alt_min_ratio:g} of its start's score: not kept"]
        p = self.add(p, res["construction"])
        a = None
        if alt_note is not None:
            a = Program(id="", gen=gen, role="alt", parent=p.id, code=p.code, summary=p.summary,
                        intent=f"alternative construction handed back by {p.id} ({short(intent, 150)})",
                        plan={"alt_of": p.id, **({"line": plan["line"]} if (plan or {}).get("line") else {})},
                        valid=True, score=alt_note["score"], start_score=p.start_score,
                        delta=(alt_note["score"] - p.start_score) if p.start_score is not None else None,
                        feedback=[f"score {alt_note['score']:.6f} (an alternative handed back by {p.id})"]
                        + alt_note["feedback"][1:], cpu=0.0, n=alt_note["n"])
            a = self.add(a, alt_note["construction"])
        return p, a

    def deep_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            budget = self.cfg.budget * (self.cfg.step_budget_mult if (exp.get("step") or exp.get("line")) else 1.0)
            note = ""
            if exp.get("step"):
                note = "\n\n" + P.STEP_CODER_NOTE.format(budget=budget)
            elif exp.get("line"):
                note = "\n\n" + P.CHALLENGER_CODER_NOTE.format(budget=budget)
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Target: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. budget_seconds will be "
                    f"{budget:.0f}; `start` will be the base's construction.{note}\n\n{P4.CODE_FORMAT}")
            code, summary = self.write_code("coder", P.CODER_SYSTEM, user, gen)
            tag = f"[challenger {exp['line']}] " if exp.get("line") else "[step] " if exp.get("step") else ""
            return self.child(gen, "deep", base, code, tag + short(exp.get("hypothesis") or exp.get("change"), 300),
                              exp, summary, budget)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}")), None

    def wide_child(self, gen, parent, inspiration):
        try:
            user = f"{self.problem.DESCRIPTION}\n\n{self.program_block(parent, 'The program to improve')}\n\n"
            if inspiration is not None:
                user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                         f"{P4.clip(inspiration.code, 5000)}```\n\n")
            user += (f"Write an improved version of the program to improve. budget_seconds will be {self.cfg.budget:.0f}; "
                     f"`start` will be its construction.\n\n{P4.CODE_FORMAT}")
            code, summary = self.write_code("mutator", P.MUTATOR_SYSTEM, user, gen)
            return self.child(gen, "wide", parent, code, summary or "(no summary)", {}, summary)
        except Exception as exc:                                     # noqa: BLE001
            self.log(f"[{self.name}] gen {gen}: wide child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="wide", parent=parent.id, intent="(crashed)", code="",
                                    error=f"internal error: {exc}")), None

    # ---------------------------------------------------------------- the challenger line
    def line_programs(self, line):
        return [p for p in self.archive.programs.values() if (p.plan or {}).get("line") == line["id"]]

    def line_summary(self):
        ln = self.line
        if ln is None:
            return ""
        best = self.archive.programs.get(ln.get("best_id") or "")
        where = f"its best so far is {best.id} ({best.score:.6f})" if best is not None else "no valid program yet"
        return (f"## The challenger line\nA challenger line ({ln['id']}, since generation {ln['started']}) explores a "
                f"different region with one experiment per generation, planned separately: {where}. You plan the "
                f"main line's experiments; any program, including the challenger's, can be your base.")

    def _ancestors(self, pid):
        return {p.id for p in self.archive.lineage(pid, depth=100000)}

    def start_options(self):
        a = self.archive
        best = a.best()
        anc = self._ancestors(best.id)
        used = {r for ln in self.lines_closed for r in ln.get("roots", [])}
        seed = next((p for p in a.programs.values() if p.role == "seed"), None)
        opts, ids = [], []
        if seed is not None:
            opts.append(f"- {seed.id}: a fresh start (Code Zero, score {seed.score:.6f})")
            ids.append(seed.id)
        alts = sorted((p for p in a.valid() if p.role == "alt" and p.id not in used and p.id not in anc
                       and not (p.plan or {}).get("line")), key=lambda p: -p.score)[:4]
        for p in alts:
            opts.append(f"- {p.id}: {p.score:.6f}, an alternative construction ({short(p.intent, 120)})")
            ids.append(p.id)
        others = sorted((p for p in a.valid() if p.role not in ("alt", "seed") and p.id not in anc and p.id not in used
                         and best.id not in self._ancestors(p.id) and not (p.plan or {}).get("line")),
                        key=lambda p: -p.score)[:3]
        for p in others:
            opts.append(f"- {p.id}: {p.score:.6f}, the best of another branch ({short(p.intent, 120)})")
            ids.append(p.id)
        return opts, ids

    def start_line(self, gen):
        n = len(self.lines_closed) + 1
        self.line = {"id": f"C{n}", "started": gen, "best": None, "best_id": None, "last_gain_gen": gen,
                     "roots": [], "programs": 0}
        self.log(f"[{self.name}] gen {gen}: the search has stalled; challenger line {self.line['id']} starts")

    def challenger_experiment(self, gen):
        ln = self.line
        options, ids = (self.start_options() if ln["best_id"] is None else (None, []))
        user = self.memory.challenger_view(gen, ln, options) + "\n\n" + P.CHALLENGER_FORMAT.format(
            start_hint=", or one of the starting options" if options else "")
        system = P.CHALLENGER_SYSTEM.format(budget=self.cfg.budget * self.cfg.step_budget_mult)
        plan, info = self.researcher(user, gen, system=system, role="challenger")
        e = ((plan or {}).get("experiments") or [{}])[0]
        e = e if isinstance(e, dict) else {}
        line_ids = {p.id for p in self.line_programs(ln) if p.valid}
        base = str(e.get("base", "")).strip()
        if ln["best_id"] is None:
            if base not in ids:
                info["base_requested"], base = base, ids[0]
            ln["roots"] = list(dict.fromkeys(ln["roots"] + [base]))
        elif base not in line_ids:
            info["base_requested"], base = base, ln["best_id"]
        exp = {"base": base, "hypothesis": e.get("hypothesis") or "(no plan: the challenger's reply was unusable)",
               "change": e.get("change") or "Improve the base program in the way you judge most promising.",
               "prediction": e.get("prediction") or "", "builds_on": e.get("builds_on") if isinstance(e.get("builds_on"), list) else [],
               "line": ln["id"]}
        return exp, {"analysis": (plan or {}).get("analysis"), **info}

    def update_line(self, gen, children):
        ln = self.line
        if ln is None:
            return None
        mine = [c for c in children if c is not None and (c.plan or {}).get("line") == ln["id"]]
        ln["programs"] += len(mine)
        for c in mine:
            if c.valid and (ln["best"] is None or c.score > ln["best"] + self.floor(ln["best"])):
                ln["best"], ln["best_id"], ln["last_gain_gen"] = c.score, c.id, gen
        best = self.archive.best()
        why = None
        if ln["best_id"] is not None and best.id in {p.id for p in self.line_programs(ln)}:
            why = "merged: it took the record"
        elif gen - ln["last_gain_gen"] >= self.cfg.line_patience:
            why = f"retired: no gain for {self.cfg.line_patience} generations"
        elif gen - ln["started"] + 1 >= self.cfg.line_max_gens:
            why = f"retired: {self.cfg.line_max_gens} generations"
        if why:
            ln.update(ended=gen, why=why)
            self.lines_closed.append(ln)
            self.log(f"[{self.name}] gen {gen}: challenger line {ln['id']} {why} (best {ln['best']})")
            self.line = None
        return why

    # ---------------------------------------------------------------- the generation
    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        stalled = self.stalled_for()
        if stalled >= self.cfg.stall_gens and self.line is None and gen >= 2:
            self.start_line(gen)
        line_now = self.line
        k_main = self.cfg.deep - (1 if line_now is not None else 0)
        rng = random.Random(self.cfg.seed * 7919 + gen)
        pool = [p for p in self.archive.valid() if p.gen < gen]
        parents = [self.archive.sample_parent(rng, pool) for _ in range(self.cfg.wide)]
        top = sorted(pool, key=lambda p: -p.score)[:5]
        prev_best = self.archive.best()
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide + 1) as ex:
            wide = []
            for par in parents:
                others = [q for q in top if q.id != par.id]
                wide.append(ex.submit(self.wide_child, gen, par, rng.choice(others) if others else None))
            cfut = ex.submit(self.challenger_experiment, gen) if line_now is not None else None
            plan, info = self.memory.plan(gen, k_main, stalled)
            exps = self.experiments(plan, k_main, step=info.get("step_asked", False))
            deep = [ex.submit(self.deep_child, gen, e) for e in exps]
            cinfo = None
            if cfut is not None:
                cexp, cinfo = cfut.result()
                exps.append(cexp)
                deep.append(ex.submit(self.deep_child, gen, cexp))
            pairs = [f.result() for f in deep + wide]
        children = [c for c, _ in pairs] + [a for _, a in pairs if a is not None]
        t_mem = time.time()
        mem_info = self.memory.update(gen, plan, children) or {}
        line_event = self.update_line(gen, children)
        best = self.archive.best()
        dc = [c for c, _ in pairs[: len(deep)]]
        wc = [c for c, _ in pairs[len(deep):]]
        alts = [a for _, a in pairs if a is not None]

        def best_of(cs):
            ok = [c.score for c in cs if c is not None and c.valid]
            return max(ok) if ok else None

        def gains(cs):
            return sum(1 for c in cs if outcome(c, self.cfg) == "gain")

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        rose = best.score > prev_best.score + self.floor(prev_best.score)
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role,
               "deep_best": best_of(dc), "wide_best": best_of(wc), "deep_gains": gains(dc), "wide_gains": gains(wc),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in dc + wc if c.duplicate_of), "new_best": rose,
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "bases": [e["base"] for e in exps], "builds_on_refs": len(refs),
               "builds_on_known": sum(1 for r in refs if str(r) in self.archive.programs or str(r) in self.memory.findings),
               "stalled": stalled, "step": [c.id for c, e in zip(dc, exps) if e.get("step")],
               "challenger": ({"line": line_now["id"], "child": dc[-1].id, "score": dc[-1].score, "event": line_event}
                              if line_now is not None else None),
               "alternatives_kept": [a.id for a in alts],
               "researcher_prompt_chars": info.get("prompt_chars"), "researcher_seconds": info.get("seconds"),
               "memory_seconds": round(time.time() - t_mem, 1), "calls": self.llm.calls - calls0,
               "seconds": round(time.time() - t0, 1), **self.memory.stats()}
        self._append("plans.jsonl", {"gen": gen, "plan": plan, "experiments": exps, "info": info,
                                     "challenger": cinfo, "memory": mem_info})
        self._append("history.jsonl", row)
        self._append("lines.jsonl", {"gen": gen, "active": self.line, "closed": self.lines_closed})
        self.checkpoint(gen)
        extra = []
        if line_now is not None:
            extra.append(f"challenger {line_now['id']} {dc[-1].score:.6f}" if dc[-1].valid else f"challenger {line_now['id']} failed")
        if row["step"]:
            extra.append("step " + ",".join(row["step"]))
        if alts:
            extra.append(f"{len(alts)} alternatives kept")
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}); deep "
                 f"{row['deep_best'] or 0:.6f} ({row['deep_gains']}/{len(dc)} gained), wide {row['wide_best'] or 0:.6f} "
                 f"({row['wide_gains']}/{len(wc)} gained)" + (f"; {'; '.join(extra)}" if extra else "")
                 + f"; {row['seconds']:.0f} s")
        return row

    def finish(self, seconds=None, stopped_at=None):
        summary = super().finish(seconds, stopped_at)
        summary["lines"] = self.lines_closed + ([self.line] if self.line else [])
        summary["alternatives"] = sum(1 for p in self.archive.programs.values() if p.role == "alt")
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
        return summary


# ---------------------------------------------------------------------------------------------- the fake model
FAKE_CODE = '''import numpy as np, time
# fake variant {tag}


def construct(budget_seconds, start):
    rng = np.random.default_rng({tag})
    h = np.ones(40) if start is None else np.asarray(start, dtype=float).copy()

    def score(h):
        g = np.concatenate(([0.0], np.convolve(h, h), [0.0]))
        a, b = g[:-1], g[1:]
        return np.sum(a * a + a * b + b * b) / 3 / (h.sum() ** 2 * g.max())

    best, t = score(h), time.process_time()
    while time.process_time() - t < min(0.6, 0.3 * budget_seconds):
        k = rng.integers(len(h))
        old = h[k]
        h[k] = max(0.0, h[k] * (1 + 0.3 * rng.standard_normal()))
        s = score(h)
        if s > best:
            best = s
        else:
            h[k] = old
    alt = h * (1 + 0.05 * rng.random(len(h)))
    print("fake search reached", round(best, 6))
    return {"best": h, "alternative": alt}
'''


def fake_answer(role, system, user):
    if role in ("coder", "mutator"):
        return "```python\n" + FAKE_CODE.replace("{tag}", str(random.randint(1, 10 ** 9))) + "```\nSUMMARY: fake search"
    if role == "challenger":
        ids = re.findall(r"\bp\d{4}\b", user)
        exp = {"base": ids[0] if ids else "p0001", "hypothesis": "fake challenger hypothesis", "change": "perturb",
               "prediction": "a gain on the line", "builds_on": []}
        return "```json\n" + json.dumps({"analysis": "fake", "experiments": [exp]}) + "\n```"
    if role == "researcher":
        k = int(m.group(1)) if (m := re.search(r"Give exactly (\d+) experiments", user)) else 3
        ids = re.findall(r"\bp\d{4}\b", user)
        base = ids[0] if ids else "p0001"
        exps = [{"base": base, "hypothesis": f"fake hypothesis {i}", "change": f"perturb heights, variant {i}",
                 "prediction": "a small gain", "builds_on": ids[:1]} for i in range(k)]
        return "```json\n" + json.dumps({"analysis": "fake analysis", "experiments": exps}) + "\n```"
    return fake_answer4(role, system, user)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--deep", type=int, default=3)
    ap.add_argument("--wide", type=int, default=3)
    ap.add_argument("--effort", default="low", help="the Researcher's thinking effort")
    ap.add_argument("--label", default="")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model writes random-search programs)")
    a = ap.parse_args(argv)
    cfg = Config(seed=a.seed, gens=a.gens or 20, budget=a.budget, deep=a.deep, wide=a.wide,
                 researcher_effort=a.effort, label=a.label)
    llm = FakeLLM(fake_answer) if a.fake else None
    run = Run(a.out, cfg, llm=llm, gens=a.gens, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()


if __name__ == "__main__":
    sys.exit(main())
