"""One Helix v4.5 or v5 run. Same loop as v4 (helix4/run.py), with the fixes the v4 overnight run showed:

    python -m helix5.run --condition v45 --seed 1 --gens 20 --out runs/v5/v45-s1
    python -m helix5.run --condition v5  --seed 1 --gens 20 --out runs/v5/v5-s1
    python -m helix5.run --out runs/v5/v5-s1            # resumes (state.json is there)
    python -m helix5.run --condition v5 --gens 2 --fake --out /tmp/x    # no model calls

Each generation: the wide loop (memoryless Mutator, identical to v4) writes `wide` children; the deep loop's planner
(v4.5: Atlas+; v5: the researcher) plans `deep` experiments and Coders write them; every child is run, checked,
scored and described; the memory is updated.

Changes from v4's engine:
- experiments can start fresh (no start construction) and carry their if/then and agenda item;
- evaluator: 8 printed lines back, unused budget stated, gains labelled by size (helix5/evaluate.py);
- coders are told to use the whole budget and return the best they found (prompts.CODE_RULES);
- a portfolio of slot roles every generation, assigned by code (see PORTFOLIO below), instead of 3 free slots;
- history counts real gains (>= 1e-5), not 1e-9 polishing, and "new_best" means the record actually rose.

PORTFOLIO. The v4 run and the first v5 tests showed the planner narrowing: with 3 free slots, spending all of them on
the most promising line always looks locally right, so the population went unused and runs stalled on one
construction. The fix is structural: each generation's planned experiments have roles, assigned by code.
- deepen: build on the best line (the best program or one of its ancestors). Depth never stops.
- branch: build from a different point: the best program of another line, or an earlier point of the best line where
  a big gain happened (a fork point). Candidates are listed by code, young lines first, so new lines get to mature.
- explore: a genuinely different construction, from scratch (no start construction). It starts a new line.
- challenge (v5 only, every few rounds): an experiment designed to break one of the researcher's beliefs.
Default: deepen, branch, explore. On a hot streak (the record rose by HOT_EPS or more last generation, on the best
line): deepen, deepen, and branch or explore alternately. Generation 1: deepen, explore, explore.
A line is the set of programs descending from one root: Code Zero or a fresh start.
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

import numpy as np

from helix4.archive import Archive, Program, make_diff, short
from helix4.llm import FakeLLM, LLMError
from helix5.llm import LLM
from helix5 import prompts as P
from helix5.evaluate import GAIN_EPS, evaluate, gain_label

STALL_EPS = 1e-4
HOT_EPS = 1e-3
ROLES = ("deepen", "branch", "explore", "challenge")


@dataclass
class Config:
    condition: str = "v45"
    seed: int = 1
    gens: int = 20
    deep: int = 3
    wide: int = 3
    budget: float = 30.0
    researcher_effort: str = "low"
    open_k: int = 6
    lookup_k: int = 5
    review_every: int = 5
    stall_gens: int = 3
    challenge_every: int = 3
    mem_mb: int = 1500
    problem: str = "ac2"
    label: str = ""


def modes():
    from helix5.v45 import AtlasPlus
    from helix5.v5 import Researcher
    return {"v45": AtlasPlus, "v5": Researcher}


class Run:
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
        self.problem = importlib.import_module(f"helix4.problems.{cfg.problem}")
        self.archive = Archive(self.dir)
        self.lock = threading.Lock()
        self.trace_lock = threading.Lock()
        self.trace = (self.dir / "trace.jsonl").open("a")
        self.llm = llm if llm is not None else LLM(on_call=self.record)
        if getattr(self.llm, "on_call", None) is None:
            self.llm.on_call = self.record
        self.memory = modes()[cfg.condition](self)
        if state:
            dropped = self.archive.truncate(self.gen_done)
            self.memory.truncate(self.gen_done)
            for f in ("plans.jsonl", "history.jsonl"):
                self._truncate_jsonl(self.dir / f)
            self.log(f"[{self.name}] resuming after generation {self.gen_done} (dropped {dropped} programs of the unfinished one)")

    # ---------------------------------------------------------------- bookkeeping
    def _truncate_jsonl(self, path):
        if path.exists():
            rows = [l for l in path.read_text().splitlines() if l.strip() and json.loads(l).get("gen", -1) <= self.gen_done]
            path.write_text("".join(r + "\n" for r in rows))

    def _append(self, name, row):
        with self.lock, (self.dir / name).open("a") as f:
            f.write(json.dumps(row, default=float) + "\n")

    def history(self):
        p = self.dir / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def record(self, call):
        call = {"t": round(time.time(), 1), "run": self.name, **call}
        with self.trace_lock:
            self.trace.write(json.dumps(call) + "\n")
            self.trace.flush()

    def call(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", gen=None, grow=True):
        kw = {"grow": grow} if getattr(self.llm, "supports_grow", False) else {}
        try:
            return self.llm.chat(role, system, user, temperature=temperature, max_tokens=max_tokens, effort=effort,
                                 meta={"gen": gen}, **kw).text
        except LLMError as exc:
            self.log(f"[{self.name}] gen {gen}: {role} call failed: {exc}")
            return ""

    def add(self, p: Program, construction=None):
        with self.lock:
            p.id = self.archive.new_id()
            self.archive.add(p, construction)
        return p

    # ---------------------------------------------------------------- progress facts (computed, shown to planners)
    def last_rise(self, gen):
        """The last generation (before gen) in which the best score rose by at least STALL_EPS over the record."""
        hist = [h for h in self.history() if h["gen"] < gen]
        last, record = 0, hist[0]["best"] if hist else 0.0
        for h in hist[1:]:
            if h["best"] >= record + STALL_EPS:
                last, record = h["gen"], h["best"]
        return last

    def stall(self, gen):
        """Generations (up to gen-1) since the best score last rose by at least STALL_EPS over the previous record."""
        hist = [h for h in self.history() if h["gen"] < gen]
        if len(hist) < 2:
            return 0
        return hist[-1]["gen"] - self.last_rise(gen)

    def tried_since_rise(self, gen, k=12):
        """The planned experiments since the last rise of the record, with results (newest first, at most k)."""
        last = self.last_rise(gen)
        ps = [p for p in self.archive.programs.values() if p.role == "deep" and last < p.gen < gen]
        ps.sort(key=lambda p: (-p.gen, p.id))
        out = []
        for p in ps[:k]:
            if not p.valid:
                res = "failed"
            elif p.delta is None:
                res = f"{p.score:.6f} (fresh start)"
            else:
                res = f"{p.score:.6f} ({p.delta:+.6f}, {gain_label(p.delta)})"
            role = (p.plan or {}).get("role", "")
            out.append(f"- {p.id} (gen {p.gen}{', ' + role if role else ''}) on {p.parent}: {short(p.intent, 150)} -> {res}")
        return last, out

    def progress_block(self, gen):
        hist = [h for h in self.history() if h["gen"] < gen]
        if len(hist) < 2:
            return "## Progress check (computed)\nThis is the first generation."
        cur = hist[-1]["best"]
        back = hist[max(0, len(hist) - 4)]["best"]
        s = self.stall(gen)
        best = self.archive.best()
        lines = [f"## Progress check (computed)",
                 f"Best score {cur:.6f} ({best.id}); {len(hist) - 1 - max(0, len(hist) - 4)} generations ago it was "
                 f"{back:.6f} ({cur - back:+.6f})."]
        if s >= 1:
            lines.append(f"The best score has not risen by {STALL_EPS} or more for {s} generation(s).")
        if s >= 2:
            last, tried = self.tried_since_rise(gen)
            if tried:
                lines.append(f"\nWhat the planned experiments tried since generation {last} (the last rise), newest first:")
                lines += tried
                lines.append("Before planning, group these by the kind of change they made (for example: a different "
                             "objective or surrogate, a constraint or reformulation, more resolution, a new search "
                             "method, a new starting family, more budget for a stage). At least one experiment this "
                             "round must make a kind of change that none of them made; say which kind in its hypothesis.")
        return "\n".join(lines)

    def best_line(self):
        b = self.archive.best()
        return {p.id for p in self.archive.lineage(b.id, depth=1000)}

    # ---------------------------------------------------------------- lines and the portfolio
    def root_of(self, p):
        """The root of p's line: the nearest ancestor (or p itself) that is Code Zero or a fresh start."""
        a = self.archive.programs
        while p is not None:
            if p.parent is None or (p.plan or {}).get("fresh"):
                return p.id
            p = a.get(p.parent)
        return None

    def lines(self, before_gen=None):
        """{root id: [valid programs of that line]}, optionally only programs made before a generation."""
        out = {}
        for p in self.archive.valid():
            if before_gen is not None and p.gen >= before_gen:
                continue
            out.setdefault(self.root_of(p), []).append(p)
        return out

    def roles(self, gen):
        """The roles of this generation's planned slots (see PORTFOLIO in the module docstring); fixed once per
        generation, so the planner's view and the enforcement agree."""
        cache = self.__dict__.setdefault("_roles_cache", {})
        if gen not in cache:
            cache[gen] = self._compute_roles(gen)
        return list(cache[gen])

    def _compute_roles(self, gen):
        if gen <= 1:
            roles = ["deepen", "explore", "explore"]
        else:
            hist = [h for h in self.history() if h["gen"] < gen]
            rises = [b["best"] - a["best"] for a, b in zip(hist, hist[1:])]
            hot = bool(rises) and (rises[-1] >= HOT_EPS or (len(rises) >= 2 and min(rises[-2:]) >= STALL_EPS))
            roles = ["deepen", "deepen", "branch" if gen % 2 == 0 else "explore"] if hot else ["deepen", "branch", "explore"]
        roles = (roles + ["explore"] * self.cfg.deep)[: self.cfg.deep]
        return self.memory.adjust_roles(gen, roles) if hasattr(self.memory, "adjust_roles") else roles

    def branch_candidates(self, gen, k=6):
        """Where a branch slot may build from, with why: the best of each other line (young lines first), fork points
        on the best line (ancestors where a big gain happened), then strong programs off the best line."""
        best = self.archive.best()
        line = [q.id for q in self.archive.lineage(best.id, depth=1000)]
        inc_root = self.root_of(best)
        out, seen = [], {best.id}
        others = []
        for root, ps in self.lines(before_gen=gen).items():
            if root == inc_root:
                continue
            top = max(ps, key=lambda q: q.score)
            rp = self.archive.programs[root]
            others.append((rp.gen, top, f"best of the line started by {root} (gen {rp.gen}): {top.score:.6f}"))
        for _, top, why in sorted(others, key=lambda x: (-x[0], -x[1].score)):       # young lines first
            out.append((top, why))
        for pid in reversed(line[:-2]):
            q = self.archive.programs[pid]
            if q.valid and q.delta is not None and q.delta >= HOT_EPS:
                out.append((q, f"fork point on the best line (gen {q.gen}, {q.delta:+.6f} there): {q.score:.6f}"))
        for q in self.archive.ranked():
            if q.id not in line and q.gen < gen:
                out.append((q, f"strong program off the best line: {q.score:.6f}"))
        res = []
        for q, why in out:
            if q.id not in seen:
                seen.add(q.id)
                res.append((q, why))
        return res[:k]

    def portfolio_block(self, gen):
        roles = self.roles(gen)
        best = self.archive.best()
        desc = {"deepen": f"build on the best line (best: {best.id}, {best.score:.6f}, or one of its ancestors)",
                "branch": "build from a different point: pick one of the branch candidates below",
                "explore": "a genuinely different construction, started from scratch (no start construction); the base "
                           "is only a code template",
                "challenge": "an experiment designed to break one of your beliefs (name it in \"challenges\")"}
        out = [f"## This generation's slots (assigned by the system: depth and breadth every generation)"]
        out += [f"{i + 1}. {r}: {desc[r]}" for i, r in enumerate(roles)]
        cands = self.branch_candidates(gen)
        if "branch" in roles and cands:
            out.append("Branch candidates:")
            out += [f"- {q.id}: {why}" for q, why in cands]
        lines = self.lines(before_gen=gen)
        if len(lines) > 1:
            out.append(f"Lines so far: {len(lines)} (" + ", ".join(
                f"{r}: best {max(q.score for q in ps):.6f}" for r, ps in sorted(lines.items(), key=lambda kv: -max(q.score for q in kv[1]))[:6]) + ")")
        return "\n".join(out), roles

    # ---------------------------------------------------------------- roles
    def researcher(self, system, user, gen, max_tokens=20000, effort=None, role="researcher", need="experiments"):
        """A planning call at the planner's effort, capped: if it thinks past its budget (20k answer + 12k thinking
        room) or replies unreadably, it is asked once more without thinking, which answers in seconds."""
        t0 = time.time()
        text = self.call(role, system, user, temperature=0.7, max_tokens=max_tokens,
                         effort=effort or self.cfg.researcher_effort, gen=gen, grow=False)
        plan = P.extract_json(text)
        retried = False
        ok = lambda pl: isinstance(pl, dict) and (need is None or (isinstance(pl.get(need), list) and pl[need]))  # noqa: E731
        if not ok(plan):
            retried = True
            text = self.call(role, system, user + "\n\n(Your previous reply could not be read. Reply with the JSON "
                             "object only.)", temperature=0.5, max_tokens=4000, effort="none", gen=gen)
            plan = P.extract_json(text)
            if not ok(plan):
                plan = None
        return plan, {"prompt_chars": len(user), "parsed": plan is not None, "retried": retried,
                      "seconds": round(time.time() - t0, 1)}

    def experiments(self, plan, gen):
        """Validated experiments, one per slot role (deepen / branch / explore / challenge), constraints enforced."""
        best = self.archive.best()
        line = [q.id for q in self.archive.lineage(best.id, depth=1000)]
        roles = self.roles(gen)
        cands = [q.id for q, _ in self.branch_candidates(gen)]
        keep = ("base", "fresh", "role", "hypothesis", "change", "prediction", "if_gain", "if_not", "builds_on", "item",
                "step", "challenges")
        given = []
        for e in (plan or {}).get("experiments", []):
            if isinstance(e, dict) and (e.get("change") or e.get("hypothesis")):
                given.append({k: e.get(k) for k in keep if k in e})
        # match experiments to roles: by their stated role first, then in order
        slots = [None] * len(roles)
        rest = []
        for e in given:
            r = str(e.get("role", "")).lower()
            idx = next((i for i, rr in enumerate(roles) if rr == r and slots[i] is None), None)
            if idx is None:
                rest.append(e)
            else:
                slots[idx] = e
        for i in range(len(slots)):
            if slots[i] is None and rest:
                slots[i] = rest.pop(0)
        out = []
        for role, e in zip(roles, slots):
            if e is None:
                e = {"hypothesis": "(no plan for this slot: the planner's reply was unusable or short)",
                     "change": "Improve the base program in the way you judge most promising.", "prediction": "",
                     "builds_on": [], "fallback": True}
            e["role"] = role
            base = str(e.get("base", "")).strip()
            p = self.archive.programs.get(base)
            ok = p is not None and p.valid
            if role == "deepen":
                if not (ok and base in line):
                    e["base_requested"], base = base, best.id
                e["fresh"] = False
            elif role == "branch":
                if not (ok and base != best.id and base not in line[-2:]):
                    alt = cands[0] if cands else (line[-3] if len(line) >= 3 else best.id)
                    e["base_requested"], base = base, alt
                e["fresh"] = False
            elif role == "explore":
                if not ok:
                    base = best.id
                e["fresh"] = True
            else:                                   # challenge: any base, as designed
                if not ok:
                    e["base_requested"], base = base, best.id
                e["fresh"] = bool(e.get("fresh"))
            e["base"] = base
            if not isinstance(e.get("builds_on"), list):
                e["builds_on"] = [str(e["builds_on"])] if e.get("builds_on") else []
            out.append(e)
        return out

    def program_block(self, p, title):
        fb = "\n".join(f"  {l}" for l in p.feedback)
        return f"## {title}: {p.line()}\nIts result:\n{fb}\n```python\n{P.clip(p.code, 12000)}```"

    def write_code(self, role, system, user, gen):
        text = self.call(role, system, user, temperature=0.5 if role == "coder" else 0.8, max_tokens=9000, effort="none", gen=gen)
        code = P.extract_code(text)
        if code is None:
            text = self.call(role, system, user + "\n\n(Your previous reply had no complete ```python block defining "
                             "construct. Reply with the full program.)", temperature=0.4, max_tokens=9000, effort="none", gen=gen)
            code = P.extract_code(text)
        return code, P.extract_summary(text)

    def child(self, gen, role, parent, code, intent, plan, summary, fresh=False):
        p = Program(id="", gen=gen, role=role, parent=parent.id, intent=intent, code=code or "", plan=plan or {},
                    summary=summary)
        if code is None:
            p.error = "no program in the model's reply"
            return self.add(p)
        dup = self.archive.duplicate(code, parent.id)
        if dup and not fresh:
            p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
            return self.add(p)
        p.diff = make_diff(parent.code, code)
        start = None if fresh else self.archive.construction(parent.id)
        res = evaluate(self.problem, code, start, self.cfg.budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        if fresh and p.valid:
            p.feedback = [f"(fresh start: no start construction; its base {parent.id} scored {parent.score:.6f})"] + p.feedback
        return self.add(p, res["construction"])

    def deep_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            fresh = bool(exp.get("fresh"))
            start_note = P.FRESH_NOTE if fresh else "`start` will be the base's construction."
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Prediction: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. budget_seconds will be "
                    f"{self.cfg.budget:.0f}; {start_note}\n\n{P.CODE_FORMAT}")
            code, summary = self.write_code("coder", P.CODER_SYSTEM, user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp,
                              summary, fresh=fresh)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}"))

    def wide_child(self, gen, parent, inspiration):
        try:
            user = f"{self.problem.DESCRIPTION}\n\n{self.program_block(parent, 'The program to improve')}\n\n"
            if inspiration is not None:
                user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                         f"{P.clip(inspiration.code, 5000)}```\n\n")
            user += (f"Write an improved version of the program to improve. budget_seconds will be {self.cfg.budget:.0f}; "
                     f"`start` will be its construction.\n\n{P.CODE_FORMAT}")
            code, summary = self.write_code("mutator", P.MUTATOR_SYSTEM, user, gen)
            return self.child(gen, "wide", parent, code, summary or "(no summary)", {}, summary)
        except Exception as exc:                                     # noqa: BLE001
            self.log(f"[{self.name}] gen {gen}: wide child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="wide", parent=parent.id, intent="(crashed)", code="",
                                    error=f"internal error: {exc}"))

    # ---------------------------------------------------------------- the loop
    def seed(self):
        p = Program(id="", gen=0, role="seed", parent=None, intent="Code Zero: the trivial starting program",
                    code=self.problem.CODE_ZERO)
        res = evaluate(self.problem, p.code, None, self.cfg.budget, self.cfg.mem_mb)
        if not res["valid"]:
            raise RuntimeError(f"Code Zero failed: {res['error']}")
        p.valid, p.score, p.feedback, p.cpu, p.n = True, res["score"], res["feedback"], res["cpu"], res["n"]
        self.add(p, res["construction"])
        self.checkpoint(0)
        self._append("history.jsonl", {"gen": 0, "best": p.score, "best_id": p.id, "seconds": 0})
        self.log(f"[{self.name}] gen 0: Code Zero scores {p.score:.6f}")

    def checkpoint(self, gen):
        self.gen_done = gen
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"gen_done": gen, "config": asdict(self.cfg), "t": time.time()}, indent=1))
        os.replace(tmp, self.state_path)

    def mark_shared(self, children):
        """Children of one base that gained and landed on the same score made different changes but got the same
        result, so the gain came from code they share (in v4's atlas-s1, generation 12, three different experiments
        all scored 0.928987, and each was counted as support for its own idea). Each gets a feedback line and
        plan["shared_gain_with"]; memories don't count such a gain as evidence for the change. Returns how many."""
        groups = {}
        for c in children:
            if c.valid and c.parent and c.delta is not None and c.delta >= GAIN_EPS:
                groups.setdefault(c.parent, []).append(c)
        n = 0
        for base, cs in groups.items():
            for c in cs:
                same = [d.id for d in cs if d is not c and abs(d.score - c.score) <= 1e-9 * max(1.0, abs(c.score))]
                if same:
                    c.plan = {**(c.plan or {}), "shared_gain_with": same}
                    c.feedback = list(c.feedback) + [
                        f"the same score as {', '.join(same)} (also built on {base} this generation, with a different "
                        f"change): the gain most likely came from code they share, not from this change"]
                    n += 1
        if n:
            with self.lock:
                tmp = self.archive.path.with_suffix(".tmp")
                tmp.write_text("".join(json.dumps(asdict(p)) + "\n" for p in self.archive.programs.values()))
                os.replace(tmp, self.archive.path)
        return n

    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        rng = random.Random(self.cfg.seed * 7919 + gen)
        pool = [p for p in self.archive.valid() if p.gen < gen]
        record_before = max(p.score for p in pool)
        parents = [self.archive.sample_parent(rng, pool) for _ in range(self.cfg.wide)]
        top = sorted(pool, key=lambda p: -p.score)[:5]
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide) as ex:
            wide = []
            for par in parents:
                others = [q for q in top if q.id != par.id]
                wide.append(ex.submit(self.wide_child, gen, par, rng.choice(others) if others else None))
            plan, info = self.memory.plan(gen)
            exps = self.experiments(plan, gen)
            for i, e in enumerate(exps):
                e["eid"] = f"g{gen}x{i}"           # links each experiment to the program it becomes
            self.memory.scheduled(gen, plan, exps)
            deep = [ex.submit(self.deep_child, gen, e) for e in exps]
            children = [f.result() for f in deep + wide]
        shared = self.mark_shared(children)
        t_mem = time.time()
        mem_info = self.memory.update(gen, plan, children) or {}
        best = self.archive.best()
        dc = [c for c in children if c.role == "deep"]
        wc = [c for c in children if c.role == "wide"]

        def best_of(cs):
            ok = [c.score for c in cs if c.valid]
            return max(ok) if ok else None

        def gains(cs, eps=GAIN_EPS):
            return sum(1 for c in cs if c.valid and c.delta is not None and c.delta >= eps)

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role,
               "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": gains(dc), "wide_gains": gains(wc), "deep_big_gains": gains(dc, 1e-3),
               "wide_big_gains": gains(wc, 1e-3),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in children if c.duplicate_of), "shared_gains": shared,
               "new_best": best.score > record_before + 1e-12, "record_rise": best.score - record_before,
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "fresh": sum(1 for e in exps if e.get("fresh")), "roles": [e.get("role") for e in exps],
               "role_gains": {r: sum(1 for c in dc if (c.plan or {}).get("role") == r and c.valid and c.delta is not None
                                     and c.delta >= GAIN_EPS) for r in ROLES},
               "role_best": {r: max([c.score for c in dc if (c.plan or {}).get("role") == r and c.valid] or [0]) for r in ROLES},
               "lines": len(self.lines()), "best_line_root": self.root_of(best),
               "stall": self.stall(gen), "bases": [e["base"] for e in exps],
               "distinct_bases": len({("fresh" if e.get("fresh") else e["base"]) for e in exps}),
               "builds_on_refs": len(refs), "researcher_prompt_chars": info.get("prompt_chars"),
               "researcher_seconds": info.get("seconds"), "memory_seconds": round(time.time() - t_mem, 1),
               "calls": self.llm.calls - calls0, "seconds": round(time.time() - t0, 1), **self.memory.stats()}
        self._append("plans.jsonl", {"gen": gen, "plan": plan, "experiments": exps, "info": info, "memory": mem_info})
        self._append("history.jsonl", row)
        self.checkpoint(gen)
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}); deep "
                 f"{row['deep_best'] or 0:.6f} ({row['deep_gains']}/{len(dc)} gained), wide {row['wide_best'] or 0:.6f} "
                 f"({row['wide_gains']}/{len(wc)} gained); {row['seconds']:.0f} s")
        return row

    def go(self):
        t0 = time.time()
        if self.gen_done < 0:
            self.seed()
        deadline = float(os.environ.get("HELIX5_DEADLINE", os.environ.get("HELIX4_DEADLINE", "0")) or 0)
        stopped = False
        for gen in range(self.gen_done + 1, self.cfg.gens + 1):
            if deadline and time.time() > deadline:
                self.log(f"[{self.name}] the job's deadline has passed: stopping after generation {self.gen_done}")
                stopped = True
                break
            self.generation(gen)
        return self.finish(time.time() - t0, stopped_at=self.gen_done if stopped else None)

    def finish(self, seconds=None, stopped_at=None):
        best = self.archive.best()
        hist = self.history()
        progs = list(self.archive.programs.values())
        summary = {"run": self.name, "condition": self.cfg.condition, "seed": self.cfg.seed, "gens": self.cfg.gens,
                   "problem": self.cfg.problem, "budget": self.cfg.budget, "best": best.score, "best_id": best.id,
                   "best_n": best.n, "best_lineage": self.archive.lineage_line(best.id, depth=40),
                   "best_by_gen": [h["best"] for h in hist], "programs": len(progs),
                   "valid": sum(p.valid for p in progs), "calls": self.llm.calls,
                   "tokens_in": getattr(self.llm, "tokens_in", 0), "tokens_out": getattr(self.llm, "tokens_out", 0),
                   "memory": self.memory.stats(), "config": asdict(self.cfg), "seconds_this_session": seconds,
                   "gens_done": self.gen_done, "stopped_by_deadline_at": stopped_at}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1))
        (self.dir / "best.py").write_text(best.code)
        c = self.archive.construction(best.id)
        if c is not None:
            np.save(self.dir / "best.npy", c)
        self.log(f"done: {self.name} ({self.cfg.condition}, seed {self.cfg.seed}): best {best.score:.6f} ({best.id}) "
                 f"after {self.gen_done} generations, {len(progs)} programs, {self.llm.calls} model calls")
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
    print("fake search reached", round(best, 6))
    return h
'''


def fake_answer(role, system, user):
    ids = re.findall(r"\bp\d{4}\b", user)
    tag = random.randint(1, 10 ** 9)
    base = ids[0] if ids else "p0001"

    roles = re.findall(r"with roles ([a-z, ]+) in that order", user)
    roles = [r.strip() for r in roles[-1].split(",")] if roles else ["deepen", "branch", "explore"]

    def exps(item=None):
        return [{"role": roles[i % len(roles)], "base": base if i else (ids[-1] if ids else base), "fresh": False,
                 "hypothesis": f"fake hypothesis {i}", "change": f"perturb heights, variant {i}",
                 "prediction": "a small gain", "if_gain": "push further", "if_not": "try another family",
                 "builds_on": ids[:1], **({"item": item} if item else {})} for i in range(3)]
    if role == "researcher" and "Your decision for this round" in user:
        items = re.findall(r"\bA\d+\b", user)
        bel = re.findall(r"\bB\d+\b", user)
        steps = re.findall(r"\bS\d+\b", user)
        agenda = [{"op": "add", "ref": "n1", "question": "fake question", "plan": "if A then B", "stop": "3 tries", "why": "fake"}]
        if items:
            agenda.append({"op": "revise", "id": items[0], "plan": "revised plan", "why": "fake evidence"})
        beliefs = [{"op": "add", "kind": "works", "statement": "fake belief", "confidence": "low", "evidence": ids[:1], "why": "x"},
                   {"op": "add", "kind": "mechanism", "statement": "fake mechanism", "refuted_if": "a fake result", "why": "z"}]
        if bel:
            beliefs.append({"op": "revise", "id": bel[0], "confidence": "medium", "add_evidence": ids[1:2],
                            "challenge_outcome": "held", "why": "y"})
        return "```json\n" + json.dumps({"thinking": "fake thinking", "gist": f"fake step about {base}",
                                         "follows": steps[:1], "beliefs": beliefs, "agenda": agenda,
                                         "experiments": exps(items[0] if items else "n1")}) + "\n```"
    if role == "researcher":
        return "```json\n" + json.dumps({"analysis": "fake analysis", "experiments": exps()}) + "\n```"
    if role == "lookup":
        found = re.findall(r"\b[SAB]\d+\b", user)
        return json.dumps({"lookups": found[:2] + ids[:1] + ["search: fake"], "why": "fake"})
    if role == "review":
        items = re.findall(r"\bA\d+\b", user)
        return json.dumps({"thinking": "fake review", "gist": "fake review gist", "beliefs": [],
                           "agenda": ([{"op": "park", "id": items[-1], "why": "stale"}] if items else []),
                           "summary": "fake theory summary"})
    if role == "navigator":
        fs = re.findall(r"\bF\d+\b", user)
        return json.dumps({"open": (ids[:2] + fs[:2]), "why": "fake"})
    if role in ("coder", "mutator"):
        return "```python\n" + FAKE_CODE.replace("{tag}", str(tag)) + "```\nSUMMARY: fake random local search"
    if role == "distiller":
        gen_part = user.split("every program and its result")[-1]
        pids = re.findall(r"\bp\d{4}\b", gen_part)
        fs = re.findall(r"\bF\d+\b", user.split("## Findings so far")[-1].split("##")[0])
        new = [{"kind": "works", "claim": f"fake finding about {pids[0] if pids else '?'}", "evidence": pids[:2],
                "links": [{"to": fs[0], "type": "refines"}] if fs else []}]
        return json.dumps({"new": new, "evidence": [{"finding": fs[0], "programs": pids[2:3]}] if fs else []})
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--condition", choices=["v45", "v5"], default="v5")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--deep", type=int, default=3)
    ap.add_argument("--wide", type=int, default=3)
    ap.add_argument("--effort", default="low", help="the planner's thinking effort")
    ap.add_argument("--label", default="")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model writes random-search programs)")
    a = ap.parse_args(argv)
    cfg = Config(condition=a.condition, seed=a.seed, gens=a.gens or 20, budget=a.budget, deep=a.deep, wide=a.wide,
                 researcher_effort=a.effort, label=a.label)
    llm = FakeLLM(fake_answer) if a.fake else None
    run = Run(a.out, cfg, llm=llm, gens=a.gens, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()


if __name__ == "__main__":
    sys.exit(main())
