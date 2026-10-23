"""One Helix v4.7 run: v4 (helix4/run.py, Atlas memory) with the deep loop organised in lines (docs/V47_DESIGN.md).

    python -m helix47.run --seed 1 --gens 30 --out runs/v47/v47-s1
    python -m helix47.run --out runs/v47/v47-s1                 # resumes (state.json is there)
    python -m helix47.run --gens 2 --fake --out /tmp/x          # no model calls

The roles, the two loops and the Atlas memory are v4's. What changes is what the deep loop works on.

A line is one lineage of constructions with its own best score. A run starts with one line, L1, from Code Zero, and
all `deep` planned experiments go to it, as in v4. Every experiment is judged against its line's best. The system,
not the planner, manages the lines:
- a line whose best rose by less than `stall_gain` (relative) over its last `line_patience` generations is closed:
  its programs and findings stay, but it gets no more experiments;
- when a line closes, new lines open, up to `lines_after_stall` active lines, each from a different starting point,
  in turn: the best kept alternative construction (fix 1 below), the best program of another branch (one that does
  not descend from any line's best), or a fresh start from Code Zero;
- the `deep` slots are shared out each generation: one per active line, and the rest to the line that gained most
  over its last two generations (a new line counts as gaining).
The planner sees each active line against its own previous generations, and the closed lines by name only (helix47/
memory.py). It is never asked whether a construction is saturated, so the model's habit of reading a plateau as a
limit has nothing to act on: a stalled line is closed by code, and the effort moves.

The wide loop is a halo around the active lines: its parents are sampled from their programs.

Also always on:
  1. a program may hand back an alternative construction, which is scored and kept as its own program (role "alt");
     in v4, 72% of late children returned their start unchanged, so new ideas were invisible;
  2. gains count only above a noise floor (`gain_floor`, relative), everywhere;
  3. the findings are balanced and scoped to their line; no countdown; targets instead of confirm-or-refute;
  4. up to `max_n` steps; base programs shown up to 30,000 characters; 16,000-token replies.
"""
from __future__ import annotations

import argparse
import importlib
import json
import random
import re
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from pathlib import Path

from helix4 import prompts as P4
from helix4.archive import Archive, Program, make_diff, short
from helix4.llm import FakeLLM, LLM
from helix4.run import Run as Run4, fake_answer as fake_answer4
from helix47 import prompts as P
from helix47.evaluate import evaluate
from helix47.memory import Atlas47, outcome, rel_floor

UPPER_BOUNDS = {"ac2": 1.0}          # proven bounds that the problem text already states (ac2: Hoelder)
SOURCES = ("alternative", "branch", "fresh")


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
    stall_gain: float = 2e-4         # a line is closed if its best rose by less than this (relative) ...
    line_patience: int = 4           # ... over this many generations
    lines_after_stall: int = 2       # active lines once the first line has closed (at most `deep`)
    branch_gap: float = 0.01         # another branch: it split from every line's best at a point this much lower (rel)
    alt_min_ratio: float = 0.9       # an alternative is kept if it scores at least this times its start's score
    max_n: int = 1_000_000           # the largest construction allowed (v4: 200,000)
    line_code_chars: int = 12000     # how much of each line's best program the planner sees
    map_findings: int = 45
    map_fails: int = 10
    map_works_best: int = 12
    map_works_new: int = 8
    map_questions: int = 6
    open_evidence: int = 12


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
    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print, problem=None):
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
        self.problem = problem or ProblemView(importlib.import_module(f"helix4.problems.{cfg.problem}"), cfg.max_n)
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
        self.lines = []
        if state:
            dropped = self.archive.truncate(self.gen_done)
            self.memory.truncate(self.gen_done)
            for f in ("plans.jsonl", "history.jsonl", "lines.jsonl"):
                self._truncate_jsonl(self.dir / f)
            rows = self._jsonl("lines.jsonl")
            self.lines = rows[-1]["lines"] if rows else []
            self.log(f"[{self.name}] resuming after generation {self.gen_done} (dropped {dropped} programs of the unfinished one)")

    # ---------------------------------------------------------------- bookkeeping
    def _jsonl(self, name):
        p = self.dir / name
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def floor(self, ref):
        return rel_floor(self.cfg, ref)

    # ---------------------------------------------------------------- lines
    def line_of(self, p):
        if p is None:
            return None
        return (p.plan or {}).get("line") or "L1"

    def active_lines(self):
        return [ln for ln in self.lines if ln["status"] == "active"]

    def closed_lines(self):
        return [ln for ln in self.lines if ln["status"] == "closed"]

    def members(self, ln):
        """The programs a line's experiments may build on: its own programs and its root."""
        ids = {p.id for p in self.archive.programs.values() if p.valid and self.line_of(p) == ln["id"]}
        return ids | {ln["root"]}

    def line_moves(self, ln, k=6):
        out, prev = [], None
        for g, b in ln["curve"][-(k + 1):]:
            if prev is None:
                prev = b
                continue
            d = b - prev
            out.append(f"g{g} {b:.6f} ({d:+.6f})" if d > self.floor(prev) else f"g{g} no gain")
            prev = b
        return out

    def open_line(self, gen, root, source, kind="fresh"):
        n = len(self.lines) + 1
        ln = {"id": f"L{n}", "root": root.id, "source": source, "kind": kind, "started": gen, "status": "active",
              "best": root.score, "best_id": root.id, "curve": [[gen - 1, root.score]], "ended": None, "why": None}
        self.lines.append(ln)
        self.log(f"[{self.name}] gen {gen}: line {ln['id']} opens from {source}")
        return ln

    def _distinct(self, p):
        """True if p is on another branch: for every line's best b, p and b split at a program scoring at least
        `branch_gap` (relative) below b, so p is not a polish of b, nor on b's own path."""
        a = self.archive
        mine = [q.id for q in reversed(a.lineage(p.id, depth=100000))]          # p first, then its ancestors
        for ln in self.lines:
            b = a.programs.get(ln["best_id"])
            if b is None or b.score is None:
                continue
            anc = {q.id for q in a.lineage(b.id, depth=100000)}
            lca = next((i for i in mine if i in anc), None)
            if lca == p.id or (lca is not None and a.programs[lca].score is not None
                               and a.programs[lca].score > b.score - self.cfg.branch_gap * abs(b.score)):
                return False
        return True

    def pick_root(self, gen):
        """The next starting point for a new line, taking the sources in turn (alternative, branch, fresh)."""
        a = self.archive
        used = {ln["root"] for ln in self.lines} | {ln["best_id"] for ln in self.lines}
        opened = max(0, len(self.lines) - 1)
        active = Counter(ln.get("kind") for ln in self.active_lines())
        # the sources in turn, but a kind the active lines already have goes last, and never two fresh starts at once
        order = sorted(range(len(SOURCES)), key=lambda i: (active[SOURCES[(opened + i) % len(SOURCES)]], i))
        for i in order:
            src = SOURCES[(opened + i) % len(SOURCES)]
            if src == "fresh" and active["fresh"]:
                continue
            if src == "alternative":
                cands = [p for p in a.valid() if p.role == "alt" and p.id not in used]
                if cands:
                    p = max(cands, key=lambda q: q.score)
                    return p, f"an alternative construction ({p.id}, handed back by {p.parent})", src
            elif src == "branch":
                cands = [p for p in a.valid() if p.role not in ("alt", "seed") and p.id not in used and self._distinct(p)]
                if cands:
                    p = max(cands, key=lambda q: q.score)
                    return p, f"another branch ({p.id})", src
            else:
                seed = next((p for p in a.programs.values() if p.role == "seed"), None)
                if seed is not None:
                    return seed, "a fresh start (Code Zero)", src
        return None, None, None

    def update_lines(self, gen, children):
        events = []
        for ln in self.active_lines():
            mine = [c for c in children if c is not None and c.valid and self.line_of(c) == ln["id"]]
            for c in sorted(mine, key=lambda c: -c.score):
                if c.score > ln["best"] + self.floor(ln["best"]):
                    ln["best"], ln["best_id"] = c.score, c.id
                break
            ln["curve"].append([gen, ln["best"]])
            k = self.cfg.line_patience
            if len(ln["curve"]) > k:
                old = ln["curve"][-1 - k][1]
                if ln["best"] - old < self.cfg.stall_gain * max(abs(old), 1e-12):
                    ln.update(status="closed", ended=gen,
                              why=f"its best rose by less than {self.cfg.stall_gain:g} (relative) in {k} generations")
                    events.append(f"{ln['id']} closed")
                    self.log(f"[{self.name}] gen {gen}: line {ln['id']} closes (best {ln['best']:.6f})")
        target = 1 if not self.closed_lines() else min(self.cfg.lines_after_stall, self.cfg.deep)
        while len(self.active_lines()) < target:
            root, source, kind = self.pick_root(gen + 1)
            if root is None:
                break
            ln = self.open_line(gen + 1, root, source, kind)
            events.append(f"{ln['id']} opened from {source}")
        return events

    def allocation(self):
        act = self.active_lines()[: self.cfg.deep]
        alloc = {ln["id"]: 1 for ln in act}

        def rate(ln):
            c = ln["curve"]
            if len(c) < 3:
                return float("inf")           # a new line counts as gaining
            return (c[-1][1] - c[-3][1]) / max(abs(c[-3][1]), 1e-12)
        if act:
            lead = max(act, key=lambda ln: (rate(ln), ln["started"]))
            alloc[lead["id"]] += self.cfg.deep - len(act)
        return alloc

    # ---------------------------------------------------------------- roles
    def researcher_system(self, k):
        return P.RESEARCHER_SYSTEM.format(k=k, budget=self.cfg.budget)

    def researcher(self, user, gen, step="plan", system=None, role="researcher", k=None):
        system = system or self.researcher_system(k or self.cfg.deep)
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

    def experiments(self, plan, alloc):
        lines = {ln["id"]: ln for ln in self.active_lines()}
        left = dict(alloc)
        out = []
        for e in (plan or {}).get("experiments", []):
            if not isinstance(e, dict) or not (e.get("change") or e.get("hypothesis")) or not any(left.values()):
                continue
            lid = str(e.get("line", "")).strip()
            if left.get(lid, 0) <= 0:
                e = {**e, "line_requested": lid}
                lid = next(l for l, n in left.items() if n > 0)
            ln = lines[lid]
            base = str(e.get("base", "")).strip()
            x = {key: e.get(key) for key in ("base", "hypothesis", "change", "prediction", "builds_on")}
            x["line"] = lid
            if "line_requested" in e:
                x["line_requested"] = e["line_requested"]
            if base not in self.members(ln):
                x["base_requested"], x["base"] = base, ln["best_id"]
            if not isinstance(x.get("builds_on"), list):
                x["builds_on"] = [str(x["builds_on"])] if x.get("builds_on") else []
            out.append(x)
            left[lid] -= 1
        for lid, n in left.items():
            for _ in range(n):
                out.append({"line": lid, "base": lines[lid]["best_id"],
                            "hypothesis": "(no plan: the researcher's reply was unusable)",
                            "change": "Improve the base program in the way you judge most promising.",
                            "prediction": "", "builds_on": [], "fallback": True})
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

    def child(self, gen, role, parent, code, intent, plan, summary):
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
        res = evaluate(self.problem, code, self.archive.construction(parent.id), self.cfg.budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        if p.valid and p.delta is not None and 0 < p.delta <= self.floor(p.start_score) and p.feedback:
            p.feedback = [p.feedback[0] + " (below the noise floor: counts as no gain)"] + p.feedback[1:]
        alt, keep = res.get("alternative"), None
        if p.valid and alt is not None:
            ref = p.start_score if p.start_score is not None else p.score
            if alt["score"] >= self.cfg.alt_min_ratio * ref:
                keep = alt
                p.feedback = p.feedback + [f"it also handed back an alternative construction scoring {alt['score']:.6f}, "
                                           f"kept as its own program"]
            else:
                p.feedback = p.feedback + [f"its alternative construction scored {alt['score']:.6f}, below "
                                           f"{self.cfg.alt_min_ratio:g} of its start's score: not kept"]
        p = self.add(p, res["construction"])
        a = None
        if keep is not None:
            a = Program(id="", gen=gen, role="alt", parent=p.id, code=p.code, summary=p.summary,
                        intent=f"alternative construction handed back by {p.id} ({short(intent, 150)})",
                        plan={"alt_of": p.id, "line": (plan or {}).get("line") or "L1"},
                        valid=True, score=keep["score"], start_score=p.start_score,
                        delta=(keep["score"] - p.start_score) if p.start_score is not None else None,
                        feedback=[f"score {keep['score']:.6f} (an alternative handed back by {p.id})"]
                        + keep["feedback"][1:], cpu=0.0, n=keep["n"])
            a = self.add(a, keep["construction"])
        return p, a

    def deep_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            ln = next((l for l in self.lines if l["id"] == exp["line"]), None)
            note = ""
            if ln is not None and ln["id"] != "L1" and gen - ln["started"] < 2:
                note = "\n\n" + P.NEW_LINE_NOTE.format(source=ln["source"])
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Target: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. budget_seconds will be "
                    f"{self.cfg.budget:.0f}; `start` will be the base's construction.{note}\n\n{P4.CODE_FORMAT}")
            code, summary = self.write_code("coder", P.CODER_SYSTEM, user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp, summary)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}")), None

    def wide_child(self, gen, parent, inspiration, line_id):
        try:
            user = f"{self.problem.DESCRIPTION}\n\n{self.program_block(parent, 'The program to improve')}\n\n"
            if inspiration is not None:
                user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                         f"{P4.clip(inspiration.code, 5000)}```\n\n")
            user += (f"Write an improved version of the program to improve. budget_seconds will be {self.cfg.budget:.0f}; "
                     f"`start` will be its construction.\n\n{P4.CODE_FORMAT}")
            code, summary = self.write_code("mutator", P.MUTATOR_SYSTEM, user, gen)
            return self.child(gen, "wide", parent, code, summary or "(no summary)", {"line": line_id}, summary)
        except Exception as exc:                                     # noqa: BLE001
            self.log(f"[{self.name}] gen {gen}: wide child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="wide", parent=parent.id, intent="(crashed)", code="",
                                    plan={"line": line_id}, error=f"internal error: {exc}")), None

    def wide_parents(self, rng, gen):
        """The halo: parents sampled from the active lines' programs (and their roots)."""
        pools = []
        for ln in self.active_lines():
            ids = self.members(ln)
            pools += [(p, ln["id"]) for p in self.archive.valid() if p.id in ids and p.gen < gen]
        if not pools:
            return []
        line_of = {p.id: lid for p, lid in pools}
        progs = list({p.id: p for p, _ in pools}.values())
        out = []
        for _ in range(self.cfg.wide):
            par = self.archive.sample_parent(rng, progs)
            out.append((par, line_of[par.id]))
        return out

    # ---------------------------------------------------------------- the generation
    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        if not self.lines:
            seed = next(p for p in self.archive.programs.values() if p.role == "seed")
            self.open_line(gen, seed, "Code Zero", "seed")
        alloc = self.allocation()
        rng = random.Random(self.cfg.seed * 7919 + gen)
        parents = self.wide_parents(rng, gen)
        pool = [p for p, _ in parents]
        top = sorted({p.id: p for p in self.archive.valid() if p.gen < gen and self.line_of(p) in alloc}.values(),
                     key=lambda p: -p.score)[:5]
        prev_best = self.archive.best()
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide) as ex:
            wide = []
            for par, lid in parents:
                others = [q for q in top if q.id != par.id]
                wide.append(ex.submit(self.wide_child, gen, par, rng.choice(others) if others else None, lid))
            plan, info = self.memory.plan(gen, alloc)
            exps = self.experiments(plan, alloc)
            deep = [ex.submit(self.deep_child, gen, e) for e in exps]
            pairs = [f.result() for f in deep + wide]
        children = [c for c, _ in pairs] + [a for _, a in pairs if a is not None]
        t_mem = time.time()
        mem_info = self.memory.update(gen, plan, children) or {}
        events = self.update_lines(gen, children)
        best = self.archive.best()
        dc = [c for c, _ in pairs[: len(deep)]]
        wc = [c for c, _ in pairs[len(deep):]]
        alts = [a for _, a in pairs if a is not None]

        def best_of(cs):
            ok = [c.score for c in cs if c is not None and c.valid]
            return max(ok) if ok else None

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role, "best_line": self.line_of(best),
               "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": sum(1 for c in dc if outcome(c, self.cfg) == "gain"),
               "wide_gains": sum(1 for c in wc if outcome(c, self.cfg) == "gain"),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in dc + wc if c.duplicate_of),
               "new_best": best.score > prev_best.score + self.floor(prev_best.score),
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "bases": [e["base"] for e in exps], "allocation": alloc, "line_events": events,
               "lines": [{"id": ln["id"], "best": ln["best"], "status": ln["status"]} for ln in self.lines],
               "alternatives_kept": [a.id for a in alts], "builds_on_refs": len(refs),
               "builds_on_known": sum(1 for r in refs if str(r) in self.archive.programs or str(r) in self.memory.findings),
               "researcher_prompt_chars": info.get("prompt_chars"), "researcher_seconds": info.get("seconds"),
               "memory_seconds": round(time.time() - t_mem, 1), "calls": self.llm.calls - calls0,
               "seconds": round(time.time() - t0, 1), **self.memory.stats()}
        self._append("plans.jsonl", {"gen": gen, "plan": plan, "experiments": exps, "info": info, "memory": mem_info})
        self._append("history.jsonl", row)
        self._append("lines.jsonl", {"gen": gen, "lines": self.lines})
        self.checkpoint(gen)
        lines_txt = ", ".join(f"{lid} x{n} {next(l['best'] for l in self.lines if l['id'] == lid):.6f}" for lid, n in alloc.items())
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}, line {self.line_of(best)}); "
                 f"lines {lines_txt}; deep {row['deep_gains']}/{len(dc)} gained, wide {row['wide_gains']}/{len(wc)} gained"
                 + (f"; {len(alts)} alternatives kept" if alts else "") + (f"; {'; '.join(events)}" if events else "")
                 + f"; {row['seconds']:.0f} s")
        return row

    def finish(self, seconds=None, stopped_at=None):
        summary = super().finish(seconds, stopped_at)
        summary["lines"] = self.lines
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
    if role == "researcher":
        alloc = re.findall(r"(\d+) for line (L\d+)", user.split("Give exactly")[-1])
        exps = []
        for n, lid in alloc:
            block = user.split(f"## Line {lid}:")[1] if f"## Line {lid}:" in user else user
            ids = re.findall(r"\bp\d{4}\b", block)
            for i in range(int(n)):
                exps.append({"line": lid, "base": ids[0] if ids else "p0001", "hypothesis": f"fake hypothesis {i}",
                             "change": f"perturb heights, variant {i}", "prediction": "a gain", "builds_on": ids[:1]})
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
