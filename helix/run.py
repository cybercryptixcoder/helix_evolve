"""The two-loop search. Run from the repo root:

  python -m helix.run --generations 20              the full algorithm
  python -m helix.run --fake-llm --generations 3    offline test, no keys needed
  python -m helix.run --mode wide-only              control: a conventional single-mutator search
  python -m helix.run --mode zero-shot --n 40       control: best of N plain answers, no search
  python -m helix.run --resume helix/runs/<run>     continue a stopped run

One generation:
  1. Rank the current pool.
  2. Deep branch: the Researcher reads the ranked programs, their per-family scores and the
     research log, and proposes hypotheses. The Coder writes one program per hypothesis,
     changing only that aspect of its base program. Each is scored and judged against its
     base (supported / refuted / flat). The top X go forward.
  3. Wide branch: the Mutator sees only the top X programs' code and scores (the air gap)
     and writes variants with no direction. The top X go forward.
  4. Merge both branches' survivors, plus the best program found so far, into the next pool.

Generation 0 is Code Zero plus one wide batch, because there's nothing to research yet.
"""
import argparse
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import roles
from .llm import LLM, FakeLLM, Settings
from .mongo import Mirror
from .population import Hypothesis, Program, Store, judge
from .sandbox import REPO_ROOT, evaluate_code, evaluate_file

RUNS_DIR = Path(__file__).resolve().parent / "runs"
# Mutator runs hot for variety; Coder runs cool so it changes only what it's told.
TEMPERATURE = {"mutator": 1.0, "researcher": 0.7, "coder": 0.3, "zeroshot": 1.0}
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

    # ================================================================ live status (read by the dashboard)
    def set_status(self, **fields):
        with self._status_lock:
            self.status.update(fields)
            best = self.store.best()
            self.status.update(phase=" | ".join(f"{b}: {t}" for b, t in self.phases.items()),
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

    def stop_requested(self):
        return (self.store.dir / "STOP").exists()

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
    def candidate(self, role, user, generation, branch, parent_id=None, hypothesis_id=None):
        """Ask one agent for a program, score it, repair it once if it fails. Always returns a Program."""
        pid = self.store.new_id("p")
        system = roles.system_prompt(role)
        prog = Program(id=pid, code="", generation=generation, branch=branch,
                       parent_id=parent_id, hypothesis_id=hypothesis_id)
        try:
            reply = self.llm.chat(role, system, user, temperature=TEMPERATURE[role])
        except Exception as exc:
            prog.error = f"LLM call failed: {exc}"
            self.store.add_program(prog)
            return prog
        prog.model, prog.note = reply.model, roles.extract_note(reply.text)
        code = roles.extract_code(reply.text)

        for attempt in range(self.a.repairs + 1):
            if code is None:
                result = {"valid": False, "error": "reply had no ```python block defining priority()"}
            else:
                prog.code = code
                dup = self.store.duplicate_of(code)
                if dup is not None:
                    prog.duplicate_of = dup.id
                    prog.valid, prog.score, prog.families, prog.error = dup.valid, dup.score, dup.families, dup.error
                    break
                # The tiny `quick` split first, so broken or very slow programs fail in a second.
                result = evaluate_code(code, self.store.candidate_path(pid), "quick", min(15.0, self.a.eval_timeout))
                if result["valid"]:
                    result = evaluate_file(self.store.candidate_path(pid), "train", self.a.eval_timeout)
            if result["valid"]:
                prog.valid, prog.score, prog.error = True, result["score"], None
                prog.families = {f: v["excess_pct"] for f, v in result["families"].items()}
                break
            prog.error = result["error"]
            if attempt == self.a.repairs:
                break
            try:   # one repair: show the agent its own error
                fix = self.llm.chat(f"{role}-repair", system, roles.repair_message(code or reply.text, prog.error),
                                    temperature=TEMPERATURE[role])
            except Exception as exc:
                prog.error += f"\n(repair call failed: {exc})"
                break
            prog.repaired = True
            code = roles.extract_code(fix.text)

        self.store.add_program(prog)
        return prog

    # ================================================================ the two branches
    def wide(self, pool, generation):
        """Mutator: top X programs in, variants out. Only code and score cross the air gap."""
        top = [p for p in pool if p.valid][: self.a.top_x]
        scored = [roles.Scored(p.code, p.score) for p in top]
        jobs = []
        for i in range(self.a.variants):
            t = i % len(top)
            msg = roles.mutator_message(scored[t], scored[:t] + scored[t + 1:])
            jobs.append(self.workers.submit(self.candidate, "mutator", msg, generation, "wide", top[t].id))
        self.set_phase("wide", f"Mutator writing {len(jobs)} variants")
        progs = []
        for job in as_completed(jobs):
            progs.append(job.result())
            self.set_phase("wide", f"{len(progs)}/{len(jobs)} variants scored")
        self.set_phase("wide", None)
        return progs, {}

    def deep(self, pool, generation):
        """Researcher forms hypotheses; Coder tests each with a one-aspect change; verdicts go in the log."""
        shown = [p for p in pool if p.valid][:RESEARCHER_SHOWN]
        msg = roles.researcher_message(shown, self.store.hypotheses, self.a.hypotheses, generation)
        self.set_phase("deep", f"Researcher reading {len(shown)} programs")
        try:
            reply = self.llm.chat("researcher", roles.system_prompt("researcher"), msg, temperature=TEMPERATURE["researcher"])
            proposals = roles.extract_hypotheses(reply.text, {p.id for p in shown}, shown[0].id)[: self.a.hypotheses]
        except Exception as exc:
            say(f"   deep: Researcher call failed ({exc}); skipping the deep branch this generation")
            self.set_phase("deep", None)
            return [], {"tested": 0}
        if not proposals:
            say("   deep: Researcher reply had no usable hypotheses; skipping the deep branch this generation")
            self.set_phase("deep", None)
            return [], {"tested": 0}
        self.set_phase("deep", f"Coder testing {len(proposals)} hypotheses")

        def test(prop):
            base = self.store.programs[prop["base"]]
            h = Hypothesis(id=self.store.new_id("h"), generation=generation, base_id=base.id,
                           claim=prop["claim"], change=prop["change"], prediction=prop["prediction"])
            prog = self.candidate("coder", roles.coder_message(base, h), generation, "deep", base.id, h.id)
            judge(h, base, prog, self.a.epsilon)
            self.store.add_hypothesis(h)
            return prog, h

        jobs = [self.workers.submit(test, p) for p in proposals]
        results, verdicts = [], {}
        for job in as_completed(jobs):
            prog, h = job.result()
            results.append((prog, h))
            verdicts[h.verdict] = verdicts.get(h.verdict, 0) + 1
            delta = f"{h.delta:+.3f}" if h.delta is not None else "  n/a "
            say(f"   {h.id} {h.verdict:9s} {delta}  on {h.base_id}: {short(h.claim, 90)}")
            self.set_phase("deep", f"{len(results)}/{len(jobs)} hypotheses tested")
        self.set_phase("deep", None)
        return [prog for prog, _ in results], {"tested": len(results), **verdicts}

    # ================================================================ generations
    def survivors(self, programs, x):
        fresh = [p for p in programs if p.valid and p.duplicate_of is None]
        return sorted(fresh, key=lambda p: p.rank_key, reverse=True)[:x]

    def generation(self, gen, pool_ids):
        started = time.time()
        pool = self.store.ranked(pool_ids)
        if self.a.mode == "full" and self.a.schedule == "alternate":
            branches = ["deep"] if gen % 2 == 1 else ["wide"]
        else:
            branches = {"full": ["deep", "wide"], "wide-only": ["wide"], "deep-only": ["deep"]}[self.a.mode]

        say(f"\n── generation {gen}: {' + '.join(branches)} | pool best {pool[0].score:.3f} ({pool[0].id})")
        self.set_status(generation=gen)
        with ThreadPoolExecutor(max_workers=2) as both:   # deep and wide run at the same time
            futures = {b: both.submit(getattr(self, b), pool, gen) for b in branches}
            out = {b: f.result() for b, f in futures.items()}

        best = self.store.best()
        next_pool = []
        for b in branches:
            next_pool += [p.id for p in self.survivors(out[b][0], self.a.top_x)]
        next_pool = list(dict.fromkeys(next_pool + [best.id]))  # always keep the best ever
        if len(next_pool) == 1 and best.id in pool_ids:        # nothing new survived: keep the old pool
            next_pool = list(pool_ids)

        record = {"generation": gen, "branches": branches, "pool": next_pool,
                  "best_id": best.id, "best_score": best.score, "seconds": round(time.time() - started, 1),
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
        if self.a.mode == "deep-only":
            pool = [p.id]
        else:
            progs, _ = self.wide([p], 0)
            pool = list(dict.fromkeys([q.id for q in self.survivors(progs, self.a.top_x)] + [self.store.best().id]))
            valid = sum(q.valid for q in progs)
            say(f"   wide: {valid}/{len(progs)} valid, best so far {self.store.best().score:.3f}")
        self.store.log_generation({"generation": 0, "branches": ["seed", "wide"], "pool": pool,
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
        try:
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
                    pool = self.generation(gen, pool)
                    self.publish_trace()
        except KeyboardInterrupt:
            state = "stopped"
            say("\nStopped. Everything so far is saved; continue with --resume " + str(self.store.dir))
        except (Exception, SystemExit) as exc:
            state = "crashed"
            error = "".join(traceback.format_exception(exc)).strip()[-3000:]
            say(f"\nThe run crashed:\n{error}")
        finally:
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
            counts = {v: sum(h.verdict == v for h in hyps) for v in ("supported", "refuted", "flat", "invalid", "unchanged")}
            say("hypotheses tested: " + ", ".join(f"{n} {v}" for v, n in counts.items() if n))
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


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="python -m helix.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=["full", "wide-only", "deep-only", "zero-shot"], default="full")
    ap.add_argument("--schedule", choices=["parallel", "alternate"], default="parallel",
                    help="parallel: deep and wide every generation; alternate: deep on odd, wide on even")
    ap.add_argument("--generations", type=int, default=20)
    ap.add_argument("--max-minutes", type=float, default=0, help="stop after this long (0 = no limit)")
    ap.add_argument("--top-x", type=int, default=4, help="survivors kept from each branch")
    ap.add_argument("--variants", type=int, default=6, help="Mutator programs per generation")
    ap.add_argument("--hypotheses", type=int, default=4, help="Researcher hypotheses per generation")
    ap.add_argument("--n", type=int, default=40, help="answers in zero-shot mode")
    ap.add_argument("--epsilon", type=float, default=0.4,
                    help="score change that counts as supported/refuted; smaller changes are 'flat'. 0.4 is about "
                         "the gap between baselines, so smaller differences may just be noise across instances")
    ap.add_argument("--repairs", type=int, default=1, help="repair attempts for a program that fails")
    ap.add_argument("--workers", type=int, default=8, help="LLM calls and evaluations in flight at once")
    ap.add_argument("--eval-timeout", type=float, default=60.0, help="seconds before a program counts as hung")
    ap.add_argument("--pro-every", type=int, default=10, help="every Nth LLM call uses HELIX_PRO_MODEL (0 = never)")
    ap.add_argument("--seed-program", default=str(REPO_ROOT / "programs" / "code_zero.py"))
    ap.add_argument("--fake-llm", action="store_true", help="offline test double instead of Luminal")
    ap.add_argument("--publish", action=argparse.BooleanOptionalAction, default=None,
                    help="keep results/<run>/ updated every generation (default: on for real runs, off with --fake-llm)")
    ap.add_argument("--run-dir", help="where to save this run (default helix/runs/<time>-<mode>)")
    ap.add_argument("--resume", help="a run folder to continue")
    return ap.parse_args(argv)


# On --resume these come from the run's own config.json, so a run continues with the algorithm it started with.
KEPT_ON_RESUME = ["mode", "schedule", "top_x", "variants", "hypotheses", "n", "epsilon", "repairs",
                  "pro_every", "seed_program", "fake_llm"]


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
    say(f"Helix | mode {args.mode} | schedule {args.schedule} | models {model}{pro}")
    say(f"run folder: {store.dir}")
    if store.mirror.enabled:
        say(f"mirroring to MongoDB database '{store.mirror.db_name}'")
    elif store.mirror.status["error"]:
        say(f"MongoDB mirror off: {store.mirror.status['error']}")
    Search(args, store, llm).run(start_gen, pool)


if __name__ == "__main__":
    main()
