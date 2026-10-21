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
- stagnation is computed (generations since the best last rose by STALL_EPS) and, after `stall_gens`, at least one
  experiment must be an escape (fresh, or a base outside the best line), enforced by code;
- history counts real gains (>= 1e-5), not 1e-9 polishing, and "new_best" means the record actually rose.
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
    def stall(self, gen):
        """Generations (up to gen-1) since the best score last rose by at least STALL_EPS over the previous record."""
        hist = [h for h in self.history() if h["gen"] < gen]
        if len(hist) < 2:
            return 0
        last_rise, record = 0, hist[0]["best"]
        for h in hist[1:]:
            if h["best"] >= record + STALL_EPS:
                last_rise = h["gen"]
                record = h["best"]
        return hist[-1]["gen"] - last_rise

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
        return "\n".join(lines)

    def best_line(self):
        b = self.archive.best()
        return {p.id for p in self.archive.lineage(b.id, depth=1000)}

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
        """Validated experiments (exactly `deep`); the escape rule is applied when the best has stalled."""
        best = self.archive.best()
        out = []
        for e in (plan or {}).get("experiments", [])[: self.cfg.deep]:
            if not isinstance(e, dict) or not (e.get("change") or e.get("hypothesis")):
                continue
            base = str(e.get("base", "")).strip()
            p = self.archive.programs.get(base)
            keep = ("base", "fresh", "hypothesis", "change", "prediction", "if_gain", "if_not", "builds_on", "item", "step")
            e = {k: e.get(k) for k in keep if k in e}
            e["fresh"] = bool(e.get("fresh")) or base.lower() == "fresh"
            if p is None or not p.valid:
                if base.lower() != "fresh":
                    e["base_requested"] = base
                e["base"] = best.id
            if not isinstance(e.get("builds_on"), list):
                e["builds_on"] = [str(e["builds_on"])] if e.get("builds_on") else []
            out.append(e)
        while len(out) < self.cfg.deep:
            out.append({"base": best.id, "fresh": False, "hypothesis": "(no plan: the planner's reply was unusable)",
                        "change": "Improve the base program in the way you judge most promising.",
                        "prediction": "", "builds_on": [], "fallback": True})
        stall = self.stall(gen)
        if stall >= self.cfg.stall_gens:
            line = self.best_line()
            if not any(e["fresh"] or e["base"] not in line for e in out):
                out[-1]["fresh"] = True
                out[-1]["forced_escape"] = True
                out[-1]["change"] = (f"{out[-1].get('change')}\n(The best score has stalled for {stall} generations, "
                                     "so this experiment starts from scratch: build a genuinely different construction.)")
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
               "duplicates": sum(1 for c in children if c.duplicate_of),
               "new_best": best.score > record_before + 1e-12, "record_rise": best.score - record_before,
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "fresh": sum(1 for e in exps if e.get("fresh")), "forced_escapes": sum(1 for e in exps if e.get("forced_escape")),
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

    def exps(item=None):
        return [{"base": base if i else (ids[-1] if ids else base), "fresh": i == 2 and random.random() < 0.3,
                 "hypothesis": f"fake hypothesis {i}", "change": f"perturb heights, variant {i}",
                 "prediction": "a small gain", "if_gain": "push further", "if_not": "try another family",
                 "builds_on": ids[:1], **({"item": item} if item else {})} for i in range(3)]
    if role == "researcher" and "Your decision for this round" in user:
        items = re.findall(r"\bA\d+\b", user)
        bel = re.findall(r"\bB\d+\b", user)
        steps = re.findall(r"\bS\d+\b", user)
        agenda = [{"op": "add", "ref": "n1", "purpose": "fake purpose", "plan": "if A then B", "why": "fake"}]
        if items:
            agenda.append({"op": "revise", "id": items[0], "plan": "revised plan", "why": "fake evidence"})
        beliefs = [{"op": "add", "kind": "works", "statement": "fake belief", "confidence": "low", "evidence": ids[:1], "why": "x"}]
        if bel:
            beliefs.append({"op": "revise", "id": bel[0], "confidence": "medium", "add_evidence": ids[1:2], "why": "y"})
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
