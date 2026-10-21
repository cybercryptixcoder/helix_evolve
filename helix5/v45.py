"""v4.5: v4's Atlas, solidified with what the v4 overnight run showed.

What stays from Atlas (helix4/memory.py): the immutable log, the tree of attempts, the findings graph written by the
Distiller with code-checked evidence, the map with the last generation in full, and two-step navigation.

What changes, and why (evidence from results/v4, October 20-21):
1. Its own recent reasoning comes back. Atlas showed the planner a map but not what it had been thinking; the Journal
   (which did) produced the cleanest example of continuity. v4.5 shows the planner its last 3 analyses, each bet, the
   if/then it committed to, and what came of it.
2. If/then follow-up (from the v5 idea): every experiment states what to do next if it gains and if it doesn't.
3. A computed progress check, and an escape rule. Stalled v4 runs polished the same construction for 5-10
   generations; the planner put all 3 experiments on the current best in most generations. After `stall_gens`
   generations without a rise of 1e-4, at least one experiment must start fresh or leave the best line (enforced by
   the engine).
4. Real gains only. A finding counts as supported only by gains of at least 1e-5 (v4 counted +1e-9 polishing).
5. Engine fixes shared with v5: fresh starts, 8 printed lines back, unused budget stated, coders told to use the whole
   budget and return the best they found.
"""
from __future__ import annotations

import json

from helix4.archive import short
from helix4.memory import Atlas, best_block, header
from helix5 import prompts as P
from helix5.evaluate import GAIN_EPS, gain_label


def outcome(p):
    if p is None:
        return "missing"
    if not p.valid:
        return "error"
    if p.delta is None:
        return "fresh" if p.plan and p.plan.get("fresh") else "seed"
    return "gain" if p.delta >= GAIN_EPS else "no gain"


def result_text(p):
    if p is None:
        return "(no result)"
    if not p.valid:
        return f"FAILED: {short(p.error, 140)}"
    if p.delta is None:
        return f"{p.score:.6f} (fresh start)"
    return f"{p.score:.6f} ({p.delta:+.6f}, {gain_label(p.delta)})"


class AtlasPlus(Atlas):
    name = "v45"

    # ---- statuses count only real gains
    def status(self, f):
        outs = [outcome(self.run.archive.programs.get(p)) for p in f["evidence"]]
        gains = outs.count("gain")
        bad = outs.count("no gain") + outs.count("error")
        if f["kind"] == "question":
            return "open" if not (gains or bad) else f"tested ({gains} gained, {bad} didn't)"
        if f["kind"] == "fails":
            st = "supported" if bad and not gains else "mixed" if bad and gains else "refuted" if gains else "untested"
        else:
            st = "supported" if gains and gains >= bad else "mixed" if gains else "refuted" if bad else "untested"
        return f"{st}: {gains} gained, {bad} didn't"

    # ---- its own recent reasoning, with what came of each bet
    def recent_reasoning(self, gen, k=3):
        path = self.run.dir / "plans.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
        rows = [r for r in rows if gen - k <= r["gen"] < gen]
        if not rows:
            return ""
        by_eid = {p.plan.get("eid"): p for p in self.run.archive.programs.values() if p.plan and p.plan.get("eid")}
        out = ["## Your recent reasoning, and what came of it"]
        for r in rows:
            pl = r.get("plan") or {}
            out.append(f"### Generation {r['gen']}\nYou wrote: {short(pl.get('analysis'), 700)}")
            for e in r.get("experiments", []):
                p = by_eid.get(e.get("eid"))
                tag = " [fresh start]" if e.get("fresh") else ""
                out.append(f"- {p.id if p else '?'} on {e.get('base')}{tag}: bet: {short(e.get('hypothesis'), 160)}\n"
                           f"  if it gains: {short(e.get('if_gain'), 120)} | if not: {short(e.get('if_not'), 120)}\n"
                           f"  -> {result_text(p)}")
        return "\n".join(out)

    def plan(self, gen):
        run = self.run
        stall = run.stall(gen)
        system = P.RESEARCHER45_SYSTEM.format(k=run.cfg.deep, budget=run.cfg.budget)
        base = (header(run, gen) + "\n" + best_block(run) + "\n\n" + run.progress_block(gen) + "\n\n" + self.map(gen))
        rr = self.recent_reasoning(gen)
        if rr:
            base += "\n\n" + rr
        opened, why, asked = [], "", []
        if run.archive.programs and gen > 1:
            nav = run.call("navigator", system, base + "\n\n" + P.NAVIGATOR_ASK.format(k=run.cfg.open_k),
                           temperature=0.4, max_tokens=800, effort="none", gen=gen)
            js = P.extract_json(nav) or {}
            asked = [str(x).strip() for x in (js.get("open") or []) if isinstance(x, (str, int))][: run.cfg.open_k]
            why = str(js.get("why", ""))[:300]
            for item in asked:
                if item in run.archive.programs:
                    opened.append(self.open_program(item))
                elif item in self.findings:
                    opened.append(self.open_finding(item))
        user = base
        if opened:
            user += "\n\n## What you opened\n" + "\n\n".join(opened)
        rule = P.ESCAPE_RULE.format(stall=stall) if stall >= run.cfg.stall_gens else ""
        user += "\n\n" + P.PLAN45_FORMAT.format(k=run.cfg.deep, rule=rule)
        plan, info = run.researcher(system, user, gen)
        info.update(opened=asked, open_why=why, stall=stall)
        return plan, info

    def scheduled(self, gen, plan, exps):
        pass

    def update(self, gen, plan, children):
        # the Distiller sees gain labels through the feedback lines; statuses use real gains (status above)
        return super().update(gen, plan, children)
