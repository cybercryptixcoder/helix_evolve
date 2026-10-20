"""One Helix v4 run: program evolution with a population, two loops, and one of three memory conditions.

    python -m helix4.run --condition atlas --seed 1 --gens 20 --out runs/v4/atlas-s1
    python -m helix4.run --out runs/v4/atlas-s1            # resumes (state.json is there), same settings
    python -m helix4.run --condition control --gens 2 --fake --out /tmp/x   # no model calls

Each generation:
  wide loop (memoryless, identical in every condition): `wide` parents sampled from the archive (rank-based, with a
      bonus for programs with few children); the Mutator writes an improved version of each.
  deep loop: the Researcher (thinking `low`) sees the past through the condition's memory and plans `deep`
      experiments, each on a base program it chooses; a Coder implements each one.
  Every child runs from its base's construction with `budget` s of CPU, is checked, scored and described; all are
  kept. The memory is then updated (the journal is appended; the Atlas Distiller records findings).
Everything is written as it happens: programs.jsonl (the immutable log), constructions/, plans.jsonl,
history.jsonl (one line per generation), trace.jsonl (every model call), state.json (the checkpoint), and at the
end summary.json, best.py, best.npy.
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

from helix4 import prompts as P
from helix4.archive import Archive, Program, make_diff, short
from helix4.evaluate import evaluate
from helix4.llm import FakeLLM, LLM, LLMError
from helix4.memory import MODES


@dataclass
class Config:
    condition: str = "atlas"
    seed: int = 1
    gens: int = 20
    deep: int = 3
    wide: int = 3
    budget: float = 30.0
    researcher_effort: str = "low"
    journal_chars: int = 24000
    journal_keep: int = 4
    journal_summary_chars: int = 4000
    open_k: int = 6
    mem_mb: int = 1500
    problem: str = "ac2"
    label: str = ""


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
        self.memory = MODES[cfg.condition](self)
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

    def record(self, call):
        call = {"t": round(time.time(), 1), "run": self.name, **call}
        with self.trace_lock:
            self.trace.write(json.dumps(call) + "\n")
            self.trace.flush()

    def call(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", gen=None):
        try:
            return self.llm.chat(role, system, user, temperature=temperature, max_tokens=max_tokens, effort=effort,
                                 meta={"gen": gen}).text
        except LLMError as exc:
            self.log(f"[{self.name}] gen {gen}: {role} call failed: {exc}")
            return ""

    def add(self, p: Program, construction=None):
        with self.lock:
            p.id = self.archive.new_id()
            self.archive.add(p, construction)
        return p

    # ---------------------------------------------------------------- roles
    def researcher(self, user, gen, step="plan"):
        system = P.RESEARCHER_SYSTEM.format(k=self.cfg.deep, budget=self.cfg.budget)
        t0 = time.time()
        text = self.call("researcher", system, user, temperature=0.7, max_tokens=12000, effort=self.cfg.researcher_effort, gen=gen)
        plan = P.extract_json(text)
        retried = False
        if not (isinstance(plan, dict) and isinstance(plan.get("experiments"), list) and plan["experiments"]):
            retried = True
            text = self.call("researcher", system, user + "\n\n(Your previous reply could not be read. Reply with the "
                             "JSON object only.)", temperature=0.5, max_tokens=3500, effort="none", gen=gen)
            plan = P.extract_json(text)
            if not (isinstance(plan, dict) and isinstance(plan.get("experiments"), list)):
                plan = None
        return plan, {"prompt_chars": len(user), "parsed": plan is not None, "retried": retried,
                      "seconds": round(time.time() - t0, 1)}

    def experiments(self, plan):
        best = self.archive.best()
        out = []
        for e in (plan or {}).get("experiments", [])[: self.cfg.deep]:
            if not isinstance(e, dict) or not (e.get("change") or e.get("hypothesis")):
                continue
            base = str(e.get("base", "")).strip()
            p = self.archive.programs.get(base)
            e = {k: e.get(k) for k in ("base", "hypothesis", "change", "prediction", "builds_on")}
            if p is None or not p.valid:
                e["base_requested"], e["base"] = base, best.id
            if not isinstance(e.get("builds_on"), list):
                e["builds_on"] = [str(e["builds_on"])] if e.get("builds_on") else []
            out.append(e)
        while len(out) < self.cfg.deep:
            out.append({"base": best.id, "hypothesis": "(no plan: the researcher's reply was unusable)",
                        "change": "Improve the base program in the way you judge most promising.",
                        "prediction": "", "builds_on": [], "fallback": True})
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

    def child(self, gen, role, parent, code, intent, plan, summary):
        p = Program(id="", gen=gen, role=role, parent=parent.id, intent=intent, code=code or "", plan=plan or {},
                    summary=summary)
        if code is None:
            p.error = "no program in the model's reply"
            return self.add(p)
        dup = self.archive.duplicate(code, parent.id)
        if dup:
            p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
            return self.add(p)
        p.diff = make_diff(parent.code, code)
        res = evaluate(self.problem, code, self.archive.construction(parent.id), self.cfg.budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        return self.add(p, res["construction"])

    def deep_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Prediction: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. budget_seconds will be "
                    f"{self.cfg.budget:.0f}; `start` will be the base's construction.\n\n{P.CODE_FORMAT}")
            code, summary = self.write_code("coder", P.CODER_SYSTEM, user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp, summary)
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
        parents = [self.archive.sample_parent(rng, pool) for _ in range(self.cfg.wide)]
        top = sorted(pool, key=lambda p: -p.score)[:5]
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide) as ex:
            wide = []
            for par in parents:
                others = [q for q in top if q.id != par.id]
                wide.append(ex.submit(self.wide_child, gen, par, rng.choice(others) if others else None))
            plan, info = self.memory.plan(gen)
            exps = self.experiments(plan)
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

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role,
               "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": sum(1 for c in dc if c.valid and (c.delta or 0) > 1e-9),
               "wide_gains": sum(1 for c in wc if c.valid and (c.delta or 0) > 1e-9),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in children if c.duplicate_of),
               "new_best": best.gen == gen, "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "bases": [e["base"] for e in exps], "builds_on_refs": len(refs),
               "builds_on_known": sum(1 for r in refs if str(r) in self.archive.programs or str(r) in getattr(self.memory, "findings", {})),
               "researcher_prompt_chars": info.get("prompt_chars"), "researcher_seconds": info.get("seconds"),
               "memory_seconds": round(time.time() - t_mem, 1), "calls": self.llm.calls - calls0,
               "seconds": round(time.time() - t0, 1), **self.memory.stats()}
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
        deadline = float(os.environ.get("HELIX4_DEADLINE", "0") or 0)    # epoch seconds; 0 = none
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
        hist = [json.loads(l) for l in (self.dir / "history.jsonl").read_text().splitlines() if l.strip()]
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
    if role == "researcher":
        base = ids[0] if ids else "p0001"
        exps = [{"base": base if i else (ids[-1] if ids else base), "hypothesis": f"fake hypothesis {i}",
                 "change": f"perturb heights, variant {i}", "prediction": "a small gain", "builds_on": ids[:1]}
                for i in range(3)]
        return "```json\n" + json.dumps({"analysis": "fake analysis", "experiments": exps}) + "\n```"
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
        ev = [{"finding": fs[0], "programs": pids[2:3]}] if fs else []
        return json.dumps({"new": new, "evidence": ev})
    if role == "compactor":
        return "fake compacted summary of the old journal"
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--condition", choices=sorted(MODES), default="atlas")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--deep", type=int, default=3)
    ap.add_argument("--wide", type=int, default=3)
    ap.add_argument("--effort", default="low", help="the Researcher's thinking effort")
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
