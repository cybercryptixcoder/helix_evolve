"""The two-loop search. Run from the repo root:

  python -m helix.run --generations 20              the full algorithm
  python -m helix.run --fake-llm --generations 3    offline test, no keys needed
  python -m helix.run --mode wide-only              control: a conventional single-mutator search
  python -m helix.run --mode zero-shot --n 40       control: best of N plain answers, no search
  python -m helix.run --resume helix/runs/<run>     continue a stopped run

One generation (the three branches run at the same time):
  1. Rank the current pool: the best programs found so far.
  2. Deep branch: the Researcher studies the champion (knock-outs, inherited from its ancestors
     where the parts are shared) and proposes mechanism changes. The Coder writes one program per
     hypothesis, changing only that aspect. Each is scored and judged against its base.
  3. Wide branch: the Mutator sees only the top X programs' code and scores (the air gap) and
     writes variants of them, plus a fresh idea or two.
  4. Tune branch: a cheap local search tunes the numbers of the champion and of the best untuned
     newcomer, so the LLMs can spend their effort on structure.
  5. Next pool = the best K of the old pool plus everything new (at most a few siblings per parent).

Generation 0 is Code Zero plus one wide batch, because there's nothing to research yet.
"""
import argparse
import json
import os
import random
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import roles
from .llm import LLM, FakeLLM, Settings
from .mongo import Mirror
from . import tune as tuner
from .bounds import family_floor
from .population import Hypothesis, Program, Store, judge, read_records
from .sandbox import REPO_ROOT, evaluate_code, evaluate_file

RUNS_DIR = Path(__file__).resolve().parent / "runs"
# Mutator runs hot for variety; Coder runs cool so it changes only what it's told.
TEMPERATURE = {"mutator": 0.8, "researcher": 0.6, "coder": 0.3, "zeroshot": 0.8}
# Output limits per role (tokens): a reply that deliberates instead of answering fails in seconds, not a
# minute, and gets one retry asking for only the answer. Zero-shot answers keep the general limit.
MAX_TOKENS = {"mutator": 4000, "coder": 4000, "researcher": 6000}
# Characters of hidden reasoning, with no answer yet, after which a reply is abandoned and retried: with
# thinking off the model still sometimes slips into it, and then rarely answers before running out of room.
THINK_LIMIT = {"mutator": 8000, "coder": 6000, "researcher": 16000}
RESEARCHER_SHOWN = 8      # programs shown to the Researcher


class Search:
    def __init__(self, args, store, llm):
        self.a = args
        self.store = store
        self.llm = llm
        self.workers = ThreadPoolExecutor(max_workers=args.workers)
        self._status_lock = threading.Lock()
        self.phases = {}          # branch -> what it's doing right now
        self.status = {"state": "starting", "pid": os.getpid(), "mode": args.mode, "schedule": args.schedule,
                       "generation": None, "generations": args.generations, "started": time.time()}
        # What each step of the flowchart is doing in the current generation (read by the dashboard).
        self.flow, self.flow_generation = {}, None
        self._evals = {"running": 0, "done": 0}
        # Scores many variants of one program in parallel: the tune branch, and tune-then-judge in the deep branch.
        many = tuner.evaluator("train", args.eval_timeout, args.tune_workers)

        def counted(codes):
            self.count_evals(len(codes), 0)
            try:
                return many(codes)
            finally:
                self.count_evals(-len(codes), len(codes))
        self.tune_eval = counted
        self.rng = random.Random()
        # Programs whose numbers have been tuned already (restored from the log on --resume).
        self.tuned = {t for g in read_records(store.dir / "generations.jsonl")
                      for t in (g.get("tune") or {}).get("targets", [])}

    # ================================================================ live status (read by the dashboard)
    def set_status(self, **fields):
        with self._status_lock:
            self.status.update(fields)
            best = self.store.best()
            self.status.update(phase=" | ".join(f"{b}: {t}" for b, t in self.phases.items()),
                               flow=self.flow, flow_generation=self.flow_generation,
                               updated=time.time(), llm=self.llm.summary(),
                               best_id=best.id if best else None, best_score=best.score if best else None,
                               mongo=self.store.mirror.status if self.store.mirror else None)
            tmp = self.store.dir / "status.json.tmp"
            tmp.write_text(json.dumps(self.status, indent=2))
            os.replace(tmp, self.store.dir / "status.json")
            if self.store.mirror and ("state" in fields or "generation" in fields):
                self.store.mirror.put("runs", {"status": {k: v for k, v in self.status.items() if k != "mongo"}},
                                      key="run_id")

    def set_phase(self, branch, text):
        with self._status_lock:
            if text is None:
                self.phases.pop(branch, None)
            else:
                self.phases[branch] = text
        self.set_status()

    # ---------------------------------------------------------------- the flowchart's live state
    FLOW_NODES = ("pool", "researcher", "coder", "mutator", "tune", "evaluator", "merge")

    def reset_flow(self, generation, branches):
        with self._status_lock:
            self.flow_generation = generation
            self._evals = {"running": 0, "done": 0}
            uses = {"pool": True, "researcher": "deep" in branches, "coder": "deep" in branches,
                    "mutator": "wide" in branches, "tune": "tune" in branches, "evaluator": True, "merge": True}
            self.flow = {n: {"state": "waiting" if uses[n] else "off"} for n in self.FLOW_NODES}
        self.set_status()

    def set_flow(self, node, state=None, **fields):
        with self._status_lock:
            f = self.flow.setdefault(node, {"state": "waiting"})
            if state:
                f["state"] = state
            f.update(fields)
        self.set_status()

    def count_evals(self, running, done):
        with self._status_lock:
            self._evals["running"] += running
            self._evals["done"] += done
            ev = self.flow.setdefault("evaluator", {})
            ev.update(running=self._evals["running"], done=self._evals["done"],
                      state="active" if self._evals["running"] > 0 else ("done" if self._evals["done"] else "waiting"))

    def stop_requested(self):
        return (self.store.dir / "STOP").exists()

    def ensure_model_ready(self, why):
        """Wait until the model answers before spending a generation on it."""
        if self.a.fake_llm:
            return
        say(f"   checking the model is answering ({why})...")

        def waiting(error, left):
            msg = f"model not answering yet, retrying every 15s ({left / 60:.0f} min left): {error[:120]}"
            say("   " + msg)
            self.set_phase("model", msg)

        ready, error = self.llm.wait_until_ready(max_wait=self.a.wait_minutes * 60, on_wait=waiting)
        self.set_phase("model", None)
        if not ready:
            raise RuntimeError(f"the model isn't answering: {error}")
        say("   model is answering")

    # ================================================================ published trace (results/<run>/)
    def publish_trace(self, final=False):
        """Copy the run's trace into results/<run>/ (committed to the repo). Never stops the run."""
        if not self.a.publish:
            return
        try:
            from .publish import export
            if final:
                say("Publishing the final trace with the held-out check...")
            dest = export(self.store.dir, report=final and self.store.best() is not None)
            if final:
                shown = dest.relative_to(REPO_ROOT) if dest.is_relative_to(REPO_ROOT) else dest
                say(f"published to {shown}  (commit it, or use Publish on the dashboard)")
        except Exception as exc:
            say(f"   (publishing the trace failed, the run carries on: {type(exc).__name__}: {exc})")

    # ================================================================ one candidate
    def candidate(self, role, user, generation, branch, parent_id=None, hypothesis_id=None, finalize=None):
        """Ask one agent for a program, score it, repair it once if it fails. Always returns a Program.

        `finalize(prog)` runs after scoring and before the program is saved (the deep branch uses it
        to judge a test and mark knock-outs as measurements)."""
        pid = self.store.new_id("p")
        system = roles.system_prompt(role)
        prog = Program(id=pid, code="", generation=generation, branch=branch,
                       parent_id=parent_id, hypothesis_id=hypothesis_id)
        limit, think = MAX_TOKENS.get(role), THINK_LIMIT.get(role)
        tag = {"generation": generation, "branch": branch, "program": pid,
               **({"hypothesis": hypothesis_id} if hypothesis_id else {})}
        try:
            reply = self.llm.chat(role, system, user, temperature=TEMPERATURE[role], max_tokens=limit,
                                  think_limit=think, tag=tag)
        except Exception as exc:
            prog.error = f"LLM call failed: {exc}"
            if finalize:
                finalize(prog)
            self.store.add_program(prog)
            return prog
        prog.model, prog.note = reply.model, roles.extract_note(reply.text)
        code = roles.extract_code(reply.text)
        if code is None:   # cut off (or no program at all): one retry for only the code, keeping its idea
            try:
                again = self.llm.chat(f"{role}-retry", system, roles.code_only_message(user, reply.text),
                                      temperature=TEMPERATURE[role], max_tokens=limit, think_limit=think, tag=tag)
                code = roles.extract_code(again.text)
                prog.note = roles.extract_note(again.text) or prog.note
            except Exception as exc:
                prog.error = f"retry for a reply with no program failed: {exc}"

        for attempt in range(self.a.repairs + 1):
            if code is None:
                prog.error = prog.error or ("reply had no ```python block defining priority()" if attempt == 0
                                            else "the repair reply had no ```python block")
                break
            prog.code = code
            dup = self.store.duplicate_of(code)
            if dup is not None:
                prog.duplicate_of = dup.id
                prog.valid, prog.score, prog.families, prog.error = dup.valid, dup.score, dup.families, dup.error
                break
            # The tiny `quick` split first, so broken or very slow programs fail in a second.
            self.count_evals(1, 0)
            try:
                result = evaluate_code(code, self.store.candidate_path(pid), "quick", min(15.0, self.a.eval_timeout))
                if result["valid"]:
                    result = evaluate_file(self.store.candidate_path(pid), "train", self.a.eval_timeout)
            finally:
                self.count_evals(-1, 1)
            if result["valid"]:
                prog.valid, prog.score, prog.error = True, result["score"], None
                prog.families = {f: v["excess_pct"] for f, v in result["families"].items()}
                break
            prog.error = result["error"]
            if attempt == self.a.repairs:
                break
            try:   # one repair: show the agent its own error
                fix = self.llm.chat(f"{role}-repair", system, roles.repair_message(code, prog.error),
                                    temperature=TEMPERATURE[role], max_tokens=limit, think_limit=think, tag=tag)
            except Exception as exc:
                prog.error += f"\n(repair call failed: {exc})"
                break
            prog.repaired = True
            code = roles.extract_code(fix.text)
            prog.error = None if code else prog.error + "\n(the repair reply had no ```python block)"

        if finalize:
            finalize(prog)
        self.store.add_program(prog)
        return prog

    # ================================================================ the two branches
    def wide(self, pool, generation):
        """Mutator: top X programs in, variants out. Only code and score cross the air gap."""
        top = [p for p in pool if p.valid and not p.probe][: self.a.top_x]
        scored = [roles.Scored(p.code, p.score) for p in top]
        # Most requests are variants: half of them start from the best program, so a hit gets built on;
        # the rest go round the other top programs (a different one first each generation). The last
        # one or two requests ask for a fresh idea, to keep variety.
        stuck = self.stall(generation) >= self.a.stall
        fresh = min(self.a.fresh + (1 if stuck else 0), self.a.variants)   # more exploration while stuck
        n_var = self.a.variants - fresh
        half = (n_var + 1) // 2
        rest = list(range(1, len(top))) or [0]
        targets = ([(0, False)] * half + [(rest[(i + generation) % len(rest)], False) for i in range(n_var - half)]
                   + [(0, True)] * fresh)
        jobs = []
        for t, is_fresh in targets:
            msg = roles.mutator_message(scored[t], scored[:t] + scored[t + 1:], fresh=is_fresh)
            jobs.append(self.workers.submit(self.candidate, "mutator", msg, generation, "wide",
                                            None if is_fresh else top[t].id))
        self.set_phase("wide", f"Mutator writing {len(jobs)} variants")
        self.set_flow("mutator", "active", done=0, total=len(jobs), note=f"{len(jobs) - fresh} variants, {fresh} fresh ideas")
        progs = []
        for job in as_completed(jobs):
            progs.append(job.result())
            self.set_phase("wide", f"{len(progs)}/{len(jobs)} variants scored")
            self.set_flow("mutator", done=len(progs))
        self.set_phase("wide", None)
        valid = [p for p in progs if p.valid]
        self.set_flow("mutator", "done", note=f"{len(valid)}/{len(progs)} valid"
                      + (f", best {max(p.score for p in valid):.3f}" if valid else ""))
        return progs, {}

    def lineage(self, prog, depth=12):
        """The program and its ancestors, nearest first."""
        out = []
        while prog is not None and len(out) < depth and prog.id not in out:
            out.append(prog.id)
            prog = self.store.programs.get(prog.parent_id) if prog.parent_id else None
        return out

    def champion_plan(self, generation):
        """The champion (best program so far), whether it's a real jump, and how many cause/improve tests to run.

        Knock-outs are spent only where they teach something new: on a champion that jumped by at least
        epsilon, and then only on its new or changed parts (knock-outs on its ancestors are inherited).
        A small step, a tuned champion (same parts, new numbers) or a deep champion (its own test already
        measured the one part it changed) gets improve tests only."""
        champ = self.store.best()
        older = [p for p in self.store.programs.values()
                 if p.valid and not p.probe and int(p.id[1:]) < int(champ.id[1:])]
        prev_best = max((p.score for p in older), default=None)
        jump = round(champ.score - prev_best, 4) if prev_best is not None else None
        info = {"new": champ.generation >= generation - 1 and champ.branch != "seed", "jump": jump,
                "real_jump": jump is None or jump >= self.a.jump, "stall": self.stall(generation)}
        line = self.lineage(champ)
        done = [h for h in self.store.hypotheses if h.kind == "cause" and h.verdict not in ("pending", "invalid")]
        own = sum(h.base_id == champ.id for h in done)
        inherited = sum(h.base_id in line[1:] for h in done)
        n = self.a.hypotheses
        if champ.branch in ("seed", "tune", "deep") or own:
            cause = 0                      # nothing new to take apart, or already taken apart: improve it
        elif info["real_jump"]:
            cause = 1 if inherited else max(1, n // 2)   # only the new parts need measuring if the rest is known
        else:
            cause = 0 if inherited else 1                # a small step: measure once if nothing in its line ever was
        cause = min(cause, n)
        return champ, info, {"cause": cause, "improve": n - cause, "tuned": bool(self.a.tune),
                             "stuck": info["stall"] >= self.a.stall, "stall": info["stall"]}

    def stall(self, generation):
        """Generations since the last new best that changed the program's structure (from the deep or wide
        branch, or Code Zero): 0 if it came last generation. New bests from the tune branch only change
        numbers, so they don't count: the LLMs still need to find a better idea."""
        best, last = float("-inf"), 0
        for p in sorted(self.store.programs.values(), key=lambda p: int(p.id[1:])):
            if p.valid and not p.probe and p.score is not None and p.score > best:
                best = p.score
                if p.branch != "tune":
                    last = p.generation
        return max(0, generation - 1 - last)

    def deep(self, pool, generation):
        """Researcher: knock-outs to learn why the champion wins, moderate improve tests to beat it.
        Coder writes each test; knock-outs are kept as measurements, improve tests compete for the pool."""
        champ, info, plan = self.champion_plan(generation)
        candidates = [p for p in pool if p.valid and not p.probe and p.id != champ.id]
        shown = [champ] + candidates[: RESEARCHER_SHOWN - 1]
        gains = {}
        for p in shown:
            parent = self.store.programs.get(p.parent_id) if p.parent_id else None
            if parent is not None and parent.valid and parent.score is not None:
                gains[p.id] = round(p.score - parent.score, 4)
        parent = self.store.programs.get(champ.parent_id) if champ.parent_id else None
        msg = roles.researcher_message(champ, info, shown, self.store.hypotheses, plan, generation, gains,
                                       lineage=self.lineage(champ), parent=parent if parent and parent.valid else None,
                                       floor=family_floor("train"))
        jump = f", new by {info['jump']:+.3f}" if info["new"] and info["jump"] is not None else ""
        say(f"   deep: champion {champ.id} ({champ.score:.3f}{jump}); plan {plan['cause']} cause + {plan['improve']} improve")
        self.set_phase("deep", f"Researcher studying champion {champ.id}")
        self.set_flow("researcher", "active", note=f"studying {champ.id}: {plan['cause']} cause + {plan['improve']} improve")
        system = roles.system_prompt("researcher")
        proposals = []
        for attempt in range(2):     # a cut-off reply gets one retry asking for only the JSON
            try:
                text = msg if attempt == 0 else (msg + "\n\nYour previous reply ran out of room before the JSON. "
                                                 "Reply with ONLY the ```json block, no analysis, and keep each field "
                                                 "under 40 words.")
                reply = self.llm.chat("researcher" if attempt == 0 else "researcher-retry", system, text,
                                      temperature=TEMPERATURE["researcher"], max_tokens=MAX_TOKENS["researcher"],
                                      think_limit=THINK_LIMIT["researcher"],
                                      tag={"generation": generation, "branch": "deep"})
                proposals = roles.extract_hypotheses(reply.text, {p.id for p in shown}, champ.id)[: self.a.hypotheses]
            except Exception as exc:
                say(f"   deep: Researcher call failed ({str(exc)[:120]})")
            if proposals:
                break
        if not proposals:
            say("   deep: no usable hypotheses after a retry; skipping the deep branch this generation")
            self.set_phase("deep", None)
            self.set_flow("researcher", "failed", note="no usable hypotheses after a retry")
            self.set_flow("coder", "off")
            return [], {"tested": 0}
        self.set_phase("deep", f"Coder writing {len(proposals)} tests")
        self.set_flow("researcher", "done", note=f"{len(proposals)} hypotheses on {champ.id}")
        self.set_flow("coder", "active", done=0, total=len(proposals), note="writing and judging tests")

        def test(prop):
            base = self.store.programs[prop["base"]]
            h = Hypothesis(id=self.store.new_id("h"), generation=generation, base_id=base.id,
                           claim=prop["claim"], change=prop["change"], prediction=prop["prediction"],
                           kind=prop["kind"], builds_on=prop["builds_on"])
            prog = self.candidate("coder", roles.coder_message(base, h), generation, "deep", base.id, h.id,
                                  finalize=lambda p: self.judge_test(h, base, p))
            self.store.add_hypothesis(h)
            return prog, h

        jobs = [self.workers.submit(test, p) for p in proposals]
        results, verdicts = [], {}
        for job in as_completed(jobs):
            prog, h = job.result()
            results.append((prog, h))
            verdicts[h.verdict] = verdicts.get(h.verdict, 0) + 1
            delta = f"{h.delta:+.3f}" if h.delta is not None else "  n/a "
            say(f"   {h.id} {h.kind:7s} {h.verdict:13s} {delta}  on {h.base_id}: {short(h.claim, 80)}")
            self.set_phase("deep", f"{len(results)}/{len(jobs)} tests scored")
            self.set_flow("coder", done=len(results))
        self.set_phase("deep", None)
        self.set_flow("coder", "done", note=", ".join(f"{n} {v}" for v, n in sorted(verdicts.items())))
        kinds = {k: sum(h.kind == k for _, h in results) for k in ("cause", "improve")}
        return [prog for prog, _ in results], {"tested": len(results), **kinds, **verdicts}

    def judge_test(self, h, base, prog):
        """Tune-then-judge: an improve test that adds or changes numbers gets a short search over just those
        numbers before it's judged, so a new mechanism is compared with its base at a good weight, not at
        the weight the Coder guessed. Knock-outs are measurements and are judged as written."""
        if h.kind == "improve":
            raw = self.tune_new_part(prog, base)
            if raw is not None:
                h.raw_delta = round(raw - base.score, 4)
        judge(h, base, prog, self.a.epsilon)

    def tune_new_part(self, prog, base):
        """Tune the numbers `prog` added relative to `base` (see tune.new_constants), in place.
        Returns the score before tuning if tuning improved it, else None."""
        if not (self.tune_eval and self.a.judge_tune_evals > 0 and prog.valid and prog.duplicate_of is None
                and prog.code and base.code):
            return None
        try:
            fresh = tuner.new_constants(base.code, prog.code)
            if not fresh:
                return None
            out = tuner.tune(prog.code, prog.score, self.tune_eval, evals=self.a.judge_tune_evals,
                             batch=min(8, self.a.judge_tune_evals), rng=self.rng, consts=fresh)
        except Exception as exc:          # a tuning failure must never lose the test itself
            say(f"   (tuning {prog.id}'s new weights failed: {type(exc).__name__}: {exc})")
            return None
        if not out or out["code"] is None:
            return None
        raw = prog.score
        prog.code, prog.score = out["code"], out["score"]
        prog.families = {f: v["excess_pct"] for f, v in out["result"]["families"].items()}
        self.store.candidate_path(prog.id).write_text(prog.code)
        changes = ", ".join(f"{a:g}→{b:g}" for a, b in out["changes"][:6])
        prog.note = (prog.note + " | " if prog.note else "") + f"new weights tuned {raw:.3f} → {out['score']:.3f}: {changes}"
        return raw

    def tune(self, pool, generation):
        """Tune branch: local search over the numbers of the champion and of the best untuned newcomer.
        A tuned program joins the pool only if it beats its original by --tune-margin."""
        ranked = [p for p in pool if p.valid and not p.probe]
        champ = self.store.best()
        targets = [champ] if champ and champ.id not in self.tuned and champ.branch != "seed" else []
        targets += [p for p in ranked if p.id not in self.tuned and p.branch in ("deep", "wide")
                    and p not in targets][: max(0, self.a.tune_targets - len(targets))]
        progs, tried, deadline = [], 0, time.time() + self.a.tune_seconds
        valid_split = _has_split("valid")
        for target in targets:
            if time.time() > deadline:
                break
            self.tuned.add(target.id)
            self.set_phase("tune", f"tuning {target.id}'s constants ({len(progs)} improved so far)")
            self.set_flow("tune", "active", note=f"tuning {target.id}", done=len(progs), total=len(targets))
            out = tuner.tune(target.code, target.score, self.tune_eval, evals=self.a.tune_evals,
                             batch=self.a.tune_workers * 2, seconds=deadline - time.time(), rng=self.rng)
            if out is None:
                continue                   # no numbers to tune
            tried += out["tried"]
            if out["code"] is None or out["score"] < target.score + self.a.tune_margin:
                continue
            if valid_split:                # a check on instances the tuning never saw, when the evaluator has them
                with_tuning = evaluate_code(out["code"], self.store.dir / "tune-check.py", "valid", self.a.eval_timeout)
                without = evaluate_file(self.store.candidate_path(target.id), "valid", self.a.eval_timeout)
                if not with_tuning["valid"] or (without["valid"] and with_tuning["score"] < without["score"]):
                    continue
            if self.store.duplicate_of(out["code"]) is not None:
                continue
            changes = ", ".join(f"{a:g}→{b:g}" for a, b in out["changes"][:8])
            prog = Program(id=self.store.new_id("p"), code=out["code"], generation=generation, branch="tune",
                           parent_id=target.id, valid=True, score=out["score"],
                           families={f: v["excess_pct"] for f, v in out["result"]["families"].items()},
                           note=f"tuned {len(out['changes'])} constants of {target.id} "
                                f"({out['score'] - target.score:+.3f}): {changes}")
            self.store.candidate_path(prog.id).write_text(prog.code)
            self.store.add_program(prog)
            progs.append(prog)
            say(f"   tune: {target.id} {target.score:.3f} → {prog.id} {prog.score:.3f} ({out['tried']} tries)")
        self.set_phase("tune", None)
        self.set_flow("tune", "done", note=f"{len(progs)} of {len(targets)} improved ({tried} evaluations)")
        return progs, {"targets": [t.id for t in targets], "tried": tried, "improved": len(progs)}

    # ================================================================ generations
    def survivors(self, programs, x):
        """Knock-out measurements (probes) never join the pool; everything else competes on score."""
        fresh = [p for p in programs if p.valid and p.duplicate_of is None and not p.probe]
        return sorted(fresh, key=lambda p: p.rank_key, reverse=True)[:x]

    def select_pool(self, ids):
        """(μ+λ) selection: the best --pool-size programs among the old pool and everything new, with at
        most --max-siblings children of one parent, so one lineage can't fill the pool."""
        progs = [self.store.programs[i] for i in dict.fromkeys(ids) if i in self.store.programs]
        ranked = self.survivors(progs, len(progs))
        pool, skipped, per_parent = [], [], {}
        for p in ranked:
            key = p.parent_id or p.id
            if per_parent.get(key, 0) >= self.a.max_siblings:
                skipped.append(p)
                continue
            per_parent[key] = per_parent.get(key, 0) + 1
            pool.append(p)
            if len(pool) == self.a.pool_size:
                break
        pool += skipped[: self.a.pool_size - len(pool)]
        return [p.id for p in pool]

    def generation(self, gen, pool_ids):
        started = time.time()
        pool = self.store.ranked(pool_ids)
        if self.a.mode == "full" and self.a.schedule == "alternate":
            branches = ["deep"] if gen % 2 == 1 else ["wide"]
        else:
            branches = {"full": ["deep", "wide"], "wide-only": ["wide"], "deep-only": ["deep"]}[self.a.mode]
        if self.a.tune:
            branches = branches + ["tune"]

        say(f"\n── generation {gen}: {' + '.join(branches)} | pool best {pool[0].score:.3f} ({pool[0].id})")
        self.set_status(generation=gen)
        self.reset_flow(gen, branches)
        self.set_flow("pool", "done", note=f"{len(pool)} programs, best {pool[0].score:.3f} ({pool[0].id})")
        with ThreadPoolExecutor(max_workers=len(branches)) as each:   # the branches run at the same time
            futures = {b: each.submit(getattr(self, b), pool, gen) for b in branches}
            out = {b: f.result() for b, f in futures.items()}

        best = self.store.best()
        self.set_flow("merge", "active")
        new_ids = [p.id for b in branches for p in out[b][0]]
        next_pool = self.select_pool(list(pool_ids) + new_ids + [best.id])
        kept_new = len(set(next_pool) & set(new_ids))
        self.set_flow("merge", "done", note=f"kept {kept_new} new of {len(new_ids)}; best {best.score:.3f} ({best.id})")

        record = {"generation": gen, "branches": branches, "pool": next_pool,
                  "best_id": best.id, "best_score": best.score, "seconds": round(time.time() - started, 1),
                  "started_at": round(started, 1), "finished_at": round(time.time(), 1),
                  "llm": self.llm.summary()}
        for b in branches:
            progs, extra = out[b]
            valid = [p for p in progs if p.valid and p.duplicate_of is None]
            record[b] = {"new": len(progs), "valid": len(valid),
                         "best_new": max((p.score for p in valid), default=None), **extra}
        self.store.log_generation(record)
        for b in branches:
            r = record[b]
            best_new = f"{r['best_new']:.3f}" if r["best_new"] is not None else "none valid"
            say(f"   {b}: {r['valid']}/{r['new']} valid, best new {best_new}")
        say(f"   best so far {best.score:.3f} ({best.id}, {best.branch}) | "
            f"{record['llm']['calls']} LLM calls total | {record['seconds']}s")
        return next_pool

    def seed(self):
        """Generation 0: score Code Zero, then one wide batch from it."""
        seed_path = Path(self.a.seed_program)
        code = seed_path.read_text()
        result = evaluate_file(seed_path, "train", self.a.eval_timeout)
        if not result["valid"]:
            sys.exit(f"Code Zero ({seed_path}) is invalid:\n{result['error']}")
        p = Program(id=self.store.new_id("p"), code=code, generation=0, branch="seed", valid=True,
                    score=result["score"], families={f: v["excess_pct"] for f, v in result["families"].items()},
                    note=f"Code Zero from {seed_path}")
        self.store.candidate_path(p.id).write_text(code)
        self.store.add_program(p)
        say(f"── generation 0: Code Zero scores {p.score:.3f} ({p.id})")
        self.reset_flow(0, [] if self.a.mode == "deep-only" else ["wide"])
        self.set_flow("pool", "done", note=f"Code Zero {p.score:.3f}")
        if self.a.mode == "deep-only":
            pool = [p.id]
        else:
            progs, _ = self.wide([p], 0)
            pool = self.select_pool([p.id] + [q.id for q in progs])
            valid = sum(q.valid for q in progs)
            say(f"   wide: {valid}/{len(progs)} valid, best so far {self.store.best().score:.3f}")
        self.set_flow("merge", "done", note=f"pool of {len(pool)}, best {self.store.best().score:.3f}")
        self.store.log_generation({"generation": 0, "branches": ["seed", "wide"], "pool": pool,
                                   "started_at": round(self.status["started"], 1), "finished_at": round(time.time(), 1),
                                   "best_id": self.store.best().id, "best_score": self.store.best().score,
                                   "llm": self.llm.summary()})
        return pool

    def zero_shot(self):
        say(f"── zero-shot control: {self.a.n} independent answers, no search")
        jobs = [self.workers.submit(self.candidate, "zeroshot", roles.zeroshot_message(), 0, "zeroshot")
                for _ in range(self.a.n)]
        progs = []
        for job in as_completed(jobs):
            progs.append(job.result())
            self.set_phase("zero-shot", f"{len(progs)}/{len(jobs)} answers scored")
        self.set_phase("zero-shot", None)
        valid = [p for p in progs if p.valid]
        self.store.log_generation({"generation": 0, "branches": ["zeroshot"], "pool": [p.id for p in valid],
                                   "best_id": self.store.best().id if valid else None,
                                   "best_score": self.store.best().score if valid else None,
                                   "llm": self.llm.summary()})
        say(f"   {len(valid)}/{len(progs)} valid")

    # ================================================================ main
    def run(self, start_gen, pool):
        deadline = time.time() + self.a.max_minutes * 60 if self.a.max_minutes else None
        (self.store.dir / "STOP").unlink(missing_ok=True)
        self.set_status(state="running", error=None)
        state, error = "finished", None
        self._alive = True

        def heartbeat():   # keeps the dashboard current while calls are slow (in flight, retrying)
            while self._alive:
                time.sleep(5)
                if self._alive:
                    try:
                        self.set_status()
                    except Exception:
                        pass
        threading.Thread(target=heartbeat, daemon=True).start()
        try:
            self.ensure_model_ready("before starting")
            if self.a.mode == "zero-shot":
                self.set_status(generation=0)
                self.zero_shot()
            else:
                if pool is None:
                    self.set_status(generation=0)
                    pool = self.seed()
                    self.publish_trace()
                for gen in range(start_gen, self.a.generations + 1):
                    if self.stop_requested():
                        say("\nStop requested. Everything so far is saved.")
                        state = "stopped"
                        break
                    if deadline and time.time() > deadline:
                        say(f"\nTime budget of {self.a.max_minutes} min reached.")
                        break
                    answered_before = self.llm.summary()["calls"]
                    pool = self.generation(gen, pool)
                    self.publish_trace()
                    if self.llm.summary()["calls"] == answered_before:
                        self.ensure_model_ready(f"no call answered in generation {gen}")
        except KeyboardInterrupt:
            state = "stopped"
            say("\nStopped. Everything so far is saved; continue with --resume " + str(self.store.dir))
        except (Exception, SystemExit) as exc:
            state = "crashed"
            error = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip()[-3000:]
            say(f"\nThe run crashed:\n{error}")
        finally:
            self._alive = False
            self.workers.shutdown(wait=False, cancel_futures=True)
            self.phases.clear()
            self.set_status(state=state, error=error, finished=time.time())
            if self.store.mirror:
                self.store.mirror.close()
        self.finish()
        self.publish_trace(final=True)
        if state == "crashed":
            sys.exit(1)

    def finish(self):
        best = self.store.best()
        seed = next((p for p in self.store.programs.values() if p.branch == "seed"), None)
        hyps = self.store.hypotheses
        usage = self.llm.summary()
        say("\n══ done")
        if best:
            gain = f" (Code Zero {seed.score:.3f}, gain {best.score - seed.score:+.3f})" if seed else ""
            say(f"best: {best.id} score {best.score:.3f}{gain}, found in generation {best.generation} by the {best.branch} branch")
        if hyps:
            for kind in ("cause", "improve"):
                mine = [h for h in hyps if h.kind == kind]
                if mine:
                    counts = {}
                    for h in mine:
                        counts[h.verdict] = counts.get(h.verdict, 0) + 1
                    say(f"{kind} tests: " + ", ".join(f"{n} {v}" for v, n in counts.items()))
        say(f"LLM: {usage['calls']} calls ({usage['pro_calls']} pro), {usage['tokens_in']:,} tokens in, "
            f"{usage['tokens_out']:,} out")
        say(f"run folder: {self.store.dir}")
        say(f"final held-out check:  python -m helix.report {self.store.dir}")


# ==================================================================== helpers
def say(msg):
    print(msg, flush=True)


def short(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _has_split(name):
    """Whether the evaluator offers a split (read from its code, never changed)."""
    try:
        from evaluator.problem import SPLITS
        return name in SPLITS
    except Exception:
        return False


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="python -m helix.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--engine", choices=["features", "programs"], default="features",
                    help="features: agents write features, an optimiser fits the weights (helix/evolve.py); "
                         "programs: agents write whole programs (the engine of runs 1-3)")
    ap.add_argument("--mode", choices=["full", "wide-only", "deep-only", "zero-shot"], default="full")
    ap.add_argument("--schedule", choices=["parallel", "alternate"], default="parallel",
                    help="parallel: deep and wide every generation; alternate: deep on odd, wide on even")
    ap.add_argument("--generations", type=int, default=20)
    ap.add_argument("--max-minutes", type=float, default=0, help="stop after this long (0 = no limit)")
    ap.add_argument("--top-x", type=int, default=4, help="programs the Mutator works from (the top of the pool)")
    ap.add_argument("--pool-size", type=int, default=8, help="programs kept from one generation to the next")
    ap.add_argument("--max-siblings", type=int, default=3, help="most pool slots that children of one parent can hold")
    ap.add_argument("--variants", type=int, default=None,
                    help="Mutator programs (programs engine, default 6) or features (features engine, default 4) per generation")
    ap.add_argument("--fresh", type=int, default=None, help="of those, how many ask for a fresh idea (default 2 / 1)")
    ap.add_argument("--hypotheses", type=int, default=4, help="Researcher hypotheses per generation")
    ap.add_argument("--n", type=int, default=40, help="answers in zero-shot mode")
    ap.add_argument("--epsilon", type=float, default=0.05,
                    help="score change that counts as supported/refuted; smaller changes are 'flat'. Scoring is "
                         "deterministic and champions in past runs gained 0.01-0.2, so this stays small; the "
                         "held-out check at the end guards against overfitting")
    ap.add_argument("--jump", type=float, default=0.15,
                    help="a new champion that beats the old one by at least this much gets knock-out tests")
    ap.add_argument("--stall", type=int, default=3,
                    help="generations without a new best before the search pushes for bigger changes")
    ap.add_argument("--judge-tune-evals", type=int, default=16,
                    help="evaluations spent tuning a deep test's new numbers before it's judged (0 = off)")
    ap.add_argument("--repairs", type=int, default=1, help="repair attempts for a program that fails")
    ap.add_argument("--workers", type=int, default=12,
                    help="LLM calls and evaluations in flight at once (12 = a whole generation at once)")
    ap.add_argument("--wait-minutes", type=float, default=15,
                    help="how long to wait for the model to start answering before giving up")
    ap.add_argument("--eval-timeout", type=float, default=60.0, help="seconds before a program counts as hung")
    ap.add_argument("--pro-every", type=int, default=10, help="every Nth LLM call uses HELIX_PRO_MODEL (0 = never)")
    ap.add_argument("--tune", action=argparse.BooleanOptionalAction, default=None,
                    help="tune branch: local search over the champion's numbers (default: on in full mode)")
    ap.add_argument("--tune-evals", type=int, default=48, help="evaluations per tuned program")
    ap.add_argument("--tune-targets", type=int, default=2, help="programs tuned per generation")
    ap.add_argument("--tune-seconds", type=float, default=40, help="time limit for the tune branch per generation")
    ap.add_argument("--tune-margin", type=float, default=0.05, help="gain a tuned program needs to be kept")
    ap.add_argument("--tune-workers", type=int, default=max(2, (os.cpu_count() or 4) // 2),
                    help="evaluations in parallel while tuning")
    ap.add_argument("--seed-program", default=str(REPO_ROOT / "programs" / "code_zero.py"))
    fe = ap.add_argument_group("features engine")
    fe.add_argument("--trial-evals", type=int, default=24, help="evaluations searching a new feature's weights")
    fe.add_argument("--trial-sigma", type=float, default=0.5, help="step size searching a new feature's weights")
    fe.add_argument("--refit-evals", type=int, default=64, help="evaluations of the joint refit when features are kept")
    fe.add_argument("--inspect", action=argparse.BooleanOptionalAction, default=True,
                    help="show the Researcher the champion's packings next to near-optimal packings of the same jobs")
    fe.add_argument("--trial-refit-evals", type=int, default=24,
                    help="evaluations of each of a feature's two paired refits (with it, and with it switched off)")
    fe.add_argument("--champion-refit-evals", type=int, default=24,
                    help="evaluations refitting the champion's own weights each generation, before features are tried")
    fe.add_argument("--refit-sigma", type=float, default=0.15)
    fe.add_argument("--accept-margin", type=float, default=0.03,
                    help="validation gain a feature needs to be kept, and loss that retires one (one bin on one "
                         "validation instance is about 0.017)")
    fe.add_argument("--max-columns", type=int, default=60, help="most weights the policy may have")
    fe.add_argument("--fit-workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="processes scoring policies in parallel")
    fe.add_argument("--fit-timeout", type=float, default=900, help="seconds before a batch of evaluations counts as hung")
    ap.add_argument("--fake-llm", action="store_true", help="offline test double instead of Luminal")
    ap.add_argument("--publish", action=argparse.BooleanOptionalAction, default=None,
                    help="keep results/<run>/ updated every generation (default: on for real runs, off with --fake-llm)")
    ap.add_argument("--run-dir", help="where to save this run (default helix/runs/<time>-<mode>)")
    ap.add_argument("--resume", help="a run folder to continue")
    return ap.parse_args(argv)


# On --resume these come from the run's own config.json, so a run continues with the algorithm it started with.
KEPT_ON_RESUME = ["engine", "inspect", "trial_evals", "trial_sigma", "trial_refit_evals", "refit_evals",
                  "champion_refit_evals", "refit_sigma", "accept_margin", "max_columns",
                  "mode", "schedule", "top_x", "pool_size", "max_siblings", "variants", "fresh", "hypotheses", "n",
                  "epsilon", "jump", "stall", "judge_tune_evals", "repairs", "pro_every", "seed_program", "fake_llm",
                  "tune", "tune_evals", "tune_targets",
                  "tune_seconds", "tune_margin"]


def main(argv=None):
    args = parse_args(argv)
    if args.resume:
        cfg_path = Path(args.resume) / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            for key in KEPT_ON_RESUME:
                if key in cfg:
                    setattr(args, key, cfg[key])

    if args.publish is None:
        args.publish = not args.fake_llm
    old_cfg = Path(args.resume) / "config.json" if args.resume else None
    if old_cfg and old_cfg.exists() and "engine" not in json.loads(old_cfg.read_text()):
        args.engine = "programs"                    # runs from before the feature engine existed
    features = args.engine == "features"
    if args.variants is None:
        args.variants = 4 if features else 6
    if args.fresh is None:
        args.fresh = 1 if features else 2
    if args.tune is None:
        args.tune = args.mode == "full" and not features
    if features and args.mode == "zero-shot":
        args.engine, features = "programs", False   # zero-shot is a control of the programs engine
    settings = Settings.from_env(pro_every=args.pro_every)
    if not args.fake_llm and settings.problems():
        sys.exit(f"Missing {', '.join(settings.problems())}. Fill them in on the dashboard (python -m helix.ui) "
                 "or in helix/.env, or run with --fake-llm to test offline.")

    if args.resume:
        store, last = Store.load(args.resume)
        if last is None:
            sys.exit(f"{args.resume} has no completed generation to resume from")
        start_gen, pool = last["generation"] + 1, last["pool"]
        store.mirror = Mirror(store.dir.name)
    else:
        run_dir = Path(args.run_dir) if args.run_dir else RUNS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.mode}"
        store, start_gen, pool = Store(run_dir), 1, None
        store.mirror = Mirror(store.dir.name)
        fake = args.fake_llm
        store.save_config({**vars(args), "provider": "fake" if fake else settings.provider,
                           "flash_model": "fake" if fake else settings.flash_model,
                           "pro_model": "" if fake else settings.pro_model,
                           "base_url": "" if fake else settings.base_url, "temperature": TEMPERATURE})

    llm_cls = FakeLLM if args.fake_llm else LLM
    llm = llm_cls(settings, store.dir / "llm_calls.jsonl")
    pro = f", pro {settings.pro_model} every {args.pro_every} calls" if settings.pro_model and args.pro_every else ""
    model = "fake (offline)" if args.fake_llm else f"{settings.provider}: {settings.flash_model}"
    say(f"Helix | engine {args.engine} | mode {args.mode} | models {model}{pro}")
    say(f"run folder: {store.dir}")
    if store.mirror.enabled:
        say(f"mirroring to MongoDB database '{store.mirror.db_name}'")
    elif store.mirror.status["error"]:
        say(f"MongoDB mirror off: {store.mirror.status['error']}")
    if args.engine == "features":
        from .evolve import FeatureSearch
        FeatureSearch(args, store, llm).run(start_gen, pool)
    else:
        Search(args, store, llm).run(start_gen, pool)


if __name__ == "__main__":
    main()
