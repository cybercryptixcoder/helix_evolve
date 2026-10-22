"""One Helix v4.6 or v6 run (docs/V6_DESIGN.md).

    python -m helix6.run --condition v46 --seed 1 --gens 30 --out runs/v6/v46-s1
    python -m helix6.run --condition v6  --seed 1 --gens 30 --out runs/v6/v6-s1
    python -m helix6.run --out runs/v6/v6-s1                 # resumes (state.json is there)
    python -m helix6.run --condition v46 --gens 2 --fake --out /tmp/x     # no model calls

The engine both versions share, built on v4.5's (helix5/run.py), with the structural fixes from the trace study
(docs/TRACE_STUDY.md):

METHOD x STATE. Every program has a method (the code it runs, changed from its base program, which is its parent in
the tree) and a state (the construction it starts from). In v4 the two always travelled together: a child started
from its parent's construction. Now any method can run on any state. A program's state is kept in meta.jsonl.

THE HALO. The wide loop's parents come from the frontier (programs within FRONTIER_EPS of the record, and the deep
loop's latest children), so the two loops feed each other. A third wide slot takes a method from an older program and
transplants it onto the record's construction. v4's rule (weight 1/(1+rank)/sqrt(1+children) over every program)
penalised the record line and had a heavy tail: in generations 1-20 of atlas-s1, 25 of 60 wide parents were more
than 0.01 below the record, and their children could not reach it.

COMPUTE ALLOCATION. The planner (v4.6) or agent (v6) splits the deep loop's CPU (3 x 30 s) as it chooses, so an
expensive idea gets a fair test. The total per generation is unchanged.

PLATEAUS BY RATE OF RETURN. A polishing tail (the record rose by less than TAIL_EPS over the last TAIL_GENS
generations) triggers the elimination list. v4.5's rule ("no rise of 1e-4") was reset by micro-gains.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
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

from helix4.archive import Archive, Program, make_diff, short
from helix4.llm import FakeLLM
from helix5.llm import LLM
from helix5.run import Run as Run5
from helix6 import prompts as P
from helix6.evaluate import GAIN_EPS, evaluate, gain_label

FRONTIER_EPS = 0.002        # a program this close to the record is on the frontier
TRANSPLANT_EPS = 0.001      # a wide parent further below the record runs on the record's construction
TAIL_GENS = 3
TAIL_EPS = 3e-4             # the record rose by less than this over TAIL_GENS generations: a polishing tail


@dataclass
class Config:
    condition: str = "v46"
    seed: int = 1
    gens: int = 30
    deep: int = 3
    wide: int = 3
    budget: float = 30.0            # the default per-program budget (and the wide loop's)
    deep_seconds: float = 90.0      # the deep loop's CPU per generation, split by the planner
    min_seconds: float = 15.0
    max_seconds: float = 90.0
    units: int = 6                  # v6: evaluation units per round (each `budget` s)
    researcher_effort: str = "low"
    open_k: int = 6
    lookup_k: int = 5
    review_every: int = 5
    mem_mb: int = 1500
    problem: str = "ac2"
    label: str = ""


def modes():
    from helix6.atlas import AtlasIdeas
    from helix6.agent import Agent
    return {"v46": AtlasIdeas, "v6": Agent}


class Run(Run5):
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
        self.meta_path = self.dir / "meta.jsonl"
        self.meta = {}
        if self.meta_path.exists():
            for l in self.meta_path.read_text().splitlines():
                if l.strip():
                    r = json.loads(l)
                    self.meta.setdefault(r["id"], {}).update(r)
        self.memory = modes()[cfg.condition](self)
        if state:
            dropped = self.archive.truncate(self.gen_done)
            self.memory.truncate(self.gen_done)
            for f in ("plans.jsonl", "history.jsonl", "meta.jsonl"):
                self._truncate_jsonl(self.dir / f)
            self.meta = {k: v for k, v in self.meta.items() if v.get("gen", 0) <= self.gen_done}
            self.log(f"[{self.name}] resuming after generation {self.gen_done} (dropped {dropped} programs of the unfinished one)")

    # ---------------------------------------------------------------- per-program meta (state, seconds, kind, ...)
    def set_meta(self, p, **kv):
        row = {"id": p.id, "gen": p.gen, **kv}
        with self.lock:
            self.meta.setdefault(p.id, {}).update(row)
            with self.meta_path.open("a") as f:
                f.write(json.dumps(row, default=float) + "\n")

    def state_note(self, p):
        m = self.meta.get(p.id, {})
        if m.get("fresh"):
            return " [from scratch]"
        st = m.get("state")
        if st and st != p.parent:
            sp = self.archive.programs.get(st)
            return f" [ran on {st}'s construction{f', {sp.score:.6f}' if sp and sp.valid else ''}]"
        return ""

    # ---------------------------------------------------------------- children
    def child6(self, gen, role, base, code, intent, plan, summary, state=None, seconds=None, fresh=False, meta=None,
               allow_same=False):
        """A program with method `base` (its parent: the code it was changed from), run on `state`'s construction
        (default: its parent's), or from scratch, with `seconds` of CPU."""
        seconds = float(seconds or self.cfg.budget)
        state = None if fresh else (state or base)
        p = Program(id="", gen=gen, role=role, parent=base.id, intent=intent, code=code or "", plan=plan or {},
                    summary=summary)
        m = {"state": state.id if state else None, "seconds": seconds, "fresh": bool(fresh), **(meta or {})}
        if code is None:
            p.error = "no program in the model's reply"
            self.add(p)
            self.set_meta(p, **m)
            return p
        if state is base and not fresh and not allow_same:
            dup = self.archive.duplicate(code, base.id)
            if dup:
                p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
                self.add(p)
                self.set_meta(p, **m)
                return p
        p.diff = make_diff(base.code, code)
        start = None if state is None else self.archive.construction(state.id)
        res = evaluate(self.problem, code, start, seconds, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        if p.valid and fresh:
            p.feedback = [f"(fresh start: no start construction; its method comes from {base.id})"] + p.feedback
        elif p.valid and state is not base:
            p.feedback = [f"(ran on {state.id}'s construction, {state.score:.6f}, not its base's)"] + p.feedback
        m["inconclusive"] = bool(res.get("inconclusive"))
        self.add(p, res["construction"])
        self.set_meta(p, **m)
        return p

    def write_code6(self, role, system, user, gen):
        text = self.call(role, system, user, temperature=0.5 if role == "coder" else 0.8, max_tokens=9000, effort="none", gen=gen)
        code = P.extract_code(text)
        if code is None:
            text = self.call(role, system, user + "\n\n(Your previous reply had no complete ```python block defining "
                             "construct. Reply with the full program.)", temperature=0.4, max_tokens=9000, effort="none", gen=gen)
            code = P.extract_code(text)
        return code, P.extract_summary(text)

    def state_line(self, state):
        if state is None:
            return "`start` will be None: build the construction from scratch (you may reuse the program's methods)."
        return (f"`start` will be the construction of {state.id} (score {state.score:.6f}, N = {state.n} steps)"
                + ("." if state is None else ""))

    def deep_child6(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            state = None if exp.get("fresh") else self.archive.programs[exp["state"]]
            seconds = float(exp.get("seconds") or self.cfg.budget)
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Prediction: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. budget_seconds will be "
                    f"{seconds:.0f}; {self.state_line(state)}\n\n{P.CODE_FORMAT}")
            code, summary = self.write_code6("coder", P.CODER_SYSTEM, user, gen)
            return self.child6(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp,
                               summary, state=state, seconds=seconds, fresh=bool(exp.get("fresh")),
                               meta={"kind": exp.get("kind") or "", "eid": exp.get("eid")})
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            p = self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                 plan=exp, error=f"internal error: {exc}"))
            self.set_meta(p, kind=exp.get("kind") or "")
            return p

    def wide_child6(self, gen, parent, state, inspiration, transplant, seconds=None, role="wide"):
        try:
            user = f"{self.problem.DESCRIPTION}\n\n{self.program_block(parent, 'The program to improve')}\n\n"
            if inspiration is not None:
                user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                         f"{P.clip(inspiration.code, 5000)}```\n\n")
            where = (f"Your program will run on a different construction than its own: {self.state_line(state)} "
                     f"Make its method work well from there.") if transplant else self.state_line(state)
            seconds = float(seconds or self.cfg.budget)
            user += (f"Write an improved version of the program to improve. budget_seconds will be {seconds:.0f}. "
                     f"{where}\n\n{P.CODE_FORMAT}")
            code, summary = self.write_code6("mutator", P.MUTATOR_SYSTEM, user, gen)
            return self.child6(gen, role, parent, code, summary or "(no summary)", {}, summary, state=state,
                               seconds=seconds, meta={"transplant": bool(transplant)})
        except Exception as exc:                                     # noqa: BLE001
            self.log(f"[{self.name}] gen {gen}: wide child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role=role, parent=parent.id, intent="(crashed)", code="",
                                    error=f"internal error: {exc}"))

    # ---------------------------------------------------------------- the halo: the wide loop on the frontier
    def frontier(self, gen):
        pool = [p for p in self.archive.valid() if p.gen < gen]
        if not pool:
            return [], None
        rec = max(pool, key=lambda p: (p.score, -p.gen))
        front = [p for p in pool if p.score >= rec.score - FRONTIER_EPS]
        latest = sorted([p for p in pool if p.gen == gen - 1 and p.role == "deep"], key=lambda p: -p.score)[:3]
        out = []
        for p in sorted(front, key=lambda q: (-q.score, -q.gen)) + latest:
            if p not in out:
                out.append(p)
        return out, rec

    def wide_plan(self, gen, rng, k=None):
        """[(parent, state, transplant, inspiration)] for the wide loop: k-1 parents from the frontier (weighted to
        the strongest and newest; the deep loop's latest children are always candidates), each running on its own
        construction if it is within TRANSPLANT_EPS of the record, else on the record's; and one method donor from
        off the frontier, run on the record's construction."""
        k = k or self.cfg.wide
        front, rec = self.frontier(gen)
        if rec is None:
            return []
        pool = [p for p in self.archive.valid() if p.gen < gen]
        off = [p for p in pool if p not in front and p.code.strip()]
        out = []
        n_front = k - 1 if off and k > 1 else k
        weights = [1.0 / math.sqrt(1 + i) * (2.0 if p.gen == gen - 1 else 1.0)
                   / math.sqrt(1 + self.archive.children.get(p.id, 0)) for i, p in enumerate(front)]
        chosen = []
        for _ in range(n_front):
            cand = [(p, w) for p, w in zip(front, weights) if p not in chosen] or list(zip(front, weights))
            p = rng.choices([c[0] for c in cand], weights=[c[1] for c in cand], k=1)[0]
            chosen.append(p)
        for p in chosen:
            far = p.score < rec.score - TRANSPLANT_EPS
            out.append((p, rec if far else p, far))
        if n_front < k:
            donor = self.archive.sample_parent(rng, off)
            out.append((donor, rec, True))
        res = []
        for parent, state, tr in out:
            others = [q for q in front if q.id != parent.id]
            insp = rec if parent.id != rec.id else (others[0] if others else None)
            res.append((parent, state, tr, insp))
        return res

    # ---------------------------------------------------------------- plateaus, by rate of return
    def tail_status(self, gen):
        hist = [h for h in self.history() if h["gen"] < gen]
        best = [h["best"] for h in hist]
        rises = [b - a for a, b in zip(best, best[1:])]
        recent = rises[-TAIL_GENS:]
        in_tail = len(rises) >= TAIL_GENS + 1 and sum(recent) < TAIL_EPS
        n = 0
        while in_tail and len(rises) - n >= TAIL_GENS and sum(rises[len(rises) - n - TAIL_GENS:len(rises) - n]) < TAIL_EPS:
            n += 1
        return {"in_tail": in_tail, "tail_gens": n + TAIL_GENS - 1 if in_tail else 0, "recent_rises": [round(r, 7) for r in rises[-5:]]}

    def progress_block(self, gen):
        hist = [h for h in self.history() if h["gen"] < gen]
        if len(hist) < 2:
            return "## Progress check (computed)\nThis is the first generation."
        best = self.archive.best()
        t = self.tail_status(gen)
        lines = ["## Progress check (computed)",
                 f"Best score {best.score:.6f} ({best.id}). How the record rose in the last generations (oldest first): "
                 + ", ".join(f"{r:+.6f}" for r in t["recent_rises"]) + "."]
        if t["in_tail"]:
            start = gen - t["tail_gens"]
            tried = {}
            for p in self.archive.programs.values():
                if p.role == "deep" and start <= p.gen < gen:
                    k = " ".join(str(self.meta.get(p.id, {}).get("kind") or "?").lower().split())
                    tried.setdefault(k, []).append(p)
            lines.append(f"This is a polishing tail: the record rose by less than {TAIL_EPS} over the last {TAIL_GENS} "
                         f"generations (for about {t['tail_gens']} generations now). Kinds of change planned since "
                         f"generation {start}:")
            for k, ps in sorted(tried.items(), key=lambda kv: -len(kv[1])):
                res = ", ".join(f"{p.id} {self.memory_result(p)}" for p in ps[:4])
                lines.append(f"- {k} ({len(ps)}): {res}")
            lines.append("Tuning these further will most likely creep. At least one experiment this generation must be a "
                         "kind of change that is not on this list, for example: a different method on the best "
                         "construction, the best method on a different construction (another program's, or from "
                         "scratch), or giving an inconclusive idea the time it needs. Say which kind in its \"kind\".")
        return "\n".join(lines)

    def memory_result(self, p):
        if not p.valid:
            return "failed"
        if p.delta is None:
            return f"{p.score:.6f} (fresh)"
        if self.meta.get(p.id, {}).get("inconclusive"):
            return "inconclusive"
        return f"{p.delta:+.6f}"

    # ---------------------------------------------------------------- the planner's experiments
    def experiments6(self, plan, gen):
        """Validated experiments: method (base), state, seconds (split of deep_seconds), kind."""
        best = self.archive.best()
        keep = ("base", "state", "seconds", "kind", "hypothesis", "change", "prediction", "if_gain", "if_not",
                "builds_on", "item", "step", "thread")
        given = []
        for e in (plan or {}).get("experiments", []):
            if isinstance(e, dict) and (e.get("change") or e.get("hypothesis")):
                given.append({k: e.get(k) for k in keep if k in e})
        given = given[: self.cfg.deep]
        if not given:
            given = [{"hypothesis": "(no plan: the planner's reply was unusable)", "kind": "fallback",
                      "change": "Improve the base program in the way you judge most promising.", "prediction": "",
                      "builds_on": [], "fallback": True} for _ in range(self.cfg.deep)]
        out = []
        for e in given:
            base = str(e.get("base", "")).strip()
            p = self.archive.programs.get(base)
            if not (p is not None and p.valid and p.code.strip()):
                e["base_requested"], base = base, best.id
            e["base"] = base
            st = str(e.get("state", "best")).strip().lower()
            if st in ("none", "scratch", "fresh", "null"):
                e["fresh"], e["state"] = True, None
            else:
                q = self.archive.programs.get(str(e.get("state", "")).strip())
                if q is not None and q.valid and self.archive.construction(q.id) is not None:
                    e["state"] = q.id
                else:
                    e["state"] = best.id
                e["fresh"] = False
            e["kind"] = " ".join(str(e.get("kind") or "").split())[:60]
            if not isinstance(e.get("builds_on"), list):
                e["builds_on"] = [str(e["builds_on"])] if e.get("builds_on") else []
            out.append(e)
        secs = []
        for e in out:
            try:
                s = float(e.get("seconds") or 0)
            except (TypeError, ValueError):
                s = 0.0
            secs.append(s if s > 0 else self.cfg.deep_seconds / len(out))
        secs = split_seconds(secs, self.cfg.deep_seconds, self.cfg.min_seconds, self.cfg.max_seconds)
        for e, s in zip(out, secs):
            if "seconds" in e and abs(float(e["seconds"] or 0) - s) > 0.5:
                e["seconds_requested"] = e["seconds"]
            e["seconds"] = s
        return out

    # ---------------------------------------------------------------- one generation
    def generation(self, gen):
        if self.cfg.condition == "v6":
            return self.memory.round(gen)
        return self.generation46(gen)

    def generation46(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        rng = random.Random(self.cfg.seed * 7919 + gen)
        pool = [p for p in self.archive.valid() if p.gen < gen]
        record_before = max(p.score for p in pool)
        wide_plan = self.wide_plan(gen, rng)
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide) as ex:
            wide = [ex.submit(self.wide_child6, gen, par, st, insp, tr) for par, st, tr, insp in wide_plan]
            plan, info = self.memory.plan(gen)
            exps = self.experiments6(plan, gen)
            for i, e in enumerate(exps):
                e["eid"] = f"g{gen}x{i}"
            self.memory.scheduled(gen, plan, exps)
            deep = [ex.submit(self.deep_child6, gen, e) for e in exps]
            children = [f.result() for f in deep + wide]
        row = self.finish_generation(gen, t0, calls0, record_before, plan, info, exps, children,
                                     wide_plan=[(a.id, b.id, c) for a, b, c, _ in wide_plan])
        return row

    def finish_generation(self, gen, t0, calls0, record_before, plan, info, exps, children, wide_plan=None, extra=None):
        shared = self.mark_shared(children)
        t_mem = time.time()
        mem_info = self.memory.update(gen, plan, children) or {}
        best = self.archive.best()
        dc = [c for c in children if c.role == "deep"]
        wc = [c for c in children if c.role == "wide"]
        cc = [c for c in children if c.role == "continue"]
        rec = record_before

        def best_of(cs):
            ok = [c.score for c in cs if c.valid]
            return max(ok) if ok else None

        def gains(cs, eps=GAIN_EPS):    # beat its start; a fresh start (no start) counts if it beat the record
            return sum(1 for c in cs if c.valid and ((c.delta if c.delta is not None else c.score - rec) >= eps))

        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role,
               "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": gains(dc), "wide_gains": gains(wc), "deep_big_gains": gains(dc, 1e-3),
               "wide_big_gains": gains(wc, 1e-3), "continue_best": best_of(cc), "continue_gains": gains(cc),
               "continues": len(cc),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in children if c.duplicate_of), "shared_gains": shared,
               "new_best": best.score > record_before + 1e-12, "record_rise": best.score - record_before,
               "inconclusive": sum(1 for c in children if self.meta.get(c.id, {}).get("inconclusive")),
               "transplants": sum(1 for c in wc if self.meta.get(c.id, {}).get("transplant")),
               "wide_parent_gaps": [round(rec - self.archive.programs[c.parent].score, 6) for c in wc
                                    if c.parent in self.archive.programs and self.archive.programs[c.parent].valid],
               "wide_near_record": sum(1 for c in wc if c.valid and c.score >= rec - 1e-3),
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "fresh": sum(1 for e in exps if e.get("fresh")), "seconds": [e.get("seconds") for e in exps],
               "kinds": [e.get("kind") for e in exps], "states": [e.get("state") for e in exps],
               "bases": [e.get("base") for e in exps], "tail": self.tail_status(gen + 1)["in_tail"],
               "researcher_prompt_chars": info.get("prompt_chars"), "researcher_seconds": info.get("seconds"),
               "memory_seconds": round(time.time() - t_mem, 1), "calls": self.llm.calls - calls0,
               "wall_seconds": round(time.time() - t0, 1), **(extra or {}), **self.memory.stats()}
        row["seconds_total"] = row.pop("wall_seconds")
        self._append("plans.jsonl", {"gen": gen, "plan": plan, "experiments": exps, "info": info, "memory": mem_info,
                                     "wide_plan": wide_plan})
        self._append("history.jsonl", {**row, "seconds": row["seconds_total"], "exp_seconds": row.pop("seconds")})
        self.checkpoint(gen)
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}); deep "
                 f"{row['deep_best'] or 0:.6f} ({row['deep_gains']}/{len(dc)} gained), wide {row['wide_best'] or 0:.6f} "
                 f"({row['wide_gains']}/{len(wc)} gained, {row['wide_near_record']} near the record)"
                 + (f", continue {row['continue_best'] or 0:.6f} ({row['continue_gains']}/{len(cc)} gained)" if cc else "")
                 + f"; {row['seconds_total']:.0f} s")
        return row


def split_seconds(req, total, lo, hi):
    """Scale the requested per-experiment seconds so they add up to `total`, each within [lo, hi]."""
    n = len(req)
    if n == 0:
        return []
    lo = min(lo, total / n)
    s = [max(1e-6, float(x)) for x in req]
    for _ in range(50):
        f = total / sum(s)
        s = [min(hi, max(lo, x * f)) for x in s]
        if abs(sum(s) - total) < 1e-6:
            break
    free = [i for i in range(n) if lo < s[i] < hi]
    diff = total - sum(s)
    if abs(diff) > 1e-6 and free:
        for i in free:
            s[i] += diff / len(free)
    out = [round(x, 1) for x in s]
    i = max(range(n), key=lambda j: out[j])            # rounding residue goes to the largest share
    out[i] = round(out[i] + (total - sum(out)), 1)
    return out


# ---------------------------------------------------------------------------------------------- the fake model
from helix5.run import FAKE_CODE, fake_answer as fake5       # noqa: E402


def fake_answer(role, system, user):
    ids = re.findall(r"\bp\d{4}\b", user)
    base = ids[0] if ids else "p0001"
    if role == "researcher" and "their seconds add up to" in user:
        exps = [{"base": base, "state": "best" if i else (ids[-1] if ids else "best"), "seconds": [45, 30, 15][i],
                 "kind": ["fake kind a", "fake kind b", "fake kind a"][i], "hypothesis": f"fake hypothesis {i}",
                 "change": f"perturb heights, variant {i}", "prediction": "a small gain", "if_gain": "push",
                 "if_not": "switch", "builds_on": ids[:1]} for i in range(3)]
        return "```json\n" + json.dumps({"analysis": "fake analysis", "experiments": exps}) + "\n```"
    if role == "agent":
        from helix6.agent import fake_decision
        return fake_decision(user)
    if role == "distiller":
        gen_part = user.split("every program and its result")[-1]
        pids = re.findall(r"\bp\d{4}\b", gen_part)
        fs = re.findall(r"\bF\d+\b", user.split("## Findings so far")[-1].split("##")[0])
        new = [{"kind": "works", "tag": "fake kind a", "claim": f"fake finding about {pids[0] if pids else '?'}",
                "evidence": pids[:2], "links": [{"to": fs[0], "type": "refines"}] if fs else []}]
        return json.dumps({"new": new, "evidence": [{"finding": fs[0], "programs": pids[2:3]}] if fs else []})
    return fake5(role, system, user)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--condition", choices=["v46", "v6"], default="v46")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--effort", default="low", help="the planner's thinking effort")
    ap.add_argument("--label", default="")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model writes random-search programs)")
    a = ap.parse_args(argv)
    cfg = Config(condition=a.condition, seed=a.seed, gens=a.gens or 30, budget=a.budget,
                 deep_seconds=3 * a.budget, max_seconds=3 * a.budget, min_seconds=a.budget / 2,
                 researcher_effort=a.effort, label=a.label)
    llm = FakeLLM(fake_answer) if a.fake else None
    run = Run(a.out, cfg, llm=llm, gens=a.gens, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()


if __name__ == "__main__":
    sys.exit(main())
