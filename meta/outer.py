"""The meta loop: an evolutionary search over *strategies* (how Helix searches), run by the same kind of loop.

    python -m meta.outer --problems binpack1d,knapsack,tsp --held-out coloring \\
        --inner-generations 5 --repeats 2 --outer-generations 10

Each outer generation:
  1. the Navigator (outer) plans: approaches to how Helix searches, Researcher assignments, Mutator parents;
  2. the Researcher (outer) reads the incumbent's meta-evaluation and the digests of its inner runs (search problems
     only) and designs edits with predictions; Coders write them as file edits;
  3. the Mutator (outer) makes blind, bold variants of strategy files from the scoreboard of evaluated strategies;
  4. every candidate is validated (budgets capped, hooks run, prompts present; one repair by its author) and
     meta-evaluated on the same problems and seeds as the incumbent; crashes get one supervised repair;
  5. the best candidate that beats the incumbent by more than the noise, without losing on the held-out problems,
     is **promoted**: it becomes the incumbent, and it is **swapped into the outer loop itself**: from then on
     the outer roles use its method prompts and settings. If a swapped-in strategy makes the outer roles fail
     twice in a row, the outer loop swaps back.

Outer roles' system prompts = the outer strategy's method prompt (prompts/<role>.md) + the meta-level addendum
(meta/space/<role>.md) + the meta problem (meta/space/problem.md).
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import strategies as S
from .evaluate import ROOT, evaluate

from helix3 import roles  # noqa: E402
from helix3.engine import Strategy, Trace  # noqa: E402
from helix3.ledger import Node  # noqa: E402
from helix3.llm import LLM  # noqa: E402

SPACE = Path(__file__).resolve().parent / "space"
STAT_KEYS = ("final", "auc", "plateau", "flat_tail", "duplicates", "invalid", "probe_rejected", "kept_deep",
             "kept_wide", "predictions_held", "calls")


def say(*a):
    print(*a, flush=True)


class Outer:
    def __init__(self, args, llm=None):
        self.a = args
        if getattr(args, "resume", None):
            saved = json.loads((Path(args.resume) / "args.json").read_text())
            for k, v in saved.items():                        # the original settings, unless overridden
                if k not in ("resume", "outer_generations") or getattr(args, k, None) is None:
                    setattr(args, k, v)
            args.out = args.resume
        self.dir = Path(args.out or ROOT / "meta_runs" / f"outer-{time.strftime('%Y%m%d-%H%M%S')}")
        (self.dir / "candidates").mkdir(parents=True, exist_ok=True)
        if not getattr(args, "resume", None):
            (self.dir / "args.json").write_text(json.dumps({k: v for k, v in vars(args).items() if k != "resume"}))
        self.trace = Trace(self.dir / "trace.jsonl")
        self.llm = llm or LLM()
        self.llm.on_call = lambda rec: self.trace.emit("call", id=self.trace.call_id(), gen=self.gen, **rec)
        self.gen = 0
        self.cands = {}          # id -> record
        self.nodes = {}
        self.n_c = 0
        self.n_n = 0
        self.inc = None          # incumbent id
        self.outer_dir = self.dir / "outer_strategy"
        self.prev_outer = None
        self.role_failures = 0
        self.problems = [p for p in args.problems.split(",") if p]
        self.held = [p for p in args.held_out.split(",") if p]
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ helpers
    def new_id(self):
        self.n_c += 1
        return f"c{self.n_c:03d}"

    def outer_strategy(self):
        return Strategy(self.outer_dir)

    def system(self, role):
        st = self.outer_strategy()
        return (f"{st.prompts[role].strip()}\n\n{(SPACE / f'{role}.md').read_text().strip()}\n\n"
                f"{(SPACE / 'problem.md').read_text().strip()}")

    def ask(self, role, user):
        st = self.outer_strategy()
        c = st.config.get(role, {})
        return self.llm.chat(f"outer-{role}", self.system(role), user, temperature=c.get("temperature", 0.6),
                             max_tokens=max(6000, c.get("max_tokens", 4000)), effort=c.get("effort", "low"))

    def evaluate(self, cid):
        rec = self.cands[cid]
        say(f"   evaluating {cid} ({rec.get('name', '')})")
        r = evaluate(rec["dir"], self.problems, self.held, self.a.inner_generations, self.a.repeats,
                     self.a.parallel, self.dir / "evals" / cid, self.a.timeout, self.a.workers,
                     fake=getattr(self.a, "fake_inner", False))
        rec["result"] = {k: r[k] for k in ("score", "worst", "noise", "held_out_score", "problems", "held_out",
                                            "minutes", "calls", "crashes")}
        rec["stats"] = self.problem_stats(r)
        self.trace.emit("evaluated", gen=self.gen, candidate=cid, score=r["score"], held_out=r["held_out_score"],
                        problems=r["problems"], crashes=len(r["crashes"]))
        return r

    @staticmethod
    def problem_stats(r):
        """Per problem, the mean over repeats of the run scores and of how the search behaved (from the digests)."""
        from helix3 import digest
        out = {}
        for run in r["runs"]:
            d = out.setdefault(run["problem"], {k: [] for k in STAT_KEYS})
            for k in ("final", "auc", "plateau", "flat_tail", "calls"):
                if isinstance(run.get(k), (int, float)):
                    d[k].append(run[k])
            ev = digest.load(run["dir"])
            if ev:
                s = digest.stats(ev)
                for k in ("duplicates", "invalid", "probe_rejected", "kept_deep", "kept_wide", "predictions_held"):
                    d[k].append(s.get(k, 0))
        return {p: {k: round(statistics.mean(v), 2) for k, v in d.items() if v} for p, d in out.items()}

    # ------------------------------------------------------------------ run
    def status(self, state="running"):
        import os
        (self.dir / "status.json").write_text(json.dumps({"state": state, "pid": os.getpid(), "gen": self.gen,
                                                          "target": self.a.outer_generations, "t": time.time()}))

    def resume(self):
        """Continue from state.json (saved after every outer generation): a generation in flight is redone."""
        d = json.loads((self.dir / "state.json").read_text())
        self.cands = {c["id"]: c for c in d["candidates"]}
        self.nodes = {n["id"]: Node(**n) for n in d.get("nodes", [])}
        self.inc, self.gen = d["incumbent"], d["gen"]
        self.n_c = max(int(c[1:]) for c in self.cands)
        self.n_n = max([int(n[1:]) for n in self.nodes] or [0])
        self.trace.emit("resume", gen=self.gen)
        say(f"── resuming the meta loop after outer generation {self.gen}")
        self.status()
        for g in range(self.gen + 1, self.a.outer_generations + 1):
            self.gen = g
            self.generation()
            self.status()
        self.status("finished")
        self.trace.emit("outer_end", incumbent=self.inc, score=self.cands[self.inc]["result"]["score"])

    def run(self):
        if getattr(self.a, "resume", None):
            return self.resume()
        self.status()
        start = Path(self.a.strategy).resolve()
        cid = self.new_id()
        cdir = self.dir / "candidates" / cid
        shutil.copytree(start, cdir, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(start, self.outer_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        self.cands[cid] = {"id": cid, "dir": str(cdir), "origin": "seed", "name": "starting strategy", "gen": 0,
                           "hash": S.digest_hash(cdir), "parent": None}
        self.trace.emit("outer_start", problems=self.problems, held_out=self.held, args=vars(self.a))
        say(f"── outer generation 0: evaluating the starting strategy")
        self.evaluate(cid)
        self.inc = cid
        self.cands[cid]["verdict"] = "incumbent"
        self.save()
        for g in range(1, self.a.outer_generations + 1):
            self.gen = g
            self.generation()
            self.status()
        self.status("finished")
        self.trace.emit("outer_end", incumbent=self.inc, score=self.cands[self.inc]["result"]["score"])
        say(f"done: incumbent {self.inc}, score {self.cands[self.inc]['result']['score']}")

    def generation(self):
        inc = self.cands[self.inc]
        say(f"── outer generation {self.gen}: incumbent {self.inc} score {inc['result']['score']:.2f}")
        plan = self.navigate()
        new = []
        with ThreadPoolExecutor(2) as ex:
            fd = ex.submit(self.deep, plan)
            fw = ex.submit(self.wide, plan)
            new = fd.result() + fw.result()
        seen = {c["hash"] for c in self.cands.values() if c.get("result")}
        todo = []
        for cid in new:
            c = self.cands[cid]
            if c.get("invalid"):
                continue
            if c["hash"] in seen:
                c["verdict"] = "duplicate"
                continue
            seen.add(c["hash"])
            todo.append(cid)
        for cid in todo:
            r = self.evaluate(cid)
            if r["crashes"] and self.supervise(cid, r):
                self.evaluate(cid)
            self.check_prediction(cid)
        self.promote(todo)
        self.update_nodes()
        self.save()

    # ------------------------------------------------------------------ roles
    def report(self, cid, with_digests=True):
        c = self.cands[cid]
        r = c["result"]
        lines = [f"Strategy {cid} ({c.get('name', '')}): score {r['score']:.2f}, worst problem {r['worst']:.2f}, "
                 f"noise between repeats {r['noise']}, held-out score {r['held_out_score']}"]
        for p, v in r["problems"].items():
            st = c.get("stats", {}).get(p, {})
            lines.append(f"- {p}: score {v['score']:.1f} (final {v['final']:.1f}%, AUC {v['auc']:.1f}%, 90% by gen "
                         f"{v['plateau']}, crashes {v['crashes']}); " + ", ".join(f"{k} {st[k]}" for k in STAT_KEYS if k in st and k not in ("final", "auc", "plateau")))
        if with_digests:
            for p in self.problems:
                d = self.dir / "evals" / cid / f"{p}-r0" / "digest.txt"
                if d.exists():
                    lines.append(f"\n### Inner run digest: {p} (repeat 0)\n" + d.read_text()[:3500])
        return "\n".join(lines)

    def ledger_lines(self, k=16):
        rows = []
        inc_score = self.cands[self.inc]["result"]["score"]
        for c in list(self.cands.values())[-k:]:
            if c.get("result"):
                tag = f"score {c['result']['score']:.2f} ({c['result']['score'] - inc_score:+.2f} vs the incumbent now)"
            else:
                tag = c.get("verdict") or "not evaluated"
            pr = c.get("prediction_outcome") or {}
            ptxt = f"; prediction {pr.get('family')}/{pr.get('metric')} {pr.get('direction')}: {'held' if pr.get('held') else 'did not hold'}" if pr.get("checked") else ""
            rows.append(f"- {c['id']} {c.get('name', '')} ({c['origin']}, gen {c['gen']}, approach {c.get('node', '-')}): "
                        f"{roles.short(c.get('change', ''), 200)} → {tag}, verdict {c.get('verdict', '-')}{ptxt}")
        return "\n".join(rows)

    def navigate(self):
        nodes = "\n".join(f"- {n.id} [{n.state}] {n.title}: {n.description} (tries {len(n.features)}, best {roles.gain(n.best_gain, 2)})"
                          for n in self.nodes.values()) or "Empty: brainstorm the initial approaches (4-6)."
        user = (f"Outer generation {self.gen}.\n\n## The incumbent\n{self.report(self.inc, with_digests=False)}\n\n"
                f"## The approach tree\n{nodes}\n\n## The ledger (candidates)\n{self.ledger_lines()}\n\n"
                f"## Budget\n- Researcher: {self.a.deep} experiments\n- Mutator: {self.a.wide} slots (parents are candidate ids)")
        plan = None
        try:
            rep = self.ask("navigator", user)
            plan = roles.extract_json(rep.text)
            self.role_ok(plan is not None)
        except Exception as exc:  # noqa: BLE001
            say(f"   outer navigator failed: {exc}")
            self.role_ok(False)
        if not isinstance(plan, dict):
            plan = {"research": [{"approach": "new: anything", "mode": "explore", "why": "fallback"}],
                    "mutate": {"vary": [self.inc], "fresh": 0}}
        titles = {n.title.lower(): n.id for n in self.nodes.values()}
        for a in plan.get("new_approaches") or []:
            if isinstance(a, dict) and a.get("title") and a["title"].lower() not in titles:
                self.n_n += 1
                n = Node(id=f"m{self.n_n:02d}", title=a["title"][:80], description=str(a.get("description", ""))[:300],
                         origin="navigator", created_gen=self.gen)
                self.nodes[n.id] = n
                titles[n.title.lower()] = n.id
        for r in plan.get("research") or []:
            if isinstance(r, dict):
                a = str(r.get("approach", ""))
                r["approach"] = a if a in self.nodes else titles.get(a.lower().removeprefix("new:").strip(), "")
        self.trace.emit("plan", gen=self.gen, plan=plan)
        return plan

    def role_ok(self, ok):
        """Swap the outer strategy back if a promoted strategy makes the outer roles fail twice in a row."""
        self.role_failures = 0 if ok else self.role_failures + 1
        if self.role_failures >= 2 and self.prev_outer:
            say("   the outer roles failed twice with the swapped-in strategy: swapping back")
            shutil.rmtree(self.outer_dir)
            shutil.copytree(self.prev_outer, self.outer_dir)
            self.trace.emit("unswap", gen=self.gen, to=str(self.prev_outer))
            self.prev_outer = None
            self.role_failures = 0

    def deep(self, plan):
        inc = self.cands[self.inc]
        assigned = [r for r in plan.get("research", []) if isinstance(r, dict)][: self.a.deep]
        a_lines = "\n".join(f"- {r['approach'] or 'a new approach'} [{self.nodes[r['approach']].title if r['approach'] in self.nodes else ''}] "
                            f"→ {r.get('mode', 'explore')} ({r.get('why', '')})" for r in assigned) or "- a new approach of your choice"
        finds = [c for c in self.cands.values() if c["origin"] == "wide" and c.get("result")]
        finds.sort(key=lambda c: -c["result"]["score"])
        user = (f"Outer generation {self.gen}.\n\n## The incumbent and its inner runs\n{self.report(self.inc)}\n\n"
                f"## The incumbent strategy's files\n{S.as_text(inc['dir'])}\n\n## The ledger\n{self.ledger_lines()}\n\n"
                + (f"## The Mutator's finds\n" + "\n".join(f"- {c['id']} {c.get('name')}: score {c['result']['score']:.2f}\n{S.diff_summary(self.cands[c['parent']]['dir'] if c.get('parent') else inc['dir'], c['dir'], 25)}" for c in finds[:2]) + "\n\n" if finds else "")
                + f"## Your assignments\n{a_lines}\n\nDesign {self.a.deep} experiments. Put the JSON block first.")
        exps = []
        try:
            rep = self.ask("researcher", user)
            data = roles.extract_json(rep.text) or {}
            exps = [e for e in data.get("experiments", []) if isinstance(e, dict) and (e.get("change") or e.get("feature"))]
            self.trace.emit("research", gen=self.gen, experiments=exps, analysis=roles.after_json(rep.text))
            self.role_ok(bool(exps))
        except Exception as exc:  # noqa: BLE001
            say(f"   outer researcher failed: {exc}")
            self.role_ok(False)
        out = []
        for e in exps[: self.a.deep]:
            node = e.get("approach") if e.get("approach") in self.nodes else ""
            cid = self.make_candidate(
                "deep", self.inc, "coder",
                f"## The strategy's files\n{S.as_text(inc['dir'])}\n\n## The experiment to write: `{e.get('name', '')}`\n\n"
                f"Why: {e.get('hypothesis', '')}\n\nWhat to change: {e.get('change') or e.get('feature')}\n\nWrite this edit.",
                name=str(e.get("name", "edit"))[:48], change=str(e.get("change") or e.get("feature")),
                hypothesis=e.get("hypothesis", ""), prediction=e.get("prediction") or {}, node=node, kind=e.get("kind", "improve"))
            if cid:
                out.append(cid)
        return out

    def scoreboard(self):
        inc_score = self.cands[self.inc]["result"]["score"]
        rows = []
        for c in self.cands.values():
            if c.get("result") and c["id"] != self.inc:
                rows.append(f"- {c['id']} {c.get('name', '')}: changed {', '.join(c.get('changed', [])) or '-'} → score "
                            f"{c['result']['score']:.2f} ({c['result']['score'] - inc_score:+.2f} vs the incumbent)")
        return "\n".join(rows[-12:]) or "(nothing yet)"

    def wide(self, plan):
        mut = plan.get("mutate") if isinstance(plan.get("mutate"), dict) else {}
        parents = [p for p in (mut.get("vary") or []) if p in self.cands and self.cands[p].get("result")] or [self.inc]
        slots = (parents * self.a.wide)[: self.a.wide]
        out = []
        board = self.scoreboard()
        for parent in slots:
            p = self.cands[parent]
            user = (f"## The parent strategy {parent} (score {p['result']['score']:.2f})\n{S.as_text(p['dir'])}\n\n"
                    f"## Scoreboard: strategies already evaluated\n{board}\n\nMake one bold variation of the parent.")
            cid = self.make_candidate("wide", parent, "mutator", user, name="", change="", node=p.get("node", ""))
            if cid:
                out.append(cid)
        return out

    def make_candidate(self, origin, parent, role, user, **info):
        with self.lock:
            cid = self.new_id()
        cdir = self.dir / "candidates" / cid
        rec = {"id": cid, "dir": str(cdir), "origin": origin, "gen": self.gen, "parent": parent, **info}
        for attempt in range(2):
            try:
                rep = self.ask(role, user)
            except Exception as exc:  # noqa: BLE001
                rec.update(invalid=True, verdict="invalid", error=str(exc)[:300])
                break
            edits = S.parse_edits(rep.text)
            if not rec.get("name"):
                rec["name"] = roles.extract_name(rep.text, f"variant_{cid}")
            changed, errors = S.apply_edits(self.cands[parent]["dir"], cdir, edits)
            if not edits:
                errors.append("no <<<FILE>>> or <<<EDIT>>> blocks in the reply")
            if not errors:
                errors, notes = S.validate(cdir)
                rec["notes"] = notes
            if not errors and changed:
                rec["diff"] = S.diff_summary(self.cands[parent]["dir"], cdir, 60)
                tail = "\n".join(l for l in rep.text.split("<<<END>>>")[-1].splitlines()
                                 if l.strip() and not l.strip().startswith("name:"))
                if not tail:
                    tail = " ".join(l for l in rec["diff"].splitlines() if l.startswith(("+", "---")))
                rec.update(changed=changed, hash=S.digest_hash(cdir), change=rec.get("change") or roles.short(tail, 240))
                break
            rec["error"] = "; ".join(errors)[:600] or "nothing changed"
            user += (f"\n\nYour edit could not be used: {rec['error']}\nReply again with corrected blocks.")
        else:
            rec.update(invalid=True, verdict="invalid")
        if rec.get("error") and not rec.get("hash"):
            rec.update(invalid=True, verdict="invalid")
        with self.lock:
            self.cands[cid] = rec
        self.trace.emit("candidate", **{k: v for k, v in rec.items() if k != "dir"})
        return cid

    def supervise(self, cid, r):
        """A strategy crashed some inner runs: show the author the errors, let it repair once."""
        rec = self.cands[cid]
        errs = "\n\n".join(f"{c['problem']} r{c['seed']}:\n{c['error'][-1200:]}" for c in r["crashes"][:3])
        user = (f"## The strategy {cid}\n{S.as_text(rec['dir'])}\n\n## It crashed the inner engine\n{errs}\n\n"
                "Fix the strategy so the inner engine runs, keeping its idea. Reply with corrected blocks.")
        try:
            rep = self.ask("coder", user)
            changed, errors = S.apply_edits(rec["dir"], Path(rec["dir"] + "_fix"), S.parse_edits(rep.text))
            if not errors and changed and not S.validate(rec["dir"] + "_fix")[0]:
                shutil.rmtree(rec["dir"])
                shutil.move(rec["dir"] + "_fix", rec["dir"])
                rec["repaired"] = True
                self.trace.emit("supervise", gen=self.gen, candidate=cid, changed=changed)
                return True
        except Exception as exc:  # noqa: BLE001
            say(f"   supervisor failed: {exc}")
        return False

    def check_prediction(self, cid):
        c = self.cands[cid]
        pred = c.get("prediction") or {}
        metric, fam, d = pred.get("metric"), str(pred.get("family", "all")), str(pred.get("direction", "")).lower()
        inc_stats = self.cands[self.inc].get("stats", {})
        if not metric or not c.get("stats"):
            return
        probs = self.problems if fam in ("all", "", "None") else [fam]
        before = [inc_stats.get(p, {}).get(metric) for p in probs]
        after = [c["stats"].get(p, {}).get(metric) for p in probs]
        pairs = [(b, a) for b, a in zip(before, after) if isinstance(b, (int, float)) and isinstance(a, (int, float))]
        if not pairs:
            return
        b, a = statistics.mean(p[0] for p in pairs), statistics.mean(p[1] for p in pairs)
        held = a < b if d.startswith("down") else a > b
        c["prediction_outcome"] = {"metric": metric, "family": fam, "direction": d, "before": round(b, 3),
                                   "after": round(a, 3), "held": held, "checked": True}

    def promote(self, todo):
        inc = self.cands[self.inc]
        base = inc["result"]
        margin = max(self.a.margin, base.get("noise") or 0.0)
        best = None
        for cid in todo:
            c = self.cands[cid]
            r = c.get("result")
            if not r:
                continue
            gain = r["score"] - base["score"]
            held_ok = (base.get("held_out_score") is None or r.get("held_out_score") is None
                       or r["held_out_score"] >= base["held_out_score"] - margin)
            c["delta"] = round(gain, 2)
            c["verdict"] = "better" if gain > margin and held_ok else ("worse" if gain < -margin else "flat")
            if c["verdict"] == "better" and (best is None or gain > best[0]):
                best = (gain, cid)
        if best:
            cid = best[1]
            self.cands[self.inc]["verdict"] = "replaced"
            self.cands[cid]["verdict"] = "incumbent"
            self.prev_outer = self.dir / f"outer_strategy_before_g{self.gen}"
            shutil.copytree(self.outer_dir, self.prev_outer, dirs_exist_ok=True)
            shutil.rmtree(self.outer_dir)
            shutil.copytree(self.cands[cid]["dir"], self.outer_dir)     # the recursion: the outer loop now runs on it
            self.trace.emit("swap", gen=self.gen, old=self.inc, new=cid, gain=round(best[0], 2))
            say(f"   promoted {cid} (+{best[0]:.2f}); the outer loop now runs on it")
            self.inc = cid

    def update_nodes(self):
        for n in self.nodes.values():
            mine = [c for c in self.cands.values() if c.get("node") == n.id]
            n.features = [c["id"] for c in mine]
            deltas = [c.get("delta") for c in mine if c.get("delta") is not None]
            n.best_gain = max(deltas) if deltas else None
            if any(c.get("verdict") in ("better", "incumbent", "replaced") for c in mine):
                n.state = "promising"
            elif deltas:
                n.state = "unproven"

    def save(self):
        data = {"incumbent": self.inc, "gen": self.gen,
                "candidates": [{k: v for k, v in c.items()} for c in self.cands.values()],
                "nodes": [n.record() for n in self.nodes.values()]}
        (self.dir / "state.json").write_text(json.dumps(data, indent=1, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--strategy", default=str(ROOT / "helix3" / "strategy"), help="the starting strategy")
    ap.add_argument("--problems", default="binpack1d,knapsack,tsp,scheduling")
    ap.add_argument("--held-out", default="coloring")
    ap.add_argument("--inner-generations", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--outer-generations", type=int, default=10)
    ap.add_argument("--deep", type=int, default=2, help="Researcher candidates per outer generation")
    ap.add_argument("--wide", type=int, default=2, help="Mutator candidates per outer generation")
    ap.add_argument("--parallel", type=int, default=4, help="inner runs at the same time")
    ap.add_argument("--workers", type=int, default=None, help="fitter processes per inner run")
    ap.add_argument("--margin", type=float, default=1.0, help="minimum score gain to promote")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--out", default=None)
    ap.add_argument("--fake-inner", action="store_true", help="inner runs without model calls (tests the outer loop)")
    ap.add_argument("--resume", default=None, help="continue an interrupted meta run from its folder")
    a = ap.parse_args(argv)
    Outer(a).run()


if __name__ == "__main__":
    main()
