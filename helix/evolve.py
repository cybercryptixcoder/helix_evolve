"""The feature engine: agents invent features, an optimiser fits the weights, validation decides.

Why: in runs 2 and 3 of the program engine, agents wrote whole programs, numbers included, and judged
them by scores alone; the runs stalled at 27% and 19% of the way from Code Zero to the optimal packing.
Agents are better at ideas than at numbers, and they were working blind. So the work is split.

The starting point is the same as the program engine's: generation 0 is Code Zero and nothing else (an
empty library scores every bin 0, which is first fit, which is Code Zero). Every gain after that is the
search's own.

- the **library** holds features (small functions that measure a candidate bin); the policy is a weighted
  sum of them, and the weights are fitted by CMA-ES (helix/fit.py), never chosen by an agent;
- **inspect**: every generation the champion's packings are compared with near-optimal packings of the
  same jobs (helix/instruments.py), so the Researcher sees *how* the policy loses;
- **deep**: the Researcher reads that comparison and proposes features aimed at specific differences;
  the Coder writes each one;
- **wide**: the Mutator sees only the policy's code and score (the air gap) and writes variants of its
  features, or fresh ones;
- **fit**: first the champion's own weights are refitted (so fitting keeps improving the policy, and no
  feature is credited with that); then each new feature is tried: its own weights are searched, then all
  the weights are refitted twice, with the feature and with it switched off, and the feature is credited
  with the difference, on train and on separate validation instances;
- **accept**: features that help on validation are combined greedily (each joins only if validation
  improves again), then refitted together; features that hurt are retired.

The champion is always an ordinary priority() program (helix/features.compose), scored by the unchanged
evaluator, so runs of both engines are compared on the same score.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from . import instruments, metrics, roles
from .bounds import diagnostic_instances, family_floor
from .features import Feature, FeatureError, compose, docstring, prepare, split_vector
from .fit import FitError, Fitter, train_index
from .population import Hypothesis, Program, read_records
from .run import MAX_TOKENS, THINK_LIMIT, Search, say, short
from .sandbox import evaluate_file

TEMPERATURE = {"feature_researcher": 0.6, "feature_coder": 0.2, "feature_mutator": 0.8}
for _r in ("feature_researcher", "feature_coder", "feature_mutator"):
    MAX_TOKENS.setdefault(_r, 6000 if _r == "feature_researcher" else 3000)
    THINK_LIMIT.setdefault(_r, 16000 if _r == "feature_researcher" else 8000)


class FeatureSearch(Search):
    FLOW_NODES = ("library", "inspect", "researcher", "coder", "mutator", "fit", "accept")

    def __init__(self, args, store, llm):
        super().__init__(args, store, llm)
        self.fitter = Fitter(workers=args.fit_workers, timeout=args.fit_timeout,
                             fit_split=getattr(args, "fit_split", "train"))
        self.features = {}            # id -> Feature (every feature ever tried)
        self.library = []             # ids of the active features, in order
        self.champ = None             # {"id", "x", "train", "fams", "valid", "vfams"}
        self.base_seconds = None      # seconds per evaluation of the current library (speed check)
        self._restore()

    # ================================================================ persistence
    def save_feature(self, f):
        with self.store._lock:
            with (self.store.dir / "features.jsonl").open("a") as fh:
                fh.write(json.dumps(f.record()) + "\n")
        if self.store.mirror:
            self.store.mirror.put("features", f.record(), key="id")

    def new_feature(self, **kw):
        f = Feature(id=self.store.new_id("f"), **kw)
        self.features[f.id] = f
        return f

    def _restore(self):
        """On --resume: the features and the champion as they were at the end of the last generation."""
        for rec in read_records(self.store.dir / "features.jsonl"):
            self.features[rec["id"]] = Feature(**{k: v for k, v in rec.items() if k in Feature.__dataclass_fields__})
        if self.features:
            self.store._counters["f"] = max(int(i[1:]) for i in self.features)
        gens = read_records(self.store.dir / "generations.jsonl")
        if gens and gens[-1].get("champion"):
            c = gens[-1]["champion"]
            self.library = list(c["features"])
            for f, w in zip(self.lib(), split_vector(self.lib(), c["x"])):
                f.weights = w
            self.champ = {"id": c["id"], "x": np.asarray(c["x"], dtype=float), "train": c["train"],
                          "fams": c.get("fams") or {}, "valid": c["valid"], "vfams": c.get("vfams") or {}}
            for extra in ("official", "official_fams"):
                if c.get(extra) is not None:
                    self.champ[extra] = c[extra]

    def lib(self, ids=None):
        return [self.features[i] for i in (ids if ids is not None else self.library)]

    # ================================================================ flowchart
    def reset_flow(self, generation, branches):
        with self._status_lock:
            self.flow_generation = generation
            uses = {"library": True, "inspect": generation > 0 and self.a.inspect, "researcher": "deep" in branches,
                    "coder": "deep" in branches, "mutator": "wide" in branches, "fit": generation > 0, "accept": True}
            self.flow = {n: {"state": "waiting" if uses[n] else "off"} for n in self.FLOW_NODES}
        self.set_status()

    # ================================================================ agents
    def ask_code(self, role, user, generation, branch, fid, define="feature"):
        """One agent call for code, with one code-only retry if the reply has none. Returns (code, text)."""
        system = roles.system_prompt(role)
        tag = {"generation": generation, "branch": branch, "feature": fid}
        kw = dict(temperature=TEMPERATURE[role], max_tokens=MAX_TOKENS[role], think_limit=THINK_LIMIT[role], tag=tag)
        try:
            reply = self.llm.chat(role, system, user, **kw)
        except Exception as exc:
            return None, f"LLM call failed: {exc}"
        code = roles.extract_code(reply.text, define, flexible=(define == "feature"))
        text = reply.text
        if code is None:
            try:
                again = self.llm.chat(f"{role}-retry", system, roles.code_only_message(user, reply.text), **kw)
                code, text = roles.extract_code(again.text, define, flexible=(define == "feature")), again.text
            except Exception as exc:
                return None, f"retry failed: {exc}"
        return code, text

    def deep(self, generation, context, notify=None):
        """Researcher -> ideas -> Coder writes each feature. Returns [(Feature, idea)].
        `notify(f)` is called from the worker as each feature is written, so fitting can start early."""
        self.set_phase("deep", "Researcher reading the packings")
        self.set_flow("researcher", "active", note="reading the packing comparison")
        system = roles.system_prompt("feature_researcher")
        msg = roles.feature_researcher_message(generation, context["champion"], context["library_lines"],
                                               context["room_lines"], context["packings"], context["log_lines"],
                                               self.a.hypotheses, context.get("progress"), context.get("stuck", 0))
        ideas = []
        for attempt in range(2):
            text = msg if attempt == 0 else msg + ("\n\nYour previous reply ran out of room before the JSON. Reply "
                                                   "with ONLY the ```json block, each field under 40 words.")
            try:
                reply = self.llm.chat("feature_researcher" if attempt == 0 else "feature_researcher-retry", system, text,
                                      temperature=TEMPERATURE["feature_researcher"],
                                      max_tokens=MAX_TOKENS["feature_researcher"],
                                      think_limit=THINK_LIMIT["feature_researcher"],
                                      tag={"generation": generation, "branch": "deep"})
                ideas = roles.extract_feature_ideas(reply.text)[: self.a.hypotheses]
            except Exception as exc:
                say(f"   deep: Researcher call failed ({str(exc)[:120]})")
            if ideas:
                break
        if not ideas:
            self.set_flow("researcher", "failed", note="no usable ideas after a retry")
            self.set_flow("coder", "off")
            self.set_phase("deep", None)
            return []
        self.set_flow("researcher", "done", note=f"{len(ideas)} feature ideas")
        self.set_flow("coder", "active", done=0, total=len(ideas), note="writing features")
        self.set_phase("deep", f"Coder writing {len(ideas)} features")
        existing = context["existing_lines"]

        def write(idea):
            hid = self.store.new_id("h")
            f = self.new_feature(name=idea["name"], code="", description=idea["feature"][:300], branch="deep",
                                 generation=generation, hypothesis_id=hid)
            code, text = self.ask_code("feature_coder", roles.feature_coder_message(idea, existing), generation, "deep", f.id)
            f.code = code or ""
            f.note = roles.extract_note(text) if code else ""
            if not code:
                f.status, f.error = "invalid", (text or "no code")[:300]
            return f, {**idea, "hid": hid}

        out = []
        for job in as_completed([self.workers.submit(write, i) for i in ideas]):
            item = job.result()
            out.append(item)
            if notify is not None:
                notify(item[0])
            self.set_flow("coder", done=len(out))
        self.set_flow("coder", "done", note=f"{sum(f.status != 'invalid' for f, _ in out)} of {len(out)} written")
        self.set_phase("deep", None)
        return out

    def wide(self, generation, context, notify=None):
        """Mutator: from the policy's code and score only, variants of its features and fresh ones."""
        n = self.a.variants
        fresh = min(self.a.fresh, n)
        targets = context["mutation_targets"]
        picks = [targets[(generation + i) % len(targets)] if targets else None for i in range(n - fresh)] + [None] * fresh
        self.set_phase("wide", f"Mutator writing {n} features")
        self.set_flow("mutator", "active", done=0, total=n, note=f"{n - fresh} variants, {fresh} fresh")
        policy = roles.Scored(context["champion_code"], context["champion"]["train"])

        def write(target):
            f = self.new_feature(name="", code="", description="", branch="wide", generation=generation,
                                 note=f"variant of {target}" if target else "fresh")
            code, text = self.ask_code("feature_mutator", roles.feature_mutator_message(policy, target), generation,
                                       "wide", f.id)
            f.code = code or ""
            f.name = roles.extract_feature_name(text or "", f"wide_{f.id}")
            f.description = docstring(f.code) or f.note
            if target:
                f.parent_ids = [target.split(" ")[0].lstrip("_")]
            if not code:
                f.status, f.error = "invalid", (text or "no code")[:300]
            return f

        out = []
        for job in as_completed([self.workers.submit(write, t) for t in picks]):
            f = job.result()
            out.append(f)
            if notify is not None:
                notify(f)
            self.set_flow("mutator", done=len(out))
        self.set_flow("mutator", "done", note=f"{sum(f.status != 'invalid' for f in out)} of {len(out)} written")
        self.set_phase("wide", None)
        return out

    # ================================================================ checking and trying a feature
    def check(self, f, generation):
        """Make sure a feature compiles, runs, returns finite values of the right shape, and isn't too slow;
        one repair by its author if not. Sets its columns and scales. Returns True if usable."""
        for attempt in range(2):
            f.columns, f.scales, f.weights = ["value"], [1.0], [0.0]
            try:
                if not f.code:
                    raise FeatureError(f.error or "no code")
                prepare(f.code, f.id)
                trial = self.lib() + [f]
                x = np.concatenate([self.champ["x"], np.zeros(1)])
                width, scales = self.fitter.feature_scales(trial, x, len(trial) - 1)
                f.columns = [f.name] if width == 1 else [f"{f.name}_{i}" for i in range(width)]
                f.scales, f.weights = scales, [0.0] * width
                x = np.concatenate([self.champ["x"], np.full(width, 0.1)])
                secs = self.fitter.seconds_per_eval(trial, x)
                if self.base_seconds is None:
                    self.base_seconds = self.fitter.seconds_per_eval(self.lib(), self.champ["x"]) or 0.1
                if secs > max(3.0 * self.base_seconds, self.base_seconds + 4.0):
                    raise FeatureError(f"too slow: an evaluation takes {secs:.1f}s with it, {self.base_seconds:.1f}s "
                                       "without; vectorise it (no Python loops over bins)")
                f.error = None
                return True
            except (FeatureError, FitError) as exc:
                f.error = str(exc)[:500]
                if attempt == 1 or not f.code or f.branch == "seed":
                    break
                role = "feature_coder" if f.branch == "deep" else "feature_mutator"
                code, text = self.ask_code(role, roles.repair_message(f.code, f.error).replace(
                    "Here is the program", "Here is the feature"), generation, f.branch, f.id)
                if not code:
                    break
                if f.branch == "wide":
                    f.name = roles.extract_feature_name(text or "", f.name)
                    f.description = docstring(code) or f.description
                f.code = code
                f.note = (f.note + " | repaired").strip(" |")
        f.status = "invalid"
        return False

    def probe(self, f):
        """Cheap first pass, before the expensive line search and paired refits.

        Scores the new feature alone on top of the champion at a few strong weights of both signs. For a
        single-column feature, sign is all that matters at generation 0 (the whole policy is w x feature,
        so any w > 0 gives the same packing); otherwise the probe is an approximation, so it only rejects
        features that lose by more than --probe-margin (anywhere in a wide magnitude range)."""
        if f.width != 1 or not f.code:
            return None
        feats = self.lib() + [f]
        x0 = np.concatenate([self.champ["x"], np.zeros(1)])
        # Large magnitudes catch catastrophic features; the small ones catch subtle tie-breakers that
        # only pay off at low weight (a win can live anywhere on the line — measure both ends).
        mags = (2.0, -2.0, 0.4, -0.4, 0.1, -0.1)
        X = []
        for m in mags:
            x = x0.copy()
            x[-1] = m
            X.append(x)
        try:
            res = self.fitter.evaluate(feats, X, "train")
        except FitError:
            return None
        best = None
        for m, x, (s, fams) in zip(mags, X, res):
            if s is not None and (best is None or s > best[0]):
                best = (s, x, fams, m)
        return best

    def trial(self, f):
        """Try one feature on top of the champion, on train, then score it on validation.

        0. A cheap probe at a few strong weights; a feature that clearly loses everywhere is rejected
           without the full search (the gain can't pay for the refits).
        1. Search only the feature's own weights, with the champion's fixed.
        2. Refit all the weights twice from that point, with the same budget, step size and random seed:
           once with the feature and once with it switched off (its values multiplied by 0). Features often
           pay off only once the other weights adjust to them; the second refit is the control, so the
           feature is credited only with the difference, never with what refitting alone finds."""
        feats = self.lib() + [f]
        n = len(self.champ["x"])
        x0 = np.concatenate([self.champ["x"], np.zeros(f.width)])
        seed = int(f.id[1:])
        base = (self.champ["train"], self.champ["fams"])
        probe = self.probe(f)
        if probe is not None:
            if probe[0] < self.champ["train"] - self.a.probe_margin:
                f.delta_train = round(probe[0] - self.champ["train"], 4)
                f.delta_valid = None
                return {"feature": f, "x": np.asarray(probe[1]), "train": probe[0], "fams": probe[2],
                        "valid": None, "vfams": None, "early": True}
            x0, base = np.asarray(probe[1]), (probe[0], probe[2])
        x, s, fams = self.fitter.optimise(feats, x0, self.a.trial_evals, sigma=self.a.trial_sigma,
                                          base=base, seed=seed,
                                          free=list(range(n, n + f.width)))
        ref = {"x": np.concatenate([self.champ["x"], np.zeros(f.width)]), "train": self.champ["train"],
               "valid": self.champ["valid"]}
        if n and self.a.trial_refit_evals > 0:
            muted = self.lib() + [replace(f, scales=[0.0] * f.width)]
            start = x
            x, s, fams = self.fitter.optimise(feats, start, self.a.trial_refit_evals, sigma=self.a.refit_sigma,
                                              base=(s, fams), seed=seed + 1)
            xr, sr, _ = self.fitter.optimise(muted, start, self.a.trial_refit_evals, sigma=self.a.refit_sigma,
                                             base=(self.champ["train"], self.champ["fams"]), seed=seed + 1)
            vr = self.champ["valid"] if np.array_equal(xr, start) else self.fitter.score(muted, xr, "valid")[0]
            ref = {"x": xr, "train": sr, "valid": vr}
        v, vfams = self.fitter.score(feats, x, "valid")
        f.delta_train = round(s - ref["train"], 4)
        f.delta_valid = round(v - ref["valid"], 4)
        return {"feature": f, "x": x, "train": s, "fams": fams, "valid": v, "vfams": vfams}

    # ================================================================ one generation
    def generation(self, gen, pool_ids):
        started = time.time()
        branches = {"full": ["deep", "wide"], "wide-only": ["wide"], "deep-only": ["deep"]}[self.a.mode]
        say(f"\n── generation {gen}: {' + '.join(branches)} | champion {self.champ['id']} train {self.champ['train']:.3f}"
            f" valid {self.champ['valid']:.3f} | {len(self.library)} features, {len(self.champ['x'])} weights")
        self.set_status(generation=gen)
        self.reset_flow(gen, branches)
        if self.library:
            self.set_flow("library", "done", sub=f"{len(self.library)} feature{'s' * (len(self.library) != 1)}",
                          note=f"{len(self.champ['x'])} weights")
        else:
            self.set_flow("library", "done", sub="empty", note="= Code Zero")

        # ---- inspect (--no-inspect: the Researcher gets no packing comparison, as in the program engine)
        comparison = {}
        if self.a.inspect:
            self.set_flow("inspect", "active", note="packing the diagnostic instances")
            try:
                idx = [train_index(i["id"]) for i in diagnostic_instances()]
                comparison = instruments.compare(self.fitter.packings(self.lib(), self.champ["x"], idx))
            except FitError as exc:
                say(f"   inspect failed: {exc}")
        gaps = sorted(((fam, c["champion"]["bins"] - (c["optimum"] or {}).get("bins", c["champion"]["bins"]))
                       for fam, c in comparison.items()), key=lambda kv: -kv[1])
        if self.a.inspect:
            self.set_flow("inspect", "done", sub="extra bins vs optimum",
                          note=", ".join(f"{fam} +{g}" for fam, g in gaps[:2]) or "no comparison")
        context = self.context(gen, comparison)

        # ---- agents (deep and wide at the same time), with fitting starting as soon as it can:
        # the champion refit runs while the agents are still writing, and every candidate is checked
        # and tried the moment it is written, so fitting hides behind the agents' thinking time.
        t_agents = time.time()
        inbox = queue.Queue()
        refit_ev = threading.Event()
        refit_res = {}
        prev = {**self.champ, "features": list(self.library)}
        evals0 = self.fitter.evals
        trials = []
        tried = {"n": 0}

        def refit_worker():
            try:
                refit_res["r"] = self.refit_champion(gen)
            except Exception as exc:
                refit_res["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                refit_ev.set()

        def try_one(f):
            refit_ev.wait()                     # the champion refit comes first, as before
            tried["n"] += 1
            self.set_phase("fit", f"trying {f.id} {f.name} ({tried['n']})")
            if f.status != "invalid" and self.check(f, gen):
                try:
                    t = self.trial(f)
                    trials.append(t)
                    if t.get("early"):
                        say(f"   {f.id} {f.branch:4s} {f.name[:28]:28s} rejected by the probe"
                            f" ({t['train'] - self.champ['train']:+.3f})")
                    else:
                        say(f"   {f.id} {f.branch:4s} {f.name[:28]:28s} train {t['train'] - self.champ['train']:+.3f}"
                            f"  valid {t['valid'] - self.champ['valid']:+.3f}")
                except FitError as exc:
                    f.status, f.error = "invalid", str(exc)[:500]
            if f.status == "invalid":
                say(f"   {f.id} {f.branch:4s} {f.name[:28]:28s} invalid: {short(f.error or '', 90)}")
            self.save_feature(f)
            best = max((t["valid"] - self.champ["valid"] for t in trials if t.get("valid") is not None), default=None)
            self.set_flow("fit", done=tried["n"], note=f"best valid {best:+.3f}" if best is not None else "nothing usable yet")

        overlap = bool(self.a.overlap)
        notify = (lambda f: inbox.put(("cand", f))) if overlap else None
        branch_done_at = {}
        fit_started = None
        if overlap:
            fit_started = time.time()
            threading.Thread(target=refit_worker, name="champion-refit", daemon=True).start()
        self.set_flow("fit", "active", done=0, note="checking features" + (" as they arrive" if overlap else ""))
        with ThreadPoolExecutor(max_workers=2) as both:
            fut = {b: both.submit(getattr(self, b), gen, context, notify) for b in branches}
            for b in branches:
                def _mark(_f, b=b):            # when the branch (its writes) finished
                    branch_done_at[b] = time.time()
                    inbox.put(("done", b))
                fut[b].add_done_callback(_mark)
            if overlap:
                done = 0
                while done < len(branches):
                    kind, value = inbox.get()
                    if kind == "done":
                        done += 1
                    else:
                        try_one(value)
            out = {b: f.result() for b, f in fut.items()}
        if not overlap:
            fit_started = time.time()
            refit_worker()
            for f in [f for f, _ in out.get("deep", [])] + out.get("wide", []):
                try_one(f)
        refit = refit_res.get("r")
        if refit_res.get("error"):
            say(f"   champion refit failed: {short(refit_res['error'], 120)}")
        deep = out.get("deep", [])
        wide = out.get("wide", [])
        candidates = [f for f, _ in deep] + wide
        ideas = {f.id: idea for f, idea in deep}
        t_agents = max(branch_done_at.values()) - t_agents if branch_done_at else time.time() - t_agents

        # ---- fit records (the fits above ran under the agents when overlapping)
        self.set_flow("fit", "done", sub=f"{len(trials)} of {len(candidates)} tried",
                      note=f"{self.fitter.evals - evals0} evaluations")
        self.set_phase("fit", None)

        # ---- accept
        self.set_flow("accept", "active", note="combining")
        base_valid = self.champ["valid"]                 # what the trials were judged against
        accepted, retired = self.accept(trials)
        t_fit = time.time() - fit_started if fit_started else 0.0     # refit + trials + accept

        # ---- records
        champion_prog = self.record_champion(gen, prev, accepted)
        trial_progs = self.record_trials(gen, prev, trials, candidates, accepted)
        self.record_hypotheses(gen, prev, base_valid, deep, ideas, trial_progs, accepted)
        for f in candidates:
            if f.status == "candidate":
                f.status = "rejected"
            self.save_feature(f)
        for fid in retired + [f.id for f in accepted]:
            self.save_feature(self.features[fid])
        self.set_flow("accept", "done", sub=f"champion {self.champ['id']}",
                      note=(f"kept {len(accepted)}" if accepted else "nothing kept") + (f", retired {len(retired)}" if retired else ""))

        record = {"generation": gen, "branches": branches + ["fit"], "pool": [self.champ["id"]],
                  "best_id": self.champ["id"], "best_score": self.champ["train"], "valid_score": self.champ["valid"],
                  "seconds": round(time.time() - started, 1), "started_at": round(started, 1),
                  "finished_at": round(time.time(), 1), "llm": self.llm.summary(),
                  "phase_seconds": {"agents": round(t_agents, 1), "fit": round(t_fit, 1), "overlap": overlap},
                  "accepted": [f.id for f in accepted], "retired": retired, "champion_refit": refit,
                  "fit": {"trials": len(trials), "evals": self.fitter.evals - evals0, "candidates": len(candidates),
                          "invalid": sum(f.status == "invalid" for f in candidates)},
                  "library": [{"id": f.id, "name": f.name, "branch": f.branch, "columns": f.columns,
                               "weights": [round(w, 4) for w in f.weights], "importance": f.importance}
                              for f in self.lib()],
                  "diagnostics": comparison,
                  "champion": {"id": self.champ["id"], "features": list(self.library), "x": [float(v) for v in self.champ["x"]],
                               "train": self.champ["train"], "valid": self.champ["valid"], "fams": self.champ["fams"],
                               "vfams": self.champ["vfams"], "official": self.champ.get("official"),
                               "official_fams": self.champ.get("official_fams")}}
        for b in branches:
            mine = [t for t in trials if t["feature"].branch == b]
            fs = [f for f in candidates if f.branch == b]
            verdicts = {}
            for f in fs:
                v = self.verdict(f, accepted)
                verdicts[v] = verdicts.get(v, 0) + 1
            record[b] = {"new": len(fs), "valid": len(mine), "best_new": max((t["train"] for t in mine), default=None),
                         "tested": len(fs), **verdicts}
        self.store.log_generation(record)
        say(f"   kept {', '.join(f'{f.id} ({f.branch}) {f.name}' for f in accepted) or 'nothing'}"
            + (f"; retired {', '.join(retired)}" if retired else ""))
        say(f"   champion {self.champ['id']}: train {self.champ['train']:.3f}, valid {self.champ['valid']:.3f} | "
            f"{record['llm']['calls']} LLM calls | {record['seconds']}s (agents {t_agents:.0f}s, fit {t_fit:.0f}s)")
        return [self.champ["id"]]

    def refit_champion(self, gen):
        """Refit the champion's own weights (no new feature) before any feature is tried. If that improves it
        on train and validation it becomes the champion, credited to fitting; the features are then tried on
        top of it, so no feature is credited with what fitting alone finds."""
        budget = self.a.champion_refit_evals
        if budget <= 0 or not len(self.champ["x"]):
            return None
        self.set_phase("fit", "refitting the champion's weights")
        self.set_flow("fit", "active", note="refitting the champion")
        try:
            x, s, fams = self.fitter.optimise(self.lib(), self.champ["x"], budget, sigma=self.a.refit_sigma,
                                              base=(self.champ["train"], self.champ["fams"]), seed=10_000 + gen)
            if s <= self.champ["train"]:
                return {"train": round(s, 4), "valid": None, "kept": False}
            v, vfams = self.fitter.score(self.lib(), x, "valid")
        except FitError as exc:
            say(f"   champion refit failed: {short(str(exc), 90)}")
            return None
        kept = v > self.champ["valid"]
        if kept:
            say(f"   champion refit (no new feature): train {s - self.champ['train']:+.3f}, valid {v - self.champ['valid']:+.3f}")
            self.champ.update(x=np.asarray(x, dtype=float), train=s, fams=fams, valid=v, vfams=vfams)
        return {"train": round(s, 4), "valid": round(v, 4), "kept": kept}

    def verdict(self, f, accepted):
        if f.status == "invalid":
            return "invalid"
        if f in accepted:
            return "supported"
        if f.status == "redundant":
            return "redundant"
        if f.delta_valid is not None and f.delta_valid < -self.a.accept_margin:
            return "refuted"
        if f.delta_valid is None and (f.delta_train or 0) < -self.a.accept_margin:
            return "refuted"          # rejected by the cheap probe: worse than the champion at every weight tried
        return "flat"

    def accept(self, trials):
        """Combine the features that helped on validation (greedily, best first), refit them together, and
        retire features that hurt."""
        margin = self.a.accept_margin
        good = sorted([t for t in trials if t.get("valid") is not None and t["feature"].delta_valid > margin
                       and (t["feature"].delta_train or 0) > 0], key=lambda t: -t["feature"].delta_valid)
        accepted = []
        if good:
            # Greedy, so the result is never worse than the best single feature: start from the best one, add
            # each other one (with the weights from its own trial, or half of them, since features overlap)
            # only if validation improves again, then refit everything together.
            self.set_phase("fit", f"combining {len(good)} good feature(s)")
            first = good[0]
            chosen, feats = [first], self.lib() + [first["feature"]]
            x, s, fams, v, vfams = first["x"], first["train"], first["fams"], first["valid"], first["vfams"]
            for t in good[1:][: max(1, int(getattr(self.a, "max_combine", 99)) - 1)]:
                f = t["feature"]
                w = np.asarray(t["x"][-f.width:], dtype=float)
                X = [np.concatenate([x, k * w]) for k in (1.0, 0.5)]
                try:
                    tries = [(vt, vft, xt) for xt, (vt, vft) in zip(X, self.fitter.evaluate(feats + [f], X, "valid"))
                             if vt is not None]
                    vt, vft, xt = max(tries, key=lambda r: r[0]) if tries else (None, None, None)
                    if (vt is None or vt <= v + margin / 2) and getattr(self.a, "combine_refit", 0) > 0:
                        # close call: give the candidate's weights a small refit together with the kept set
                        # (its solo weights were fitted against an older champion and can be badly scaled here)
                        x0 = np.concatenate([np.asarray(x), np.asarray(w)])
                        xo, so, fo = self.fitter.optimise(feats + [f], x0, self.a.combine_refit,
                                                          sigma=self.a.refit_sigma)
                        vo, vfo = self.fitter.score(feats + [f], xo, "valid")
                        if vo is not None and (vt is None or vo > vt):
                            vt, vft, xt = vo, vfo, xo
                    if vt is None or vt <= v + margin / 2:
                        continue
                    st, fst = self.fitter.score(feats + [f], xt, "train")
                except FitError as exc:
                    say(f"   combining {f.id} failed: {short(str(exc), 90)}")
                    continue
                if st >= s - margin:                       # don't trade train away for validation
                    chosen.append(t)
                    feats, x, s, fams, v, vfams = feats + [f], xt, st, fst, vt, vft
            for t in good:
                if t not in chosen:
                    t["feature"].status = "redundant"   # helped alone, added nothing on top of the ones kept
            if len(good) > 1:
                say(f"   combined {len(chosen)} of {len(good)} good features: train {s:.3f}, valid {v:.3f}")
            if self.a.refit_evals > 0:
                self.set_phase("fit", f"joint refit with {len(chosen)} new feature(s)")
                try:
                    xr, sr, fr = self.fitter.optimise(feats, x, self.a.refit_evals, sigma=self.a.refit_sigma, base=(s, fams))
                    vr, vfr = self.fitter.score(feats, xr, "valid")
                    if sr > s and vr >= v:
                        x, s, fams, v, vfams = xr, sr, fr, vr, vfr
                    elif sr > s:
                        say(f"   joint refit gained on train ({sr:.3f}) but not on validation ({vr:.3f}); not used")
                except FitError as exc:
                    say(f"   joint refit failed ({short(str(exc), 90)}); keeping the combined weights")
            for t in chosen:
                t["feature"].status = "active"
                accepted.append(t["feature"])
            self.library += [t["feature"].id for t in chosen]
            self.champ.update(x=np.asarray(x, dtype=float), train=s, fams=fams, valid=v, vfams=vfams)
            self.base_seconds = None
        # ---- second chance: near-miss features, tried once more next to what was kept. A feature can pay
        # off only next to another one; its solo trial had to rescue it on its own, so a feature that came
        # close is retried together with the kept set (both sets of weights refitted).
        n_combo = int(getattr(self.a, "combo", 0) or 0)
        cap = int(getattr(self.a, "gen_eval_cap", 0) or 0)
        spent = self.fitter.evals - evals0
        if n_combo > 0 and (cap <= 0 or spent < cap):
            near = [t for t in trials if t.get("valid") is not None and t["feature"] not in accepted
                    and t["feature"].status not in ("invalid", "redundant")
                    and t["feature"].delta_valid > -margin]
            near.sort(key=lambda t: -t["feature"].delta_valid)
            for t in near[:n_combo]:
                f = t["feature"]
                feats2 = self.lib() + [f]
                x2 = np.concatenate([self.champ["x"], np.full(f.width, 0.5)])
                try:
                    self.set_phase("fit", f"second chance: {f.id} next to the kept features")
                    xr, sr, fr = self.fitter.optimise(feats2, x2, self.a.combo_evals, sigma=self.a.refit_sigma)
                    vr, vfr = self.fitter.score(feats2, xr, "valid")
                except FitError as exc:
                    say(f"   second chance for {f.id} failed: {short(str(exc), 90)}")
                    continue
                if sr >= self.champ["train"] and vr >= self.champ["valid"] + margin / 2:
                    old_train, old_valid = self.champ["train"], self.champ["valid"]
                    f.status = "active"
                    accepted.append(f)
                    self.library.append(f.id)
                    self.champ.update(x=np.asarray(xr, dtype=float), train=sr, fams=fr, valid=vr, vfams=vfr)
                    self.base_seconds = None
                    say(f"   second chance: {f.id} {f.name} works next to the kept features "
                        f"(train {sr - old_train:+.3f}, valid {vr - old_valid:+.3f})")
        # ---- backlog retry: near-miss features from past generations, re-fitted against the current
        # champion. A feature that lost against an older champion can win against a newer one.
        n_revisit = int(getattr(self.a, "revisit", 0) or 0)
        spent = self.fitter.evals - evals0
        if n_revisit > 0 and (cap <= 0 or spent < cap):
            g = self.flow_generation or 0
            backlog = [f for f in self.features.values()
                       if f.branch != "seed" and f.status in ("rejected", "redundant") and f.id not in self.library
                       and f.delta_valid is not None and f.delta_valid > -margin and g not in (f.revisited_at or [])]
            backlog.sort(key=lambda f: -(f.delta_valid or -1))
            for f in backlog[:n_revisit]:
                f.revisited_at = (f.revisited_at or []) + [g]
                feats2 = self.lib() + [f]
                x2 = np.concatenate([self.champ["x"], np.zeros(f.width)])
                try:
                    self.set_phase("fit", f"revisiting {f.id} {f.name} against the current champion")
                    xr, sr, fr = self.fitter.optimise(feats2, x2, self.a.combo_evals, sigma=self.a.refit_sigma)
                    vr, vfr = self.fitter.score(feats2, xr, "valid")
                except FitError as exc:
                    say(f"   revisit of {f.id} failed: {short(str(exc), 90)}")
                    self.save_feature(f)
                    continue
                if sr >= self.champ["train"] and vr >= self.champ["valid"] + margin / 2:
                    old_train, old_valid = self.champ["train"], self.champ["valid"]
                    f.status = "active"
                    accepted.append(f)
                    self.library.append(f.id)
                    self.champ.update(x=np.asarray(xr, dtype=float), train=sr, fams=fr, valid=vr, vfams=vfr)
                    self.base_seconds = None
                    say(f"   revisit: {f.id} {f.name} now works on top of the champion "
                        f"(train {sr - old_train:+.3f}, valid {vr - old_valid:+.3f})")
                self.save_feature(f)
        self.set_phase("fit", None)
        # importance on validation; retire non-seed features that hurt (checked when the library changed,
        # and every third generation)
        retired = []
        if not accepted and (self.flow_generation or 0) % 3 and all(f.importance is not None for f in self.lib()):
            for f, w in zip(self.lib(), split_vector(self.lib(), self.champ["x"])):
                f.weights = w
            return accepted, retired
        try:
            imp = self.fitter.importance(self.lib(), self.champ["x"], "valid", base=self.champ["valid"])
            k = 0
            for f in self.lib():
                f.importance = [round(v, 4) for v in imp[k:k + f.width]]
                k += f.width
            hurt = [f for f in self.lib() if f.branch != "seed" and sum(f.importance or [0]) < -margin]
            over = len(self.champ["x"]) - self.a.max_columns
            if over > 0:
                spare = sorted((f for f in self.lib() if f.branch != "seed" and f not in hurt),
                               key=lambda f: sum(f.importance or [0]))
                for f in spare:
                    if over <= 0:
                        break
                    hurt.append(f)
                    over -= f.width
            if hurt:
                keep = [f for f in self.lib() if f not in hurt]
                xs = split_vector(self.lib(), self.champ["x"])
                x = np.concatenate([np.asarray(w) for f, w in zip(self.lib(), xs) if f not in hurt]) if keep else np.zeros(0)
                s, fams = self.fitter.score(keep, x, "train")
                v, vfams = self.fitter.score(keep, x, "valid")
                # Retire only when removing the hurt features is not a trade: validation must not drop,
                # and train must not be sacrificed beyond a quarter of the validation gain (a tiny train
                # cost for a big validation win is worth it; the other way around made champions worse).
                allowed_train_cost = max(1e-4, 0.25 * max(0.0, v - self.champ["valid"]))
                if v >= self.champ["valid"] - 1e-9 and s >= self.champ["train"] - allowed_train_cost:
                    for f in hurt:
                        f.status = "retired"
                        retired.append(f.id)
                    self.library = [f.id for f in keep]
                    self.champ.update(x=x, train=s, fams=fams, valid=v, vfams=vfams)
                    self.base_seconds = None
                elif v >= self.champ["valid"] - 1e-9:
                    say(f"   would retire {', '.join(f.id for f in hurt)} (validation {v - self.champ['valid']:+.3f}) "
                        f"but it costs train ({s - self.champ['train']:+.3f}); keeping them")
        except FitError as exc:
            say(f"   importance check failed: {exc}")
        for f, w in zip(self.lib(), split_vector(self.lib(), self.champ["x"])):
            f.weights = w
        return accepted, retired

    # ================================================================ records the rest of Helix reads
    def compose_champion(self, title):
        return compose(self.lib(), split_vector(self.lib(), self.champ["x"]), title=title)

    def record_champion(self, gen, prev, accepted, note=None):
        """A new Program for the champion when it changed, scored by the evaluator itself."""
        if prev.get("id") and prev["train"] == self.champ["train"] and prev["valid"] == self.champ["valid"]:
            return None
        pid = self.store.new_id("p")
        code = self.compose_champion(f"{pid}, generation {gen}, {len(self.library)} features")
        path = self.store.candidate_path(pid)
        path.write_text(code)
        official = evaluate_file(path, "train", self.a.eval_timeout)
        branch = accepted[0].branch if accepted else "fit"
        prog = Program(id=pid, code=code, generation=gen, branch=branch, parent_id=prev.get("id"),
                       valid=bool(official.get("valid")), score=official.get("score"),
                       families={f: v["excess_pct"] for f, v in official.get("families", {}).items()},
                       error=official.get("error"), valid_score=self.champ["valid"], features=list(self.library),
                       note=(note or (f"added {', '.join(f'{f.id} {f.name}' for f in accepted)}" if accepted
                                      else "weights refitted")) + f"; validation {self.champ['valid']:.3f}")
        if prog.valid and self.fitter.fit_split == "train" and abs(prog.score - self.champ["train"]) > 1e-3:
            say(f"   note: the evaluator scores {pid} {prog.score:.4f}, the fitter {self.champ['train']:.4f}")
        if prog.valid and self.fitter.fit_split == "train":
            self.champ["train"], self.champ["fams"] = prog.score, prog.families
        elif prog.valid:
            # searches run on the fit subset; keep the champion's fit-set score consistent with the refits,
            # while the record (prog.score) carries the official full-train score
            self.champ["official"] = prog.score
            self.champ["official_fams"] = prog.families
        self.store.add_program(prog)
        self.champ["id"] = pid
        return prog

    def record_trials(self, gen, prev, trials, candidates, accepted):
        """Every candidate as a Program (the champion's features plus it, refitted), so the dashboard, the
        report and analyze can show what each one did."""
        out = {}
        by_feature = {t["feature"].id: t for t in trials}
        for f in candidates:
            t = by_feature.get(f.id)
            pid = self.store.new_id("p")
            if t and t.get("valid") is not None:
                feats = [self.features[i] for i in prev_ids(prev, self.library, f.id)] + [f]
                code = compose(feats, split_vector(feats, t["x"]), title=f"trial of {f.id} {f.name}")
                self.store.candidate_path(pid).write_text(code)
                prog = Program(id=pid, code=code, generation=gen, branch=f.branch, parent_id=prev.get("id"), trial=True,
                               hypothesis_id=f.hypothesis_id, valid=True, score=round(t["train"], 4), families=t["fams"],
                               valid_score=round(t["valid"], 4), features=[x.id for x in feats],
                               note=f"+ {f.id} {f.name}: train {f.delta_train:+.3f}, validation {f.delta_valid:+.3f}"
                                    + (" (kept)" if f in accepted else ""))
            else:
                prog = Program(id=pid, code=f.code, generation=gen, branch=f.branch, parent_id=prev.get("id"), trial=True,
                               hypothesis_id=f.hypothesis_id, valid=False, error=f.error,
                               note=f"{f.id} {f.name}: invalid")
            self.store.add_program(prog)
            out[f.id] = prog
        return out

    def record_hypotheses(self, gen, prev, base_valid, deep, ideas, progs, accepted):
        for f, idea in deep:
            prog = progs.get(f.id)
            h = Hypothesis(id=idea["hid"], generation=gen, base_id=prev.get("id"), claim=idea["claim"],
                           change=idea["feature"], prediction=idea.get("target", ""), kind="feature",
                           builds_on=idea.get("builds_on", ""), program_id=prog.id if prog else None,
                           base_score=round(base_valid, 4), feature_id=f.id,
                           new_score=None if f.delta_valid is None else round(base_valid + f.delta_valid, 4),
                           delta=f.delta_valid, verdict=self.verdict(f, accepted))
            self.store.add_hypothesis(h)

    # ================================================================ what the agents see
    def context(self, gen, comparison):
        champ = self.champ
        cz = next((p for p in self.store.programs.values() if p.branch == "seed"), None)
        progress = metrics.progress(champ.get("official_fams") or champ["fams"], cz.families) if cz and champ["fams"] else None
        lib_lines, existing, targets = [], [], []
        for f in self.lib():
            imp = f.importance or [None] * f.width
            lib_lines.append(f"- {f.id} {f.name} ({f.branch}, generation {f.generation}): {' '.join(f.description.split())[:160]}")
            cols = sorted(zip(f.columns, f.weights, imp), key=lambda c: -abs(c[2] or 0))
            shown = [c for c in cols if c[2] is None or abs(c[2]) >= 0.005][:12]
            for col, w, im in shown:
                lib_lines.append(f"    {col}: weight {w:+.2f}" + (f", importance {im:+.3f}" if im is not None else ""))
            if len(cols) > len(shown):
                lib_lines.append(f"    ({len(cols) - len(shown)} more values with importance under 0.005)")
            existing.append(f"- {f.name}: {' '.join(f.description.split())[:200]}")
            for col, w, im in cols[:3]:
                targets.append(f"_{f.id} ({col if f.width > 1 else f.name})")
        if not self.library:
            lib_lines = ["(no features yet: every bin scores 0, so each job goes into the oldest bin it fits; "
                         "this is Code Zero)"]
            existing = ["(none yet)"]
        floor = family_floor("train")
        room = [f"- {fam}: {champ['fams'].get(fam, 0):.2f} / {floor[fam]['lower']:.2f} / room {champ['fams'].get(fam, 0) - floor[fam]['lower']:.2f}"
                for fam in sorted(floor, key=lambda k: -(champ["fams"].get(k, 0) - floor[k]["lower"]))] if floor and champ["fams"] else []
        log = []
        for h in [h for h in self.store.hypotheses if h.kind == "feature"][-20:]:
            note = " — no weight changed the score; change the form of the measurement, not its scale" if h.delta == 0.0 else ""
            log.append(f"- {h.id} gen {h.generation} [{h.verdict}{note}{f', validation {h.delta:+.3f}' if h.delta not in (None, 0.0) else ''}] "
                       f"feature: {short(h.change, 160)} | claim: {short(h.claim, 140)}")
        for f in [f for f in self.features.values() if f.branch == "wide" and f.status in ("active", "retired")][-6:]:
            log.append(f"- {f.id} (from the Mutator) {f.name}: {f.status}, validation {f.delta_valid:+.3f}: {short(f.description, 120)}")
        champ_prog = self.store.programs.get(champ["id"])
        last_gain = champ_prog.generation if champ_prog else gen
        return {"champion": {"id": champ["id"], "train": champ["train"], "valid": champ["valid"]},
                "progress": progress, "library_lines": lib_lines, "existing_lines": existing,
                "room_lines": room, "log_lines": log,
                "packings": instruments.text(comparison) if self.a.inspect else "(switched off for this run)",
                "mutation_targets": targets, "champion_code": self.compose_champion(champ["id"]),
                "stuck": max(0, gen - 1 - last_gain)}

    # ================================================================ generation 0
    def seed(self):
        """Generation 0 is Code Zero and nothing else: the library starts empty. An empty policy scores every
        bin 0, so the simulator picks the oldest bin that fits, which is exactly what Code Zero does. No agent
        is called and nothing is fitted; every gain after this is the search's own."""
        seed_path = self.a.seed_program
        result = evaluate_file(seed_path, "train", self.a.eval_timeout)
        if not result["valid"]:
            raise SystemExit(f"Code Zero ({seed_path}) is invalid:\n{result['error']}")
        self.reset_flow(0, [])
        code = open(seed_path).read()
        p = Program(id=self.store.new_id("p"), code=code, generation=0, branch="seed", valid=True, score=result["score"],
                    families={f: v["excess_pct"] for f, v in result["families"].items()}, note=f"Code Zero from {seed_path}",
                    features=[])
        self.store.candidate_path(p.id).write_text(code)
        self.store.add_program(p)
        say(f"── generation 0: Code Zero scores {p.score:.3f} ({p.id}); the library starts empty")
        self.set_flow("library", "active", note="scoring Code Zero on validation")
        empty_train, _ = self.fitter.score([], np.zeros(0), "train")   # full split: the Code Zero check
        if abs(empty_train - p.score) > 1e-3:              # the empty policy must be Code Zero, exactly
            raise SystemExit(f"the empty feature policy scores {empty_train:.4f} but Code Zero scores {p.score:.4f}; "
                             "the feature engine starts from Code Zero only when they are the same policy")
        fit_train, fit_fams = self.fitter.score([], np.zeros(0), self.fitter.fit_split)
        v0, vf0 = self.fitter.score([], np.zeros(0), "valid")
        self.champ = {"id": p.id, "x": np.zeros(0), "train": fit_train, "fams": fit_fams, "valid": v0, "vfams": vf0}
        self.set_flow("library", "done", sub="empty", note="= Code Zero")
        self.set_flow("accept", "done", sub=f"champion {p.id}", note="Code Zero")
        self.store.log_generation({"generation": 0, "branches": ["seed"], "pool": [p.id], "best_id": p.id,
                                   "best_score": p.score, "valid_score": v0, "llm": self.llm.summary(),
                                   "started_at": round(self.status["started"], 1), "finished_at": round(time.time(), 1),
                                   "library": [],
                                   "champion": {"id": p.id, "features": [], "x": [], "train": p.score, "valid": v0,
                                                "fams": p.families, "vfams": vf0}})
        return [p.id]

    def finish(self):
        self.fitter.close()
        super().finish()
        kept = [f for f in self.features.values() if f.status == "active" and f.branch != "seed"]
        say(f"features kept: {len(kept)} ({', '.join(f'{f.id} {f.name} ({f.branch})' for f in kept) or 'none'}); "
            f"tried: {sum(f.branch != 'seed' for f in self.features.values())}")


def prev_ids(prev, library, exclude):
    """The library as it was before this generation's additions (the trial was run on that)."""
    return [i for i in (prev.get("features") or library) if i != exclude]
