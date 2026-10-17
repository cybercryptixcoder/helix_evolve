"""Helix v3: the generation loop. See docs/V3_DESIGN.md.

One generation:
  1. sample decision states from the champion's own solutions (for fingerprints)
  2. diagnose the champion next to the reference; sensitivity probes on every kept feature
  3. Navigator plans (or the strategy's hooks.allocate): approaches, Researcher assignments, Mutator parents
  4. deep (Researcher -> Coders) and wide (Mutator) run at the same time; the champion's weights are refitted
  5. novelty: duplicates / inert / span features are certified and not evaluated (wide gets one retry)
  6. Fit: probe -> trial (with vs without) -> prediction checks; combinations of near-misses
  7. Accept (greedy), retire, update the approach tree, record everything in trace.jsonl
"""
from __future__ import annotations

import importlib.util
import json
import queue
import os
import random
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import roles
from .fitter import Fitter
from .ledger import Feature, Ledger
from .policy import FeatureError, call_feature, compile_feature, compose, docstring, extract_code, make_priority

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STRATEGY = Path(__file__).resolve().parent / "strategy"


def say(*a):
    print(*a, flush=True)


# ====================================================================== strategy
class Strategy:
    """The evolvable part: config.json, prompts/*.md, hooks.py, from one folder."""

    def __init__(self, path=None):
        self.path = Path(path or DEFAULT_STRATEGY)
        self.config = json.loads((self.path / "config.json").read_text())
        self.prompts = {p.stem: p.read_text() for p in (self.path / "prompts").glob("*.md")}
        # domain addenda: prompts/<space>/<role>.md (what a candidate is at this level)
        self.addenda = {d.name: {p.stem: p.read_text() for p in d.glob("*.md")}
                        for d in (self.path / "prompts").iterdir() if d.is_dir()}
        spec = importlib.util.spec_from_file_location(f"strategy_hooks_{abs(hash(str(self.path)))}", self.path / "hooks.py")
        self.hooks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hooks)

    def c(self, *keys, default=None):
        v = self.config
        for k in keys:
            if not isinstance(v, dict) or k not in v:
                return default
            v = v[k]
        return v


# ====================================================================== trace
class Trace:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._n = 0
        if Path(path).exists():                 # resuming: keep numbering calls where the trace left off
            with open(path) as fh:
                self._n = sum(1 for line in fh if '"type": "call"' in line)
        self.f = open(path, "a")

    def emit(self, _type, **data):
        with self._lock:
            rec = {"t": round(time.time(), 3), "type": _type, **data}
            self.f.write(json.dumps(rec, default=_jsonable) + "\n")
            self.f.flush()
            return rec

    def call_id(self):
        with self._lock:
            self._n += 1
            return f"c{self._n:03d}"

    def close(self):
        self.f.close()


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


# ====================================================================== engine
class Engine:
    def __init__(self, problem, run_dir, llm, strategy=None, workers=None, seed=0, label=""):
        self.p = problem
        self.s = strategy or Strategy()
        self.cfg = self.s.config
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        if Path(self.s.path).resolve() != (self.dir / "strategy").resolve():
            shutil.copytree(self.s.path, self.dir / "strategy", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.trace = Trace(self.dir / "trace.jsonl")
        self.llm = llm
        self.llm.on_call = self._on_call
        self._meta = threading.local()
        self.fit = Fitter(problem, workers)
        nov = self.cfg.get("novelty", {})
        self.ledger = Ledger(nov.get("duplicate_rho", 0.98), nov.get("span_r2", 0.995))
        self.rng = random.Random(seed)
        self.seed = seed
        self.label = label
        self.gen = 0
        self.x = np.zeros(0)                         # champion's scaled weights over the library's columns
        self.champ = {}
        self.history = []
        self.margin = self.s.c("fit", "accept_margin", default=0.03)
        self.spread, self.xscale = 1.0, 1.0
        self._sens_key, self._sens = None, []
        self.S = getattr(problem, "search_split", "train")      # the instances searches and refits run on
        self.P = getattr(problem, "probe_split", None) or self.S  # the probe's quick first pass (can be smaller)
        self.workers = ThreadPoolExecutor(12)
        self.status = {"phase": "starting"}
        self._cert_lock = threading.Lock()

    # ------------------------------------------------------------------ plumbing
    def _on_call(self, rec):
        meta = getattr(self._meta, "m", {}) or {}
        cid = self.trace.call_id()
        rec = {**rec, "id": cid, "gen": self.gen, **meta}
        self.trace.emit("call", **rec)
        f = self.ledger.features.get(meta.get("feature") or "")
        if f is not None:
            f.calls.append(cid)

    def effort(self, cfg_key):
        """The thinking level for a role this generation: its configured level, or the breakthrough level on
        every Nth generation for the roles listed under config.breakthrough."""
        c = self.cfg.get(cfg_key, {})
        b = self.cfg.get("breakthrough") or {}
        if b.get("every") and self.gen and self.gen % int(b["every"]) == 0 and cfg_key in b.get("roles", []):
            return b.get("effort", "max")
        return c.get("effort", "none")

    def ask(self, role, system, user, cfg_key, meta=None, json_reply=False):
        """One model call. A reply that is a JSON plan is asked for differently depending on thinking:
        with thinking on, the model already reasons before answering, so it answers JSON first with a short
        summary after; with thinking off, it is asked to write its reasoning before the JSON (its chain of thought)."""
        c = self.cfg.get(cfg_key, {})
        effort = self.effort(cfg_key)
        if json_reply and effort == "none":
            user += ("\n\n(No hidden thinking for this reply.) Think first: write your reasoning in at most 200 words "
                     "under a line `Reasoning:`, then the ```json block, then nothing else.")
        max_tokens = c.get("max_tokens", 4000) * (2 if effort in ("high", "xhigh", "max", "ultra") else 1)
        self._meta.m = {**(meta or {}), "effort": effort}
        try:
            return self.llm.chat(role, system, user, temperature=c.get("temperature", 0.6),
                                 max_tokens=max_tokens, effort=effort, meta={"role_key": cfg_key})
        finally:
            self._meta.m = {}

    def phase(self, name, note=""):
        self.status = {"phase": name, "note": note, "gen": self.gen, "t": time.time()}
        (self.dir / "status.json").write_text(json.dumps({**self.status, "state": "running", "label": self.label,
                                                          "pid": os.getpid(), "target": getattr(self, "target", None)}))
        say(f"   [{name}] {note}")

    # ------------------------------------------------------------------ policy helpers
    def unpack(self, feats, x):
        out, i = [], 0
        for f in feats:
            out.append([float(v) * s for v, s in zip(x[i:i + f.width], f.scales)])
            i += f.width
        return out

    def evaluate(self, feats, xs, split="train"):
        return self.fit.evaluate([f.code for f in feats], [self.unpack(feats, x) for x in xs], split)

    def priority(self, feats, x):
        return make_priority([f.code for f in feats], self.unpack(feats, x), self.p.n_candidates)

    def waste(self, fams, split):
        if not fams:
            return None
        return float(np.mean([fams[f] - self.p.floor(f, split) if _takes_split(self.p.floor) else fams[f] - self.p.floor(f)
                              for f in fams]))

    def progress(self, fams, split="train"):
        w, w0 = self.waste(fams, split), self.waste(self.cz.get(split), split)
        if w is None or not w0 or w0 <= 0:
            return None
        return round(100 * (1 - w / w0), 2)

    # ------------------------------------------------------------------ setup
    def start(self):
        self.phase("setup", "scoring Code Zero")
        res = self.fit.evaluate([], [[]], "train")[0], self.fit.evaluate([], [[]], "valid")[0]
        self.cz = {"train": res[0][1], "valid": res[1][1]}
        self.cz_gap = {"train": res[0][0], "valid": res[1][0]}
        self.champ = {"train": res[0][0], "valid": res[1][0], "families": res[0][1], "valid_families": res[1][1],
                      "progress": 0.0, "valid_progress": 0.0,
                      "search": res[0][0] if self.S == "train" else self.fit.evaluate([], [[]], self.S)[0][0]}
        self.ref_diag = {}
        for iid in self.p.diagnostic_ids():
            try:
                self.ref_diag[iid] = self.p.reference_metrics(self.p.instance("train", iid))
            except Exception:
                self.ref_diag[iid] = {}
        self.trace.emit("run_start", problem=self.p.name, title=self.p.title, label=self.label,
                        config=self.cfg, code_zero=self.cz_gap, code_zero_families=self.cz,
                        floors={f: (self.p.floor(f, "train") if _takes_split(self.p.floor) else self.p.floor(f))
                                for f in self.p.families},
                        description=self.p.description, signature=self.p.signature,
                        metric_notes=self.p.metric_notes)
        self.history.append(self._gen_record(0, [], {}, 0.0))
        self.trace.emit("gen_end", **self.history[-1])
        say(f"── generation 0: Code Zero, gap {self.cz_gap['train']:.3f}% train, {self.cz_gap['valid']:.3f}% valid")

    def sample_states(self):
        """Decision states from the champion's own solutions on the diagnostic instances (+ Code Zero's)."""
        n_target = self.s.c("novelty", "states", default=500)
        recorded = []

        def recorder(inner):
            def pr(*args):
                recorded.append(tuple(a.copy() if hasattr(a, "copy") else a for a in args))
                return inner(*args)
            return pr

        lib = self.ledger.lib()
        for iid in self.p.diagnostic_ids():
            inst = self.p.instance("train", iid)
            for feats, x in ((lib, self.x), ([], np.zeros(0))):
                try:
                    self.p.run(inst, recorder(self.priority(feats, x)))
                except Exception:
                    pass
                if not lib:
                    break
        rng = np.random.default_rng(self.seed + self.gen)
        if len(recorded) > n_target:
            idx = rng.choice(len(recorded), n_target, replace=False)
            recorded = [recorded[i] for i in sorted(idx)]
        self.ledger.set_states(recorded, self.p.n_candidates, seed=self.seed + self.gen)
        # how strongly the champion separates candidates within a decision: probes and steps are relative to it
        self.spread, self.xscale = 1.0, 1.0
        if lib:
            pr = self.priority(lib, self.x)
            sds = []
            for a in self.ledger.states[:300]:
                try:
                    v = np.asarray(pr(*a), dtype=float)
                    if len(v) > 1:
                        sds.append(float(np.std(v)))
                except Exception:
                    pass
            if sds:
                self.spread = max(1e-4, float(np.median(sds)))
            self.xscale = max(0.02, float(np.median(np.abs(self.x)))) if len(self.x) else 1.0
        self.trace.emit("spread", gen=self.gen, spread=self.spread, xscale=self.xscale)

    # ------------------------------------------------------------------ one feature: check, scale, certify
    def check(self, f):
        """Compiles, returns the right shape, finite, fast enough. Sets width and scales."""
        try:
            fn = compile_feature(f.code)
            st = self.ledger.states[:60] or []
            t = time.time()
            vals = [call_feature(fn, a, self.p.n_candidates(a)) for a in st]
            per_call = (time.time() - t) / max(1, len(st))
            if per_call > 0.004:
                raise FeatureError(f"too slow: {per_call * 1000:.1f} ms per decision; vectorise it")
            widths = {v.shape[1] for v in vals}
            if len(widths) > 1:
                raise FeatureError(f"returns a different number of columns in different decisions: {sorted(widths)}")
            f.width = min(4, widths.pop() if widths else 1)
            cols = [np.concatenate([v[:, j] - v[:, j].mean() for v in vals]) for j in range(f.width)] if vals else []
            f.scales = [1.0 / s if s > 1e-9 else 1.0 for s in (float(np.std(c)) if len(c) else 0.0 for c in cols)] or [1.0]
            f.weights = [0.0] * f.width
            f.measures = f.measures or docstring(f.code)
            f.error = ""
            return True
        except Exception as exc:
            f.error = str(exc)[:400]
            return False

    def certify(self, f):
        try:
            cert = self.ledger.certify(f, self.p.n_candidates)
        except Exception as exc:
            cert = {"error": str(exc)[:200]}
        f.certificate = cert
        t = cert.get("type")
        if t in ("inert", "duplicate", "span"):
            f.status = t
            f.duplicate_of = cert.get("of", "") if t == "duplicate" else ""
            f.verdict = t
            src = self.ledger.features.get(f.duplicate_of)
            if src is not None:                  # inherit the result of the feature it repeats
                f.best_probe, f.d_valid, f.d_train = src.best_probe, src.d_valid, src.d_train
        return cert

    # ------------------------------------------------------------------ diagnostics and sensitivity
    def diagnose(self, feats, x, ids=None):
        out = {}
        pr = self.priority(feats, x)
        for iid in ids or self.p.diagnostic_ids():
            try:
                out[iid] = self.p.diagnose(self.p.instance("train", iid), pr)
            except Exception as exc:
                out[iid] = {"error": str(exc)[:200]}
        return out

    def sensitivity(self):
        lib = self.ledger.lib()
        mults = self.s.c("fit", "sensitivity", default=[0, 0.5, 2, 4])
        if not lib:
            return []
        key = (tuple(self.ledger.library), tuple(np.round(self.x, 6)))
        if key == self._sens_key:
            self.trace.emit("sensitivity", gen=self.gen, rows=self._sens, cached=True)
            return self._sens
        xs, keys, i = [], [], 0
        for f in lib:
            for m in mults:
                x = self.x.copy()
                x[i:i + f.width] *= m
                xs.append(x)
                keys.append((f.id, m))
            i += f.width
        res = self.evaluate(lib, xs, self.S)
        rows = {}
        for (fid, m), (s, _, _) in zip(keys, res):
            rows.setdefault(fid, {})[m] = None if s is None else round(self.champ["search"] - s, 4)
        out = [{"feature": fid, "name": self.ledger.features[fid].name, "deltas": d} for fid, d in rows.items()]
        self.trace.emit("sensitivity", gen=self.gen, rows=out)
        self._sens_key, self._sens = key, out
        return out

    # ------------------------------------------------------------------ the generation
    def run(self, generations, resume=False):
        """Run to `generations`. With resume=True, continue from the last checkpoint (written after every
        generation, atomically), so a run killed by an interruption loses at most the generation in flight."""
        self.target = generations
        if resume and self.restore():
            say(f"── resuming after generation {self.gen} (of {generations})")
            self.trace.emit("resume", gen=self.gen, target=generations)
        else:
            self.start()
            self.checkpoint()
        try:
            for g in range(self.gen + 1, generations + 1):
                self.gen = g
                self.generation()
                self.checkpoint()
        finally:
            self.finish()

    # ------------------------------------------------------------------ checkpoints
    def checkpoint(self):
        led = self.ledger
        data = {"gen": self.gen, "target": getattr(self, "target", None), "problem": self.p.name, "label": self.label,
                "seed": self.seed, "x": [float(v) for v in self.x], "champ": self.champ, "cz": self.cz,
                "cz_gap": self.cz_gap, "history": self.history,
                "features": [f.record() for f in led.features.values()], "nodes": [n.record() for n in led.nodes.values()],
                "library": led.library, "backlog": led.backlog, "n_f": led._n_f, "n_n": led._n_n,
                "llm": {"calls": self.llm.calls, "tokens_in": self.llm.tokens_in, "tokens_out": self.llm.tokens_out},
                "last_plan": getattr(self, "_last_plan", None), "saved": time.time()}
        tmp = self.dir / "checkpoint.json.tmp"
        tmp.write_text(json.dumps(data, default=_jsonable))
        tmp.replace(self.dir / "checkpoint.json")

    def restore(self):
        p = self.dir / "checkpoint.json"
        if not p.exists():
            return False
        from .ledger import Node
        d = json.loads(p.read_text())
        led = self.ledger
        led.features = {r["id"]: Feature(**r) for r in d["features"]}
        led.nodes = {r["id"]: Node(**r) for r in d["nodes"]}
        led.library, led.backlog, led._n_f, led._n_n = d["library"], d["backlog"], d["n_f"], d["n_n"]
        self.gen, self.x = d["gen"], np.asarray(d["x"], dtype=float)
        self.champ, self.cz, self.cz_gap, self.history = d["champ"], d["cz"], d["cz_gap"], d["history"]
        self._last_plan = d.get("last_plan")
        for k, v in (d.get("llm") or {}).items():
            setattr(self.llm, k, v)
        self.ref_diag = {}
        for iid in self.p.diagnostic_ids():
            try:
                self.ref_diag[iid] = self.p.reference_metrics(self.p.instance("train", iid))
            except Exception:
                self.ref_diag[iid] = {}
        return True

    def generation(self):
        g, t0 = self.gen, time.time()
        say(f"── generation {g}: champion gap {self.champ['train']:.3f}% (progress {self.champ['progress']:.1f}%), "
            f"{len(self.ledger.library)} features")
        self.trace.emit("gen_start", gen=g, champion=self._champ_summary())
        self.phase("inspect", "sampling decisions, diagnosing the champion")
        self.sample_states()
        lib = self.ledger.lib()
        diag = self.diagnose(lib, self.x)
        self.trace.emit("diagnostics", gen=g, champion=diag, reference=self.ref_diag)
        sens = self.sensitivity()

        # the champion's weights are refitted from the start (it needs no plan), overlapping the Navigator
        refit, refit_done = {}, threading.Event()

        def do_refit():
            try:
                refit.update(self.refit_champion())
            except Exception as exc:              # fall back to the champion as it stands
                say(f"   refit failed: {str(exc)[:160]}")
                refit.update({"x": self.x.copy(), "train": self.champ["search"], "valid": self.champ["valid"],
                              "probe": self.champ.get("probe", self.champ["search"])})
            finally:
                refit_done.set()
        threading.Thread(target=do_refit, daemon=True).start()

        self.revive_streams()
        self.phase("navigate", "Navigator planning")
        plan = self.navigate(diag, sens)

        # deep and wide write at the same time; each feature enters the fit lane as soon as it is certified,
        # so the Mutator's features are probed and trialled while the Researcher is still thinking
        self.phase("agents", "Researcher, Coders and Mutator writing; fitting each feature as it arrives")
        lane, probed = queue.Queue(), []

        def fit_lane():
            refit_done.wait()
            while True:
                f = lane.get()
                if f is None:
                    return
                try:
                    if f.status in ("invalid", "duplicate", "inert", "span"):
                        continue
                    self.probe_feature(f, refit)
                    probed.append(f)
                    if f.status == "probed":
                        self.trial_feature(f, refit)
                except Exception as exc:          # a fitting error must not lose the generation
                    f.status, f.verdict, f.error = "invalid", "invalid", f"fitting failed: {exc}"[:200]
        lt = threading.Thread(target=fit_lane, daemon=True)
        lt.start()
        with ThreadPoolExecutor(2) as ex:
            fd = ex.submit(self.deep, plan, diag, sens, lane.put)
            fw = ex.submit(self.wide, plan, lane.put)
            deep, wide = fd.result(), fw.result()
        t_agents = time.time() - t0
        lane.put(None)
        lt.join()
        refit_done.wait()

        self.phase("fit", "near-miss trials and prediction checks")
        new = deep + wide
        trials = []
        live = [f for f in new if f.status not in ("invalid", "duplicate", "inert", "span")]
        # the best near-misses get a trial too (weak in the probe is not proven useless)
        near = sorted([f for f in live if f.status == "rejected" and f.best_probe is not None
                       and f.best_probe > -self.s.c("fit", "near_miss_floor", default=0.3)], key=lambda f: -f.best_probe)
        second = {f.id for f in near[:self.s.c("fit", "near_miss_trials", default=2)]}
        for f in live:
            if f.id in second and f.d_valid is None:
                f.verdict = "near-miss, trialled anyway"
                self.trial_feature(f, refit)
            if f.origin == "deep":
                self.check_prediction(f, refit)
            if f.d_valid is not None:
                trials.append(f)
        for f in new:
            self.trace.emit("feature_done", gen=g, feature=f.record())
        combos = self.try_combinations(plan, refit)

        self.phase("accept", "combining the winners")
        accepted = self.accept(trials, combos, refit)
        self.update_backlog(new)
        self.ledger.update_nodes(g, self.margin)
        self.update_streams(new)
        self.prove(plan)
        rec = self._gen_record(g, accepted, plan, time.time() - t0, t_agents=t_agents, new=new)
        self.history.append(rec)
        changed = {f.id for f in new} | set(self.ledger.library) | set(accepted)
        for f in self.ledger.features.values():
            if f.id in changed or f.status == "retired" and f.retired_gen == g:
                self.trace.emit("feature_done", gen=g, feature=f.record(), final=True)
        self.trace.emit("tree", gen=g, nodes=[n.record() for n in self.ledger.nodes.values()])
        self.trace.emit("gen_end", **rec)
        self.save()
        say(f"   kept {[self.ledger.features[a].name for a in accepted] or 'nothing'} → gap {self.champ['train']:.3f}% "
            f"progress {self.champ['progress']:.1f}% (valid {self.champ['valid_progress']:.1f}%) | "
            f"{time.time() - t0:.0f}s, {self.llm.calls} calls")

    # ------------------------------------------------------------------ streams
    def update_streams(self, new):
        """After a generation: each approach that ran experiments either gained (streak resets) or didn't.
        An approach that fails `bench_after` generations in a row is benched: off the Navigator's map, but not
        dead (only a certificate prunes). See revive_streams."""
        led, g = self.ledger, self.gen
        after = self.s.c("streams", "bench_after", default=3)
        ran = {}
        for f in new:
            if f.node in led.nodes and f.status not in ("invalid", "new"):
                gain = f.d_valid if f.d_valid is not None else f.best_probe
                ran.setdefault(f.node, []).append((f.status == "kept", gain))
        for nid, rs in ran.items():
            n = led.nodes[nid]
            best = max((x for _, x in rs if x is not None), default=None)
            n.gains.append([g, best])
            if any(k for k, _ in rs) or (best is not None and best > self.margin and any(x == best for _, x in rs)
                                         and any(f.node == nid and f.status == "kept" for f in new)):
                n.streak = 0
            elif any(k for k, _ in rs):
                n.streak = 0
            else:
                n.streak += 1
            if n.state not in ("pruned", "benched") and n.streak >= after:
                n.state, n.benched_gen = "benched", g
                self.trace.emit("bench", gen=g, approach=nid, streak=n.streak)

    def revive_streams(self):
        """Before planning: each benched approach comes back with a probability that grows while it rests."""
        p0 = self.s.c("streams", "revive_p", default=0.2)
        for n in self.ledger.nodes.values():
            if n.state != "benched":
                continue
            rest = self.gen - (n.benched_gen or self.gen)
            if self.rng.random() < min(0.6, p0 * (1 + rest / 4)):
                n.state, n.revived_gen = "unproven", self.gen
                n.streak = max(0, self.s.c("streams", "bench_after", default=3) - 1)   # one more miss benches it again
                self.trace.emit("revive", gen=self.gen, approach=n.id, rested=rest)

    def stream_lines(self):
        """Approaches ranked by how fast they have been improving the champion (recent gains weigh more)."""
        led, rows = self.ledger, []
        for n in led.nodes.values():
            if n.state in ("pruned", "benched") or not n.gains:
                continue
            score = sum((x or 0) * 0.7 ** (self.gen - gg) for gg, x in n.gains if x is not None and x > 0)
            kept = [f for f in (led.features.get(i) for i in n.features) if f and f.status == "kept"]
            rows.append((score, n, kept))
        rows.sort(key=lambda r: -r[0])
        out = []
        for score, n, kept in rows[:4]:
            if score <= 0:
                break
            path = " → ".join(f"{f.id} {f.name} (gen {f.gen}, +{(f.d_valid or 0):.2f})" for f in kept[-3:]) or "no kept feature yet"
            out.append(f"- {n.id} {n.title}: momentum {score:.2f}; {path}")
        return "\n".join(out)

    # ------------------------------------------------------------------ navigator
    def view(self):
        nodes = []
        for n in self.ledger.nodes.values():
            tried = [self.ledger.features[i] for i in n.features if i in self.ledger.features]
            nodes.append({"id": n.id, "title": n.title, "description": n.description, "state": n.state,
                          "tries": len(tried), "best_gain": n.best_gain, "last_gen": n.last_gen, "parent": n.parent})
        feats = [{"id": f.id, "node": f.node, "origin": f.origin, "status": f.status, "best_probe": f.best_probe,
                  "d_valid": f.d_valid, "gen": f.gen, "name": f.name} for f in self.ledger.features.values()]
        return {"gen": self.gen, "nodes": nodes, "features": feats, "library": list(self.ledger.library),
                "backlog": list(self.ledger.backlog), "config": self.cfg}

    def navigate(self, diag, sens):
        view = self.view()
        plan, source, note = None, "hooks", ""
        if self.s.c("navigator", "enabled", default=True):
            msg = self.navigator_message(view, diag, sens)
            try:
                rep = self.ask("navigator", roles.system_prompt(self.s, "navigator", self.p), msg, "navigator",
                               meta={"step": "navigate"}, json_reply=True)
                plan = roles.extract_json(rep.text)
                note = roles.after_json(rep.text) or roles.before_json(rep.text)
                source = "navigator"
            except Exception as exc:
                say(f"   navigator failed: {str(exc)[:160]}")
        if not isinstance(plan, dict):
            plan, source = self.s.hooks.allocate(view), "hooks"
        plan = self.normalise_plan(plan, view)
        plan["source"], plan["note"] = source, note or plan.get("thinking", "")
        self.trace.emit("plan", gen=self.gen, plan=plan)
        self._last_plan = plan
        return plan

    def normalise_plan(self, plan, view):
        """Create brainstormed approaches, resolve titles to ids, drop unknown ids, fill gaps from the hooks."""
        led = self.ledger
        title_to_id = {n.title.lower(): n.id for n in led.nodes.values()}
        for a in plan.get("new_approaches") or []:
            if not isinstance(a, dict) or not a.get("title"):
                continue
            t = str(a["title"])[:80]
            if t.lower() in title_to_id:
                continue
            parent = a.get("parent") if a.get("parent") in led.nodes else ""
            n = led.new_node(t, description=str(a.get("description", ""))[:300], parent=parent,
                             origin="navigator", created_gen=self.gen)
            title_to_id[t.lower()] = n.id
        research = []
        for r in plan.get("research") or []:
            if not isinstance(r, dict):
                continue
            a = str(r.get("approach", ""))
            aid = a if a in led.nodes else title_to_id.get(a.lower().removeprefix("new:").strip(), "")
            if aid and led.nodes[aid].state in ("pruned", "benched"):
                continue
            research.append({"approach": aid or "new", "mode": r.get("mode", "explore"), "why": str(r.get("why", ""))[:200]})
        n_exp = self.s.c("researcher", "experiments", default=4)
        if not research:
            research = self.s.hooks.allocate(view)["research"]
        plan["research"] = research[:n_exp]
        slots = self.s.c("mutator", "slots", default=4)
        mut = plan.get("mutate") if isinstance(plan.get("mutate"), dict) else {}
        vary = [v for v in (mut.get("vary") or []) if v in led.features and led.features[v].code
                and led.features[v].status not in ("invalid",)]
        if not vary and led.features:
            vary = [v for v in self.s.hooks.allocate(view)["mutate"]["vary"] if v in led.features]
        fresh = max(self.s.c("mutator", "fresh", default=1), slots - len(vary))
        plan["mutate"] = {"vary": vary[:max(0, slots - fresh)], "fresh": min(slots, fresh)}
        combos, dropped = [], []
        for c in plan.get("combine") or []:
            if not (isinstance(c, list) and len(c) == 2 and all(i in led.features for i in c)):
                continue
            bad = [i for i in c if led.features[i].status in ("kept", "invalid", "duplicate", "inert", "span")]
            (dropped if bad else combos).append(c if not bad else {"pair": c, "why": f"{', '.join(bad)} already kept or not evaluable"})
        plan["combine"] = combos[:self.s.c("combine", "max_pairs", default=2)]
        plan["dropped"] = dropped
        plan["prune"] = [p for p in (plan.get("prune") or []) if p in led.nodes]
        return plan

    def navigator_message(self, view, diag, sens):
        led = self.ledger
        parts = [f"Generation {self.gen}. The champion: gap {self.champ['train']:.3f}% on train, "
                 f"{self.champ['valid']:.3f}% on validation; progress {self.champ['progress']:.1f}% "
                 f"(Code Zero is 0%). Kept features: {len(led.library)}."]
        parts.append("## Where the room is (champion gap by family, % above reference; floor = best reachable)\n" +
                     self.room_lines())
        if led.nodes:
            rows, benched = [], []
            for n in view["nodes"]:
                node = led.nodes[n["id"]]
                if n["state"] == "benched":
                    benched.append(f"{n['id']} {n['title']}")
                    continue
                tag = " (revived from the bench this generation: one more try, from a different angle)" \
                    if node.revived_gen == self.gen else ""
                rows.append(f"- {n['id']} [{n['state']}] {n['title']}: {roles.short(n['description'], 120)} "
                            f"(tries {n['tries']}, best gain {roles.gain(n['best_gain'])}, last gen {n['last_gen'] or '-'}){tag}")
            parts.append("## The approach tree\n" + "\n".join(rows))
            if benched:
                parts.append("## Benched (no gain " + str(self.s.c("streams", "bench_after", default=3)) +
                             " generations in a row; resting, each returns at random later): " + "; ".join(benched))
            mom = self.stream_lines()
            if mom:
                parts.append("## Direction of fastest improvement (approaches ranked by recent gains; the arrow is "
                             "the chain of kept steps)\n" + mom + "\nPush the leader further along its chain (the next "
                             "step in the same direction, or a bolder one), and keep a share on the rest.")
        else:
            parts.append("## The approach tree\nEmpty: this is the first generation. Brainstorm the initial approaches "
                         "(5-8, genuinely different from each other), from the problem and the diagnostics below.")
        parts.append("## Champion diagnostics vs the reference\n" + self.p.describe_diagnostics(diag, self.ref_diag))
        if sens:
            parts.append("## Sensitivity probes (gap reduction on train; + = better)\n" + self.sens_lines(sens))
        recent = [f for f in led.features.values() if f.gen >= self.gen - 2]
        if recent:
            parts.append("## The ledger: the last two generations\n" + "\n".join(roles.feature_line(f) for f in recent[-24:]))
        if led.backlog:
            parts.append("## Near-misses (backlog, not kept, worth combining): " + ", ".join(f"{i} {led.features[i].name}" for i in led.backlog))
        hist = [f"- {n.id} {n.title}: gen {x['gen']}: {x.get('result', '')}" for n in led.nodes.values() for x in n.notes
                if x.get("prune_request")]
        if hist:
            parts.append("## Prune requests so far (don't repeat one that wasn't proven unless something changed)\n" + "\n".join(hist[-8:]))
        prev = getattr(self, "_last_plan", None)
        if prev and prev.get("dropped"):
            parts.append("## Last plan's combinations that couldn't run\n" + "\n".join(f"- {d['pair']}: {d['why']}" for d in prev["dropped"])
                         + "\nCombinations are for features that are *not* kept: a kept feature is already in every trial.")
        groups = self.similar_groups()
        if groups:
            parts.append("## Groups of tried features that rank candidates alike (|rho| >= 0.9): the same idea, re-expressed\n" + groups)
        n_exp = self.s.c("researcher", "experiments", default=4)
        slots = self.s.c("mutator", "slots", default=4)
        parts.append(f"## Budget this generation\n- Researcher: {n_exp} experiments (assign up to {n_exp} approaches)\n"
                     f"- Mutator: {slots} slots (parents to vary, plus at least {self.s.c('mutator', 'fresh', default=1)} fresh)\n"
                     f"- Combinations: up to {self.s.c('combine', 'max_pairs', default=2)} pairs")
        return "\n\n".join(parts)

    def room_lines(self):
        fams = self.champ["families"]
        out = []
        for fam in sorted(fams, key=lambda f: -(fams[f] - self._floor(f))):
            out.append(f"- {fam}: gap {fams[fam]:.2f}% (floor {self._floor(fam):.2f}%, Code Zero {self.cz['train'][fam]:.2f}%)")
        return "\n".join(out)

    def _floor(self, fam):
        return self.p.floor(fam, "train") if _takes_split(self.p.floor) else self.p.floor(fam)

    def sens_lines(self, sens):
        out = []
        for r in sens:
            d = r["deltas"]
            out.append(f"- {r['feature']} {r['name']}: " + ", ".join(f"×{m:g}: {roles.gain(v)}" for m, v in d.items()))
        return "\n".join(out)

    # ------------------------------------------------------------------ deep loop
    def deep(self, plan, diag, sens, on_ready=None):
        led = self.ledger
        msg = self.researcher_message(plan, diag, sens)
        exps = []
        for attempt in range(2):
            try:
                rep = self.ask("researcher", roles.system_prompt(self.s, "researcher", self.p),
                               msg if attempt == 0 else msg + "\n\nYour previous reply had no usable JSON. Reply with the "
                               "```json block first.", "researcher", meta={"step": "research"}, json_reply=True)
                data = roles.extract_json(rep.text) or {}
                exps = [e for e in data.get("experiments", []) if isinstance(e, dict) and (e.get("change") or e.get("feature"))]
                self.trace.emit("research", gen=self.gen, experiments=exps,
                                analysis=roles.after_json(rep.text) or roles.before_json(rep.text),
                                effort=self.effort("researcher"))
                if exps:
                    break
            except Exception as exc:
                say(f"   researcher failed: {str(exc)[:160]}")
        exps = exps[:self.s.c("researcher", "experiments", default=4) + 1]
        feats = []
        for e in exps:
            a = str(e.get("approach", ""))
            aid = a if a in led.nodes else ""
            if not aid:
                title = a.split(":", 1)[-1].strip() if ":" in a else (a or e.get("name", "new approach"))
                match = [n.id for n in led.nodes.values() if n.title.lower() == title.lower()]
                aid = match[0] if match else led.new_node(title[:80], description=roles.short(e.get("hypothesis", ""), 300),
                                                          origin="researcher", created_gen=self.gen).id
            pred = e.get("prediction") if isinstance(e.get("prediction"), dict) else {}
            f = led.new_feature(name=str(e.get("name") or "experiment")[:48], origin="deep", gen=self.gen, node=aid,
                                kind="probe" if str(e.get("kind", "")).startswith("probe") else "improve",
                                idea={"hypothesis": e.get("hypothesis", ""), "feature": e.get("change") or e.get("feature", ""),
                                      "prediction": pred, "builds_on": e.get("builds_on", ""),
                                      "lesson": e.get("lesson", "")})
            led.nodes[aid].features.append(f.id)
            feats.append(f)
        existing = "\n".join(f"- {g.name}: {roles.short(g.measures, 150)}" for g in led.lib()) or "(none yet)"

        def write(f):
            user = (f"## Existing features (don't duplicate them)\n{existing}\n\n## The experiment to write: `{f.name}`\n\n"
                    f"Why: {f.idea['hypothesis']}\n\nWhat to measure: {f.idea['feature']}\n\nWrite this feature.")
            try:
                rep = self.ask("coder", roles.system_prompt(self.s, "coder", self.p), user, "coder",
                               meta={"step": "code", "feature": f.id})
                f.code = extract_code(rep.text) or ""
                f.coder_note = roles.short(rep.text.split("```")[-1], 300) if f.code else ""
            except Exception as exc:
                f.error = str(exc)[:200]
            self.prepare(f, "coder")
            if on_ready:
                on_ready(f)
            return f

        return list(self.workers.map(write, feats))

    def researcher_message(self, plan, diag, sens):
        led = self.ledger
        parts = [f"Generation {self.gen}. Champion: gap {self.champ['train']:.3f}% (train), "
                 f"{self.champ['valid']:.3f}% (validation); progress {self.champ['progress']:.1f}%."]
        lib = led.lib()
        if lib:
            rows = []
            for f in lib:
                w = f.weights[0] if f.weights else 0
                rows.append(f"- {f.id} {f.name}: computes {roles.short(f.measures, 200)}; fitted weight "
                            f"{'+' if w >= 0 else '−'}{abs(w):.2f} (scaled), importance {roles.gain(f.importance)}")
            parts.append("## The champion policy\n" + "\n".join(rows))
        else:
            parts.append("## The champion policy\nNo features yet: every candidate scores 0, so the first candidate always wins (Code Zero).")
        parts.append("## Where the room is\n" + self.room_lines())
        notes = "\n".join(f"- `{k}`: {v}" for k, v in self.p.metric_notes.items())
        parts.append("## Diagnostics: the champion's solutions vs the reference\n" + self.p.describe_diagnostics(diag, self.ref_diag)
                     + (f"\n\nMetrics you can name in a prediction (plus `gap`):\n{notes}" if notes else ""))
        if sens:
            parts.append("## Sensitivity probes on the kept features (gap reduction on train; + = better)\n" + self.sens_lines(sens))
        assigned = [r["approach"] for r in plan["research"]]
        a_lines = []
        for r in plan["research"]:
            n = led.nodes.get(r["approach"])
            if n:
                a_lines.append(f"- {n.id} [{n.state}] **{n.title}**: {n.description} → mode `{r['mode']}` ({r['why']})")
            else:
                a_lines.append(f"- a new approach of your choice → mode `{r['mode']}` ({r['why']})")
        parts.append("## Your assignments from the Navigator (one experiment each, at least)\n" + "\n".join(a_lines))
        rel = [f for f in led.features.values() if f.node in assigned]
        rel += [f for f in led.features.values() if f.origin == "deep" and f.gen == self.gen - 1 and f not in rel]
        if rel:
            k = self.s.c("ledger_lines", default=14)
            parts.append("## The ledger for these approaches (and your last generation)\n" + "\n".join(roles.feature_line(f) for f in rel[-k:]))
        missed = [f for f in led.features.values() if f.origin == "deep" and f.prediction.get("checked")
                  and not f.prediction.get("held") and f.gen >= self.gen - 2]
        if missed:
            parts.append("## Predictions that did not hold (what the mechanism you believed didn't explain)\n" + "\n".join(
                f"- {f.id} {f.name}: predicted {f.prediction['metric']} {f.prediction['direction']} in {f.prediction['family']}; "
                f"it went {f.prediction.get('before')} → {f.prediction.get('after')}" for f in missed[-8:]))
        groups = self.similar_groups()
        if groups:
            parts.append("## Tried features that rank candidates alike (|rho| >= 0.9): one idea, re-expressed. Move to a "
                         "different quantity rather than another form of these.\n" + groups)
        finds = [f for f in led.features.values() if f.origin == "wide" and f.gen >= self.gen - 2
                 and f.status not in ("invalid", "duplicate", "inert") and f.best_probe is not None]
        finds.sort(key=lambda f: -(f.d_valid if f.d_valid is not None else f.best_probe))
        if finds:
            parts.append("## The Mutator's recent finds (it doesn't know why they work)\n" +
                         "\n".join(roles.feature_line(f, with_code=True, max_code=700) for f in finds[:3]))
        n = self.s.c("researcher", "experiments", default=4)
        parts.append(f"Design {n} experiments, at least one per assignment. Put the JSON block first.")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ wide loop
    def wide(self, plan, on_ready=None):
        led = self.ledger
        champ_code = compose(self.p, led.lib(), f"champion, gap {self.champ['train']:.3f}%")
        board = self.scoreboard()
        slots = [("vary", v) for v in plan["mutate"]["vary"]] + [("fresh", None)] * plan["mutate"]["fresh"]

        def write(slot):
            kind, parent = slot
            pf = led.features.get(parent) if parent else None
            f = led.new_feature(origin="wide", gen=self.gen, kind="variant" if pf else "fresh", parent=parent or "")
            if pf and pf.node:
                f.node = pf.node
            user = (f"## The current policy (gap {self.champ['train']:.3f}%, lower is better)\n\n```python\n{champ_code}\n```\n\n"
                    f"## Scoreboard: features already evaluated\n{board or '(nothing yet)'}\n\n")
            if pf:
                user += (f"## Write a variant of this feature: `{pf.name}`\n\n```python\n{pf.code.strip()}\n```\n\n"
                         "Keep a thread of it, but change it boldly. Start your reply with the ```python block.")
            else:
                user += "## Write a fresh feature: a measurement nothing on the scoreboard captures. Start your reply with the ```python block."
            for attempt in range(2):
                try:
                    rep = self.ask("mutator", roles.system_prompt(self.s, "mutator", self.p), user, "mutator",
                                   meta={"step": "mutate", "feature": f.id})
                    f.code = extract_code(rep.text) or ""
                    f.name = roles.extract_name(rep.text, f"wide_{f.id}")
                except Exception as exc:
                    f.error = str(exc)[:200]
                self.prepare(f, "mutator")
                if f.status == "duplicate" and attempt == 0 and self.s.c("mutator", "retry_duplicates", default=True):
                    src = led.features.get(f.duplicate_of)
                    self.trace.emit("feature_done", gen=self.gen, feature=f.record())
                    old = f
                    f = led.new_feature(origin="wide", gen=self.gen, kind=old.kind, parent=old.parent, node=old.node)
                    user += (f"\n\nYour first answer, `{old.name}`, ranks candidates exactly like `{src.name if src else old.duplicate_of}` "
                             "already on the scoreboard (same ordering, up to sign or a monotone transform), so it was "
                             "discarded. Write something that orders candidates differently.")
                    continue
                break
            if on_ready:
                on_ready(f)
            return f

        return list(self.workers.map(write, slots))

    def similar_groups(self, rho=0.9, min_size=3):
        """Clusters of evaluated features whose fingerprints correlate at |rho| >= 0.9 (the same idea, re-expressed)."""
        led = self.ledger
        feats = [f for f in led.features.values() if f.status not in ("new", "invalid", "checking") and f.code]
        if len(feats) < min_size or not led.states:
            return ""
        try:
            fps = {f.id: led.fingerprint(f, self.p.n_candidates) for f in feats}
        except Exception:
            return ""
        groups, seen = [], set()
        for f in feats:
            if f.id in seen:
                continue
            g = [h for h in feats if h.id not in seen and led.similarity(fps[f.id], fps[h.id]) >= rho]
            if len(g) >= min_size:
                groups.append(g)
                seen |= {h.id for h in g}
        return "\n".join("- " + ", ".join(f"{h.id} {h.name}" for h in g[:8]) + (f" (+{len(g) - 8})" if len(g) > 8 else "")
                         for g in groups)

    def scoreboard(self):
        led = self.ledger
        k = self.s.c("mutator", "scoreboard", default=10)
        done = [f for f in led.features.values() if f.status not in ("new", "invalid") and f.code]
        kept = [f for f in done if f.status == "kept"]
        rest = sorted([f for f in done if f.status != "kept"],
                      key=lambda f: -(f.d_valid if f.d_valid is not None else (f.best_probe if f.best_probe is not None else -9)))
        pick = kept + rest[:max(0, k - len(kept) - 3)] + rest[-3:] if len(rest) > 3 else kept + rest
        seen, out = set(), []
        for f in pick:
            if f.id not in seen:
                seen.add(f.id)
                out.append(roles.scoreboard_line(f))
        return "\n".join(out[:k + 2])

    # ------------------------------------------------------------------ preparing new features
    def prepare(self, f, author):
        """Check a freshly written feature (one repair by its author), then certify it."""
        if not f.code:
            try:
                rep_ = self.ask(author, roles.system_prompt(self.s, author, self.p),
                                "Your previous reply had no usable code block. Reply with the complete feature in a single "
                                "```python block defining `def feature(...)`, then nothing else.", author,
                                meta={"step": "repair", "feature": f.id})
                f.code = extract_code(rep_.text) or ""
            except Exception as exc:
                f.error = str(exc)[:200]
        if not f.code:
            f.status, f.verdict = "invalid", "invalid"
            f.error = f.error or "no code in the reply"
            return
        for attempt in range(2):
            if self.check(f):
                break
            if attempt == 1:
                f.status, f.verdict = "invalid", "invalid"
                return
            user = (f"Your feature failed when it was checked:\n\n```\n{f.error}\n```\n\nHere is the feature:\n\n"
                    f"```python\n{f.code}\n```\n\nFix the error and keep the idea the same. Reply with the complete fixed "
                    "feature in a single ```python block.")
            try:
                rep = self.ask(author, roles.system_prompt(self.s, author, self.p), user, author,
                               meta={"step": "repair", "feature": f.id})
                code = extract_code(rep.text)
                if code:
                    f.code = code
                    f.measures = docstring(code)
            except Exception as exc:
                f.error = str(exc)[:200]
        f.measures = docstring(f.code) or f.idea.get("feature", "")[:200]
        f.status = "checking"
        with self._cert_lock:                 # first come stays the original; later twins are duplicates
            cert = self.certify(f)
            if f.status == "checking":
                f.status = "checked"
        self.trace.emit("novelty", gen=self.gen, feature=f.id, certificate=cert)

    # ------------------------------------------------------------------ fitting
    def refit_champion(self):
        lib = self.ledger.lib()
        budget = self.s.c("fit", "champion_refit_evals", default=24)
        base_valid = self.champ["valid"]
        x, s = self.x.copy(), self.champ["search"]
        if lib and budget:
            x, s = self.fit.optimise([f.code for f in lib], self.x, lambda z: self.unpack(lib, z), budget,
                                     sigma=self.s.c("fit", "sigma", default=0.3) * self.xscale, seed=self.gen, split=self.S)
        v = self.evaluate(lib, [x], "valid")[0][0] if lib else base_valid
        out = {"x": x, "train": s, "valid": v}
        out["probe"] = s if self.P == self.S else self.evaluate(lib, [x], self.P)[0][0]
        if lib and s < self.champ["search"] - 1e-9 and v is not None and v < base_valid - 1e-9:
            out["improved"] = True
        self.trace.emit("refit", gen=self.gen, train=s, valid=v, improved=bool(out.get("improved")))
        return out

    def probe_feature(self, f, refit):
        """The cheap first pass: the feature alone on top of the (refitted) champion, at a few weights."""
        lib = self.ledger.lib()
        feats = lib + [f]
        base_x, base_train, base_valid = refit["x"], refit["train"], refit["valid"]
        mults = self.s.c("fit", "probe_multiples", default=[1, -1, 0.3, -0.3, 0.1, -0.1])
        if not lib:
            mults = [m for m in mults if abs(m) == max(abs(x) for x in mults)]   # alone, only the sign matters
        ws = [round(m * self.spread, 6) for m in mults]
        xs = [np.concatenate([base_x, np.full(f.width, w)]) for w in ws]
        res = self.evaluate(feats, xs, self.P)
        base_train = refit["probe"]
        f.probe, best = [], None
        for w, (s, _, err) in zip(ws, res):
            if s is None:
                f.status, f.verdict, f.error = "invalid", "invalid", err or "failed"
                return
            d = round(base_train - s, 4)
            f.probe.append([w, d])
            if best is None or d > best[1]:
                best = (w, d)
        f.best_w, f.best_probe = best
        self.trace.emit("probe", gen=self.gen, feature=f.id, probe=f.probe)
        if f.best_probe < -self.s.c("fit", "probe_margin", default=0.08):
            f.status, f.verdict = "rejected", "rejected by the probe"
        else:
            f.status = "probed"

    def trial_feature(self, f, refit):
        """With vs without: refit everything with the feature, credit it with the difference (train and valid)."""
        feats = self.ledger.lib() + [f]
        base_x, base_train, base_valid = refit["x"], refit["train"], refit["valid"]
        x0 = np.concatenate([base_x, np.full(f.width, f.best_w)])
        mask = np.zeros(len(x0), bool)
        mask[-f.width:] = True
        x1, _ = self.fit.optimise([g.code for g in feats], x0, lambda z: self.unpack(feats, z), 5, mask=mask,
                                  sigma=abs(f.best_w), split=self.S)
        x2, s2 = self.fit.optimise([g.code for g in feats], x1, lambda z: self.unpack(feats, z),
                                   self.s.c("fit", "trial_evals", default=16), sigma=self.s.c("fit", "sigma", default=0.3) * self.xscale,
                                   seed=self.gen, split=self.S)
        v2 = self.evaluate(feats, [x2], "valid")[0][0]
        f.trial_x = [float(v) for v in x2]
        f.d_train = round(base_train - s2, 4)
        f.d_valid = round(base_valid - v2, 4) if v2 is not None else None
        f.status = "tried"
        good = f.d_valid is not None and f.d_valid > self.margin and f.d_train > 0
        f.verdict = "gain" if good else ("worse" if (f.d_valid or 0) < -self.margin else "flat")
        self.trace.emit("trial", gen=self.gen, feature=f.id, d_train=f.d_train, d_valid=f.d_valid, verdict=f.verdict)

    def check_prediction(self, f, refit):
        """Did the metric the Researcher named move the way it predicted?"""
        pred = f.idea.get("prediction") or {}
        metric, fam, direction = pred.get("metric"), pred.get("family"), str(pred.get("direction", "")).lower()
        if not metric or f.best_w is None:
            f.prediction = {"metric": metric, "family": fam, "direction": direction, "checked": False}
            return
        if not f.trial_x and f.best_probe < -3 * self.s.c("fit", "probe_margin", default=0.08):
            f.prediction = {"metric": metric, "family": fam, "direction": direction, "checked": False,
                            "why": "not checked: the feature made the policy much worse at every weight tried"}
            return
        ids = [i for i in self.p.diagnostic_ids() if i.startswith(str(fam))] or self.p.diagnostic_ids()[:1]
        lib = self.ledger.lib()
        x_with = np.asarray(f.trial_x) if f.trial_x else np.concatenate([refit["x"], np.full(f.width, f.best_w)])
        try:
            before = self.diagnose(lib, refit["x"], ids)[ids[0]].get(metric)
            after = self.diagnose(lib + [f], x_with, ids)[ids[0]].get(metric)
        except Exception:
            before = after = None
        held = None
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            eps = 1e-9 + 0.002 * abs(before)
            held = (after < before - eps) if direction.startswith("down") else (after > before + eps)
        f.prediction = {"metric": metric, "family": fam, "direction": direction, "before": before, "after": after,
                        "held": held, "checked": held is not None, "instance": ids[0]}
        self.trace.emit("prediction", gen=self.gen, feature=f.id, **f.prediction)

    def try_combinations(self, plan, refit):
        led = self.ledger
        pairs = [tuple(p) for p in plan.get("combine", [])]
        out = []
        for a, b in pairs:
            fa, fb = led.features[a], led.features[b]
            if fa.status in ("kept", "invalid", "duplicate", "inert", "span") or fb.status in ("kept", "invalid", "duplicate", "inert", "span"):
                continue
            if fa.best_w is None or fb.best_w is None:
                continue
            feats = led.lib() + [fa, fb]
            x0 = np.concatenate([refit["x"], np.full(fa.width, fa.best_w), np.full(fb.width, fb.best_w)])
            x, s = self.fit.optimise([g.code for g in feats], x0, lambda z: self.unpack(feats, z),
                                     self.s.c("fit", "trial_evals", default=16), seed=self.gen + 7, split=self.S,
                                     sigma=self.s.c("fit", "sigma", default=0.3) * self.xscale)
            v = self.evaluate(feats, [x], "valid")[0][0]
            dt, dv = round(refit["train"] - s, 4), (round(refit["valid"] - v, 4) if v is not None else None)
            rec = {"pair": [a, b], "x": x.tolist(), "d_train": dt, "d_valid": dv}
            self.trace.emit("combination", gen=self.gen, **{k: v for k, v in rec.items() if k != "x"})
            out.append(rec)
        return out

    def accept(self, trials, combos, refit):
        led = self.ledger
        lib = led.lib()
        x, train, valid = refit["x"], refit["train"], refit["valid"]
        accepted = []
        cands = [("f", f.d_valid, [f]) for f in trials if f.d_valid is not None and f.d_valid > self.margin and f.d_train > 0]
        cands += [("c", c["d_valid"], [led.features[i] for i in c["pair"]]) for c in combos
                  if c["d_valid"] is not None and c["d_valid"] > self.margin and c["d_train"] > 0]
        cands.sort(key=lambda c: -c[1])
        cur_feats = list(lib)
        for kind, _, group in cands:
            if any(g in cur_feats for g in group):
                continue
            add = []
            for g in group:
                tx = g.trial_x[-g.width:] if g.trial_x else [g.best_w] * g.width
                add.append(np.asarray(tx, dtype=float))
            feats = cur_feats + group
            x0 = np.concatenate([x] + add)
            x1, s1 = self.fit.optimise([g.code for g in feats], x0, lambda z: self.unpack(feats, z), 12,
                                       seed=self.gen + 3, split=self.S, sigma=self.s.c("fit", "sigma", default=0.3) * self.xscale)
            v1 = self.evaluate(feats, [x1], "valid")[0][0]
            if v1 is not None and v1 < valid - self.margin / 2 and s1 < train:
                cur_feats, x, train, valid = feats, x1, s1, v1
                accepted += [g.id for g in group]
                for g in group:
                    g.status, g.verdict, g.kept_gen = "kept", "kept", self.gen
                self.trace.emit("accept", gen=self.gen, features=[g.id for g in group], train=s1, valid=v1)
            else:
                for g in group:
                    if g.status != "kept":
                        g.verdict = "redundant"
                        g.status = "tried"
                self.trace.emit("redundant", gen=self.gen, features=[g.id for g in group], train=s1, valid=v1)
        if accepted:
            xj, sj = self.fit.optimise([g.code for g in cur_feats], x, lambda z: self.unpack(cur_feats, z),
                                       self.s.c("fit", "joint_refit_evals", default=32), seed=self.gen + 5, split=self.S,
                                       sigma=self.s.c("fit", "sigma", default=0.3) * self.xscale)
            vj = self.evaluate(cur_feats, [xj], "valid")[0][0]
            if vj is not None and sj < train and vj < valid:
                x, train, valid = xj, sj, vj
        elif refit.get("improved"):
            pass
        else:
            x, train, valid = self.x, self.champ["search"], self.champ["valid"]
        # retire features the policy is better without (on validation)
        retired = []
        if len(cur_feats) > 1:
            xs, spans, i = [], [], 0
            for g in cur_feats:
                z = x.copy()
                z[i:i + g.width] = 0
                xs.append(z)
                spans.append((i, g.width))
                i += g.width
            res = self.evaluate(cur_feats, xs, "valid")
            for g, (s, _, _) in zip(cur_feats, res):
                if s is not None:
                    g.importance = round(s - valid, 4)
            worst = min(((s, g) for g, (s, _, _) in zip(cur_feats, res) if s is not None), default=None, key=lambda t: t[0])
            if worst and worst[0] < valid - self.margin:
                g = worst[1]
                keep = [h for h in cur_feats if h is not g]
                idx = cur_feats.index(g)
                start = sum(h.width for h in cur_feats[:idx])
                x = np.concatenate([x[:start], x[start + g.width:]])
                cur_feats = keep
                train = self.evaluate(cur_feats, [x], self.S)[0][0]
                valid = worst[0]
                g.status, g.retired_gen = "retired", self.gen
                retired.append(g.id)
                self.trace.emit("retire", gen=self.gen, feature=g.id, valid=valid)
        elif len(cur_feats) == 1:
            z = x.copy()
            z[:] = 0
            s = self.evaluate(cur_feats, [z], "valid")[0][0]
            if s is not None:
                cur_feats[0].importance = round(s - valid, 4)
        led.library = [g.id for g in cur_feats]
        i = 0
        for g in cur_feats:
            g.weights = [float(v) for v in x[i:i + g.width]]
            i += g.width
        fams_t = self.evaluate(cur_feats, [x], "train")[0]
        fams_v = self.evaluate(cur_feats, [x], "valid")[0]
        self.x = x
        self.champ = {"train": fams_t[0], "valid": fams_v[0], "families": fams_t[1], "valid_families": fams_v[1],
                      "progress": self.progress(fams_t[1], "train"), "valid_progress": self.progress(fams_v[1], "valid"),
                      "search": fams_t[0] if self.S == "train" else self.evaluate(cur_feats, [x], self.S)[0][0]}
        return accepted

    def update_backlog(self, new):
        led = self.ledger
        near = self.s.c("combine", "near_miss", default=0.3)
        pool = [f for f in led.features.values() if f.status in ("tried", "rejected") and f.best_probe is not None
                and f.best_probe > -near and f.verdict != "redundant"]
        pool.sort(key=lambda f: -(f.d_valid if f.d_valid is not None else f.best_probe))
        led.backlog = [f.id for f in pool[:6]]
        # wide features without an approach: file them by behaviour, or open a node for them
        for f in new:
            if f.origin != "wide" or f.node or f.status in ("invalid",):
                continue
            members = [i for n in led.nodes.values() for i in n.features]
            best_id, rho = (led.nearest(f, self.p.n_candidates, members) if members and led.states else ("", 0.0))
            if best_id and rho >= 0.85:
                f.node = led.features[best_id].node
            else:
                n = led.new_node(f"wide find: {f.name}", description=roles.short(f.measures, 200), origin="wide",
                                 created_gen=self.gen)
                f.node = n.id
            led.nodes[f.node].features.append(f.id)

    def prove(self, plan):
        led = self.ledger
        for nid in plan.get("prune", []):
            n = led.nodes.get(nid)
            if not n or n.state == "pruned":
                continue
            feats = [led.features[i] for i in n.features if i in led.features]
            open_ = [f for f in feats if f.certificate.get("type") not in ("inert", "duplicate", "span")
                     and f.status not in ("invalid", "new")]
            if not open_:
                continue
            argued = []
            close = [f for f in open_ if (f.certificate.get("rho") or 0) >= 0.93 or (f.certificate.get("lib_r2") or 0) >= 0.98]
            if not close:
                n.notes.append({"gen": self.gen, "prune_request": True, "result": "not attempted: no feature under it is "
                                "close to a duplicate or to the kept features (nearest rho < 0.93, R^2 < 0.98)"})
                self.trace.emit("prove", gen=self.gen, approach=nid, state=n.state, argued=[], skipped=True)
                continue
            if self.s.c("prover", "enabled", default=True):
                kept = "\n\n".join(f"### {g.id} {g.name} (kept)\n```python\n{g.code.strip()}\n```" for g in led.lib()) or "(none)"
                body = "\n\n".join(f"### {f.id} {f.name}\nengine's nearest match: {f.certificate}\n```python\n{f.code.strip()}\n```"
                                   for f in open_)
                user = (f"Approach {n.id}: **{n.title}**. {n.description}\n\n## Features tried under it\n\n{body}\n\n"
                        f"## The kept features\n\n{kept}\n\nCertify each feature, or answer `none`.")
                try:
                    rep = self.ask("prover", roles.system_prompt(self.s, "prover", self.p), user, "prover",
                                   meta={"step": "prove", "approach": nid})
                    data = roles.extract_json(rep.text) or {}
                    for c in data.get("certificates", []):
                        f = led.features.get(str(c.get("feature")))
                        if f is None or f not in open_:
                            continue
                        argued.append(c)
                        if c.get("type") == "span":
                            r2 = led.span_r2_of(f, self.p.n_candidates)
                            if r2 is not None and r2 >= led.span_r2:
                                f.certificate = {"type": "span", "r2": round(r2, 5), "by": "prover"}
                        if c.get("type") == "duplicate" and c.get("of") in led.features:
                            g = led.features[c["of"]]
                            rho = led.similarity(led.fingerprint(f, self.p.n_candidates), led.fingerprint(g, self.p.n_candidates))
                            if rho >= led.duplicate_rho:
                                f.certificate = {"type": "duplicate", "of": g.id, "rho": round(rho, 4), "by": "prover"}
                except Exception as exc:
                    say(f"   prover failed: {str(exc)[:120]}")
            n.notes.append({"gen": self.gen, "prune_request": True, "argued": argued,
                            "result": "pruned" if all(f.certificate.get("type") in ("inert", "duplicate", "span") for f in open_)
                            else "not proven: stays at lower priority"})
            led.update_nodes(self.gen, self.margin)
            self.trace.emit("prove", gen=self.gen, approach=nid, state=n.state, argued=argued)

    # ------------------------------------------------------------------ records
    def _champ_summary(self):
        return {"train": self.champ["train"], "valid": self.champ["valid"], "progress": self.champ["progress"],
                "valid_progress": self.champ.get("valid_progress"), "library": list(self.ledger.library)}

    def _gen_record(self, g, accepted, plan, seconds, t_agents=0.0, new=()):
        led = self.ledger
        return {"gen": g, "train": self.champ["train"], "valid": self.champ["valid"],
                "progress": self.champ["progress"], "valid_progress": self.champ.get("valid_progress"),
                "families": self.champ["families"], "accepted": accepted, "library": list(led.library),
                "weights": [led.features[i].weights for i in led.library],
                "features": [f.id for f in new], "plan_source": plan.get("source") if plan else None,
                "seconds": round(seconds, 1), "agent_seconds": round(t_agents, 1), "calls": self.llm.calls,
                "tokens_in": self.llm.tokens_in, "tokens_out": self.llm.tokens_out, "evals": self.fit.evals,
                "nodes": {s: sum(n.state == s for n in led.nodes.values()) for s in ("untried", "promising", "unproven", "pruned")}}

    def save(self):
        self.ledger.save(self.dir / "ledger.json")
        (self.dir / "champion.py").write_text(compose(self.p, self.ledger.lib(),
                                                      f"{self.p.name}, gap {self.champ['train']:.3f}%, progress {self.champ['progress']:.1f}%"))
        (self.dir / "history.json").write_text(json.dumps(self.history, indent=1, default=_jsonable))

    def finish(self):
        try:
            test = None
            try:
                r = self.evaluate(self.ledger.lib(), [self.x], "test")[0]
                cz = self.fit.evaluate([], [[]], "test")[0]
                self.cz["test"] = cz[1]
                test = {"gap": r[0], "families": r[1], "code_zero": cz[0], "progress": self.progress(r[1], "test")}
            except Exception as exc:
                test = {"error": str(exc)[:200]}
            summary = {"problem": self.p.name, "label": self.label, "generations": self.gen,
                       "code_zero": self.cz_gap, "champion": self._champ_summary(), "test": test,
                       "progress_curve": [h["progress"] for h in self.history],
                       "valid_curve": [h.get("valid_progress") for h in self.history],
                       "calls": self.llm.calls, "tokens_in": self.llm.tokens_in, "tokens_out": self.llm.tokens_out,
                       "features_tried": sum(f.origin in ("deep", "wide") for f in self.ledger.features.values()),
                       "kept": [{"id": f.id, "name": f.name, "origin": f.origin} for f in self.ledger.lib()],
                       "finished": time.time()}
            (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=_jsonable))
            self.trace.emit("run_end", **summary)
            self.save()
            (self.dir / "status.json").write_text(json.dumps({"state": "finished", "gen": self.gen, "label": self.label}))
        except Exception:
            traceback.print_exc()
        finally:
            self.fit.close()
            self.trace.close()
            self.workers.shutdown(wait=False)


def _takes_split(fn):
    import inspect
    try:
        return "split" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
