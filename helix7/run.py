"""One Helix v7 run: v4's search, with exploration that rises when the record stalls and falls when it climbs, and
nothing ever closed (docs/V7_DESIGN.md).

    python -m helix7.run --seed 1 --gens 30 --out runs/v7/v7-s1
    python -m helix7.run --out runs/v7/v7-s1                     # resumes (state.json is there)
    python -m helix7.run --gens 2 --fake --out /tmp/x            # no model calls

Kept from v4 (helix4): the roles (Researcher with its Navigator, Coders, Mutator, Distiller), the two loops (3 planned
experiments and 3 mutations a generation), the Atlas with its tree of attempts, children that start from their base's
construction, and parents for the wide loop sampled from the whole archive.
Kept from v4.7 (helix47): alternative constructions, the noise floor, failures scoped to the construction they were
tried on, targets instead of confirm-or-refute, no countdown, programs shown up to 30,000 characters, 16,000-token
replies, constructions up to 1M steps.

New:
- Every program is on a track. The main track is the one holding the best program; side tracks are opened by
  exploration experiments. Nothing is closed: the main track always keeps at least one planned experiment, however
  long it has been flat, and every program stays a possible base.
- Exploration follows progress. The stall s is the number of generations since the record last rose above the floor
  (a warm start counts as a record), and T the run's own typical gap between records (the median of the last 8 gaps;
  3 until there are two). s <= T: no exploration, all planned experiments are main (v4). T < s <= 2T + 1: one
  exploration slot. s > 2T + 1: two. A cold start explores twice in each of its first 3 generations.
- An exploration slot first continues a live side track (best first), else opens a new one, rotating its kind:
  revive (an approach that failed on an earlier construction, re-applied to the current best), backtrack (an earlier
  state: an alternative construction, the point before a big gain on the record's lineage, another branch, a paused
  track's best), or bold (a genuinely different construction, from any base, Code Zero included).
- A side track is judged against its own best. It gets a follow-up after it opens even if it starts worse
  (`track_patience`), and stays live while it gains. A paused track's programs stay bases; a wide-loop gain on it
  makes it live again. A side track that beats the record becomes the main track.
- The wide loop broadens with the stall: flatter parent sampling, and at the highest level one parent from a side
  track or an alternative.
- On a noisy problem (the VRP) the floor is raised to the evaluator's measured noise (`calibrate`).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import statistics
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from helix4 import prompts as P4
from helix4.archive import Archive, Program, make_diff, short
from helix4.llm import FakeLLM, LLM
from helix4.run import fake_answer as fake_answer4
from helix47.evaluate import evaluate
from helix47.run import FAKE_CODE, ProblemView, Run as Run47, UPPER_BOUNDS
from helix7 import prompts as P
from helix7.memory import Atlas7, outcome

FIRST_TRACK = "T1"
EXPLORE = ("revive", "backtrack", "bold")
KIND_WORDS = {"revive": "revive an earlier approach", "backtrack": "go back to an earlier state",
              "bold": "a genuinely different construction", "track": "continue a side track"}
FALLBACK = {"main": "Improve the base program in the way you judge most promising.",
            "revive": "Re-apply the approach of the finding named below to this construction, adapted to it.",
            "backtrack": "Push this earlier state in a direction different from the one its descendants took.",
            "bold": "Build a genuinely different kind of construction or search, not a refinement of the base.",
            "track": "Continue this side track: improve its best program."}


@dataclass
class Config:
    condition: str = "v7"
    seed: int = 1
    gens: int = 20
    deep: int = 3
    wide: int = 3
    budget: float = 30.0
    researcher_effort: str = "low"
    open_k: int = 6
    mem_mb: int = 1500
    problem: str = "ac2"
    label: str = ""
    # ---- from v4.7
    gain_floor: float = 1e-6         # a change is a gain only above this, relative (raised to the measured noise)
    branch_gap: float = 0.01         # another branch: it split from the record's lineage this much lower (relative)
    alt_min_ratio: float = 0.9       # an alternative is kept if it scores at least this times its start's score
    max_n: int = 1_000_000
    best_code_chars: int = 12000     # how much of the best program the planner sees
    map_findings: int = 45
    map_fails: int = 10
    map_works_best: int = 12
    map_works_new: int = 8
    map_questions: int = 6
    open_evidence: int = 12
    # ---- v7
    typical_default: float = 3.0     # the typical gap between records until the run has seen two gaps
    typical_max: float = 12.0
    typical_window: int = 8          # the typical gap is the median of this many latest gaps
    track_patience: int = 1          # follow-up generations a side track gets without beating its own best
    early_gens: int = 3              # a cold start explores twice in each of its first generations
    calibrate: int = 0               # extra evaluations of the starting program, to measure the evaluator's noise
    wide_alpha_stalled: float = 0.5  # the wide loop's rank exponent when stalled (v4: 1.0)
    revive_options: int = 8
    backtrack_options: int = 6
    tree_chars: int = 40000          # the tree of attempts is cut down past this


class Run(Run47):
    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print, problem=None):
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
        self.warm = (state or {}).get("warm")
        self.warm_gen = (state or {}).get("warm_gen")
        self.warm_source = (state or {}).get("warm_source")
        if gens:
            cfg.gens = gens
        self.cfg = cfg
        self.name = cfg.label or self.dir.name
        self.problem = problem or ProblemView(importlib.import_module(f"helix4.problems.{cfg.problem}"), cfg.max_n)
        self.problem_text = self.problem.DESCRIPTION
        self.upper_bound = UPPER_BOUNDS.get(cfg.problem)
        self.archive = Archive(self.dir)
        self.lock = threading.Lock()
        self.trace_lock = threading.Lock()
        self.trace = (self.dir / "trace.jsonl").open("a")
        self.llm = llm if llm is not None else LLM(on_call=self.record)
        if getattr(self.llm, "on_call", None) is None:
            self.llm.on_call = self.record
        nf = self.dir / "noise.json"
        self.noise = float(json.loads(nf.read_text()).get("rel", 0.0)) if nf.exists() else 0.0
        self.memory = Atlas7(self)
        self.tracks, self.revived, self.lines, self.main = {}, [], [], None
        if state:
            dropped = self.archive.truncate(self.gen_done)
            self.memory.truncate(self.gen_done)
            for f in ("plans.jsonl", "history.jsonl", "tracks.jsonl"):
                self._truncate_jsonl(self.dir / f)
            rows = self._jsonl("tracks.jsonl")
            if rows:
                self.tracks = {t["id"]: t for t in rows[-1]["tracks"]}
                self.revived = rows[-1].get("revived", [])
                self.main = rows[-1].get("main")
            self.log(f"[{self.name}] resuming after generation {self.gen_done} (dropped {dropped} programs of the "
                     f"unfinished one)")
        self.sync_tracks()

    # ---------------------------------------------------------------- bookkeeping
    def floor(self, ref):
        return max(self.cfg.gain_floor, self.noise) * max(abs(ref or 0.0), 1e-12)

    def checkpoint(self, gen):
        self.gen_done = gen
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"gen_done": gen, "config": asdict(self.cfg), "t": time.time(), "version": "v7",
                                   "warm": self.warm, "warm_gen": self.warm_gen, "warm_source": self.warm_source},
                                  indent=1))
        os.replace(tmp, self.state_path)

    def seed_program(self):
        return next((p for p in self.archive.programs.values() if p.role == "seed"), None) or self.archive.best()

    # ---------------------------------------------------------------- tracks
    def track_of(self, p):
        if p is None:
            return None
        pl = p.plan or {}
        return pl.get("track") or pl.get("line") or FIRST_TRACK

    line_of = track_of

    def main_track(self):
        """The track holding the record. It changes only when another track's program beats the main track's best by
        more than the floor (a polish below the floor doesn't move it)."""
        if self.main is None or self.main not in self.tracks:
            self.main = self.track_of(self.archive.best())
        return self.main

    def live(self, t):
        """A side track is live (it gets an exploration slot when there is one) until it has had `track_patience`
        follow-ups without beating its own best."""
        return t["id"] != self.main_track() and t.get("misses", 0) < self.cfg.track_patience

    def priority(self, t):
        """Live tracks in order: those still owed their first follow-up, then by how much of their gap to the record
        their last gain closed (so a track climbing fast towards the record goes first, and one creeping far below
        it goes last)."""
        return (0 if t.get("closing") is None else 1, -(t.get("closing") or 0.0),
                -(t["best"] if t["best"] is not None else -1e300), t["id"])

    def sync_tracks(self):
        """Create the tracks that programs name but that have no record yet: the first track of a cold start, and the
        lines of an earlier v4.7 run (which start paused)."""
        names = {}
        for row in self._jsonl("lines.jsonl")[-1:]:
            names = {ln["id"]: ln for ln in row.get("lines", [])}
        for p in sorted(self.archive.programs.values(), key=lambda q: int(q.id[1:])):
            tid = self.track_of(p)
            t = self.tracks.get(tid)
            if t is None:
                ln = names.get(tid)
                src = (f"line {tid} of the earlier v4.7 run (from {ln['source']})" if ln else
                       "the start of the run" if tid == FIRST_TRACK else f"line {tid} of an earlier run")
                legacy = tid != FIRST_TRACK
                t = self.tracks[tid] = {"id": tid, "kind": "line" if legacy else "seed",
                                        "root": ln["root"] if ln and ln.get("root") else p.id,
                                        "opened": ln["started"] if ln and ln.get("started") is not None else p.gen,
                                        "source": src, "revives": None, "best": None, "best_id": None,
                                        "misses": self.cfg.track_patience, "last_gain": p.gen, "closing": 0.0,
                                        "exps": 0, "synced": True}
            if t.get("synced") and p.valid and p.score is not None and (t["best"] is None or p.score > t["best"]):
                t["best"], t["best_id"], t["last_gain"] = p.score, p.id, p.gen
        if self.archive.best() is not None:
            self.main_track()

    def track_members(self, t):
        """The valid programs of a track, best first."""
        return sorted((p for p in self.archive.valid() if self.track_of(p) == t["id"]), key=lambda p: (-p.score, p.id))

    def open_track(self, gen, kind, root, revives=None):
        n = len(self.tracks) + 1
        while f"T{n}" in self.tracks:
            n += 1
        tid = f"T{n}"
        src = {"revive": f"a revive of {revives or 'an earlier approach'} on {root}", "backtrack": f"a backtrack to {root}",
               "bold": f"a bold experiment from {root}"}[kind]
        self.tracks[tid] = {"id": tid, "kind": kind, "root": root, "opened": gen, "source": src, "revives": revives,
                            "best": None, "best_id": None, "misses": 0, "last_gain": gen, "closing": None, "exps": 0}
        return tid

    def update_tracks(self, gen, children, exps, prev_best):
        events = []
        had = Counter(x["track"] for x in exps)
        main = self.main_track()
        for tid, t in self.tracks.items():
            t.pop("synced", None)
            if tid in had:
                t["exps"] = t.get("exps", 0) + had[tid]
            mine = [c for c in children if c is not None and c.valid and self.track_of(c) == tid]
            top = max(mine, key=lambda c: c.score, default=None)
            if top is not None and (t["best"] is None or top.score > t["best"] + self.floor(t["best"])):
                if t["best"] is not None:
                    gap = max(prev_best.score - t["best"], self.floor(t["best"]))
                    t["closing"] = round(min((top.score - t["best"]) / gap, 1e6), 6)
                    if tid != main:
                        events.append(f"{tid} gained ({t['best']:.6f} -> {top.score:.6f})")
                t["best"], t["best_id"], t["last_gain"], t["misses"] = top.score, top.id, gen, 0
            elif tid in had and t["opened"] != gen:
                t["misses"] = t.get("misses", 0) + 1
                if t["misses"] == self.cfg.track_patience and tid != main:
                    events.append(f"{tid} paused (no gain on its own best)")
        best = self.archive.best()
        bt = self.track_of(best)
        if bt != main and bt in self.tracks:
            ms = max((p.score for p in self.track_members(self.tracks[main])), default=None)
            if ms is None or best.score > ms + self.floor(ms):
                events.append(f"{bt} took the record ({best.score:.6f}): it is now the main track, and {main} a side "
                              f"track")
                self.main = bt
        for tid in had:
            if self.tracks[tid]["opened"] == gen:
                events.append(f"{tid} opened ({self.tracks[tid]['source']})")
        return events

    # ---------------------------------------------------------------- progress
    def records(self):
        """(the generation the count starts from, the generations at which the record rose above the floor)."""
        rows = sorted((r for r in self._jsonl("history.jsonl") if r.get("best") is not None), key=lambda r: r["gen"])
        if not rows:
            return 0, []
        start, ref, out = rows[0]["gen"], rows[0]["best"], []
        for r in rows[1:]:
            if r["best"] > ref + self.floor(ref):
                out.append(r["gen"])
                ref = r["best"]
        return start, out

    def typical_gap(self):
        start, recs = self.records()
        pts = [start] + recs
        gaps = [b - a for a, b in zip(pts, pts[1:])][-self.cfg.typical_window:]
        if len(gaps) < 2:
            return float(self.cfg.typical_default)
        return float(min(max(statistics.median(gaps), 1.0), self.cfg.typical_max))

    def last_record(self):
        """The generation of the last record (a warm start counts as one)."""
        start, recs = self.records()
        return max([start] + recs[-1:] + ([self.warm_gen] if self.warm_gen is not None else []))

    def stall(self, gen):
        """Completed generations since the last record, before generation `gen`."""
        return max(0, gen - 1 - self.last_record())

    def level(self, gen):
        s, typ = self.stall(gen), self.typical_gap()
        return (2 if s > 2 * typ + 1 else 1 if s > typ else 0), s, typ

    # ---------------------------------------------------------------- exploration candidates
    def revive_candidates(self):
        """Findings tried on other constructions than the current best: failures first (round-robin over the
        constructions they were tried on, the closest to the record first), then two that worked elsewhere."""
        m, best = self.memory, self.archive.best()
        since = self.last_record()
        done = {r[0] for r in self.revived if r[2] > since}       # each finding is revived once per record
        lineage = self.archive.lineage(best.id, depth=100000)
        mine = {q.id for q in lineage}                                         # what the best is built from
        same = {q.id for q in lineage if q.valid and best.score - q.score <= self.floor(q.score)}   # no real gain since
        groups, works = {}, []
        for fid, f in m.findings.items():
            if fid in done or f["kind"] == "question":
                continue
            pid, sc = m.scope(f)
            if pid is None or pid in same:
                continue
            st = m.status(f).split(":")[0]
            if f["kind"] == "fails" and st in ("held", "mixed"):
                groups.setdefault(pid, []).append((len(f["evidence"]), int(fid[1:]), fid, sc))
            elif f["kind"] in ("works", "mechanism") and st in ("supported", "mixed") \
                    and not any(e in mine for e in f["evidence"]):     # (an idea already in the best's lineage is in it)
                works.append((m.best_gain(f) or 0.0, fid))
        k = self.cfg.revive_options
        order = sorted(groups.values(), key=lambda g: -(g[0][3] if g[0][3] is not None else -1e300))
        order = [sorted(g, key=lambda x: (-x[0], -x[1])) for g in order]
        fails, i = [], 0
        while len(fails) < k and any(i < len(g) for g in order):
            fails += [g[i][2] for g in order if i < len(g)]
            i += 1
        w = [fid for _, fid in sorted(works, key=lambda x: -x[0])][:2]
        out = fails[: k - len(w)] + w
        return out[:k]

    def other_branch(self, p, b):
        """True if p is not on b's path and split from it at a program at least `branch_gap` (relative) below b."""
        a = self.archive
        anc = {q.id for q in a.lineage(b.id, depth=100000)}
        for q in reversed(a.lineage(p.id, depth=100000)):
            if q.id in anc:
                return q.id != p.id and q.score is not None and q.score <= b.score - self.cfg.branch_gap * abs(b.score)
        return True

    def backtrack_candidates(self):
        a, best = self.archive, self.archive.best()
        used = {t["root"] for t in self.tracks.values()} | {best.id}
        out, seen = [], set()

        def add(p, why, cap):
            if (p is not None and p.valid and p.id not in used and p.id not in seen
                    and sum(1 for _, w in out if w.startswith(why[:12])) < cap):
                out.append((p.id, why))
                seen.add(p.id)

        for p in sorted((p for p in a.valid() if p.role == "alt"), key=lambda p: (-p.score, p.id)):
            add(p, f"an alternative construction (handed back by {p.parent})", 2)
        lin = a.lineage(best.id, depth=100000)
        jumps = sorted(((q.score - p.score, p) for p, q in zip(lin, lin[1:]) if p.valid and q.valid and p.role != "seed"
                        and q.score - p.score > self.floor(p.score)), key=lambda x: -x[0])
        for g, p in jumps:
            add(p, f"the state just before a gain of {g:+.6f} on the best program's lineage", 2)
        for t in sorted(self.tracks.values(), key=lambda t: -(t["best"] if t["best"] is not None else -1e300)):
            if t["id"] != self.main_track() and not self.live(t) and t["best_id"]:
                add(a.programs.get(t["best_id"]), f"the best program of side track {t['id']} (paused)", 2)
        found = 0
        for p in a.ranked():
            if found >= 2:
                break
            if p.role not in ("seed", "alt") and p.id not in used and p.id not in seen and self.other_branch(p, best):
                add(p, "the best program of another branch", 2)
                found += 1
        return out[: self.cfg.backtrack_options]

    # ---------------------------------------------------------------- slots
    def make_slots(self, gen, n_explore):
        slots = [{"kind": "main"} for _ in range(self.cfg.deep - n_explore)]
        live = sorted((t for t in self.tracks.values() if self.live(t)), key=self.priority)[:n_explore]
        if n_explore >= 2 and len(live) == n_explore and gen % 2 == 0:
            live = live[:-1]          # breadth: with two exploration slots, a new direction every other generation
        opened = Counter(t["kind"] for t in self.tracks.values())
        used = []
        for _ in range(n_explore):
            if live:
                slots.append({"kind": "track", "track": live.pop(0)["id"]})
                continue
            avail = [k for k in EXPLORE if k not in used and (k == "bold" or (k == "revive" and self.revive_candidates())
                                                             or (k == "backtrack" and self.backtrack_candidates()))]
            kind = min(avail, key=lambda k: (opened[k], EXPLORE.index(k))) if avail else "bold"
            used.append(kind)
            opened[kind] += 1
            slots.append({"kind": kind})
        best = self.archive.best()
        for n, s in enumerate(slots, 1):
            s["n"] = n
            k = s["kind"]
            if k == "main":
                s["text"] = P.SLOT_TEXT["main"].format(n=n)
            elif k == "revive":
                s["options"] = self.revive_candidates()
                opts = "\n".join(f"- {self.memory.finding_line(f, 220)}" for f in s["options"])
                s["text"] = P.SLOT_TEXT["revive"].format(n=n, best=best.id, options=opts)
            elif k == "backtrack":
                c = self.backtrack_candidates()
                s["options"] = [pid for pid, _ in c]
                opts = "\n".join(f"- {self.archive.programs[pid].line()}: {why}; {short(self.archive.programs[pid].intent, 110)}"
                                 for pid, why in c)
                s["text"] = P.SLOT_TEXT["backtrack"].format(n=n, options=opts)
            elif k == "bold":
                s["text"] = P.SLOT_TEXT["bold"].format(n=n, seed=self.bold_seed_text())
            else:
                t = self.tracks[s["track"]]
                mem = self.track_members(t)
                newest = sorted(mem, key=lambda p: -int(p.id[1:]))[:3]
                show = list({p.id: p for p in mem[:3] + newest}.values())
                opts = "\n".join(f"- {p.line()}: {short(p.intent, 110)}" for p in show) or \
                    f"- (its first program failed: start again from its root, {t['root']})"
                if t.get("closing") is None:
                    why = (f"it was opened at generation {t['opened']} ({t['source']}) and is owed a follow-up, even if "
                           f"it started below its base")
                else:
                    why = f"it gained at generation {t['last_gain']} ({t['source']})"
                s["options"] = [p.id for p in mem] or [t["root"]]
                score = f"{t['best']:.6f}" if t["best"] is not None else "none yet"
                s["text"] = P.SLOT_TEXT["track"].format(n=n, track=t["id"], why=why, options=opts,
                                                        best=t["best_id"] or t["root"], score=score)
        return slots

    def bold_seed_text(self):
        seed = self.seed_program()
        return f"{seed.id} (Code Zero, the trivial starting program, to build from nothing)"

    def tracks_view(self):
        main = self.main_track()
        side = [t for t in self.tracks.values() if t["id"] != main and (t["best_id"] or t["kind"] != "seed")]
        if not side:
            return ""
        side = sorted(side, key=lambda t: (not self.live(t), self.priority(t) if self.live(t) else (-t["last_gain"],)))[:10]
        rows = []
        for t in side:
            b = f"best {t['best_id']} ({t['best']:.6f})" if t["best_id"] else "no valid program yet"
            st = "live (it gets the next exploration slot)" if self.live(t) else "paused (its programs stay bases)"
            rows.append(f"- {t['id']}: {t['source']}, opened at generation {t['opened']}; {b}; {st}")
        more = len([t for t in self.tracks.values() if t["id"] != main]) - len(side)
        return (f"## Side tracks (the main track, {main}, holds the record)\n" + "\n".join(rows)
                + (f"\n({more} older side tracks not shown)" if more > 0 else ""))

    def brief(self, gen, slots):
        parts = [self.tracks_view()] if self.tracks_view() else []
        parts.append("## This generation's experiments, slot by slot\n" + "\n".join(s["text"] for s in slots))
        return "\n\n".join(parts)

    # ---------------------------------------------------------------- the planner's experiments
    def experiments(self, plan, slots, gen=None):
        gen = gen if gen is not None else self.gen_done + 1
        raw = [e for e in ((plan or {}).get("experiments") or [])
               if isinstance(e, dict) and (e.get("change") or e.get("hypothesis"))]
        by_slot, rest = {}, []
        for e in raw:
            try:
                n = int(e.get("slot"))
            except (TypeError, ValueError):
                n = None
            if n is not None and 1 <= n <= len(slots) and n not in by_slot:
                by_slot[n] = e
            else:
                rest.append(e)
        return [self.assign(gen, s, by_slot.get(s["n"]) or (rest.pop(0) if rest else None)) for s in slots]

    def assign(self, gen, s, e):
        a, best, k = self.archive, self.archive.best(), s["kind"]
        if e is None:
            x = {"base": None, "hypothesis": "(no plan: the researcher's reply was unusable)", "change": FALLBACK[k],
                 "prediction": "", "builds_on": [], "fallback": True}
        else:
            x = {key: e.get(key) for key in ("base", "hypothesis", "change", "prediction", "builds_on")}
        if not isinstance(x.get("builds_on"), list):
            x["builds_on"] = [str(x["builds_on"])] if x.get("builds_on") else []
        x["slot"], x["kind"] = s["n"], k
        req = str(x.get("base") or "").strip()
        p = a.programs.get(req)
        ok = p is not None and p.valid
        if k == "main":
            base = req if ok else best.id
        elif k == "revive":
            base = best.id
            rv = str((e or {}).get("revives") or "").strip()
            done = {r[0] for r in self.revived if r[2] > self.last_record()}
            if rv in self.memory.findings and rv not in done:
                x["revives"] = rv
            else:
                if rv:
                    x["revives_requested"] = rv
                x["revives"] = (s.get("options") or [None])[0]
                if e is None and x["revives"]:
                    x["change"] += f" ({x['revives']}: {short(self.memory.findings[x['revives']]['claim'], 300)})"
        elif k == "backtrack":
            opts = s.get("options") or [best.id]
            base = req if req in opts else opts[0]
        elif k == "bold":
            base = req if ok else self.seed_program().id
        else:
            t = self.tracks[s["track"]]
            opts = s.get("options") or [t["best_id"] or t["root"]]
            base = req if req in opts else opts[0]
        if req and req != base:
            x["base_requested"] = req
        x["base"] = base
        if k == "main":
            x["track"] = self.track_of(a.programs[base])
        elif k == "track":
            x["track"] = s["track"]
        else:
            x["track"] = self.open_track(gen, k, base, x.get("revives"))
            if k == "revive" and x.get("revives"):
                self.revived.append([x["revives"], best.id, gen])
        return x

    # ---------------------------------------------------------------- roles (hooks a problem plug-in can override)
    def researcher_system(self, k):
        return P.RESEARCHER_SYSTEM.format(k=k, budget=self.cfg.budget)

    def best_code_chars(self):
        return self.cfg.best_code_chars

    def coder_system(self):
        return P.CODER_SYSTEM

    def mutator_system(self):
        return P.MUTATOR_SYSTEM

    def task_text(self, whose):
        return f"budget_seconds will be {self.cfg.budget:.0f}; `start` will be {whose} construction."

    def evaluate_child(self, p, parent, code):
        """Runs the program from its base's construction and fills in p. Returns (construction, alternative)."""
        res = evaluate(self.problem, code, self.archive.construction(parent.id), self.cfg.budget, self.cfg.mem_mb)
        p.valid, p.score, p.start_score, p.delta = res["valid"], res["score"], res["start_score"], res["delta"]
        p.feedback, p.error, p.cpu, p.n = res["feedback"], res["error"], res["cpu"], res["n"]
        return res["construction"], res.get("alternative")

    def child(self, gen, role, parent, code, intent, plan, summary):
        p = Program(id="", gen=gen, role=role, parent=parent.id, intent=intent, code=code or "", plan=plan or {},
                    summary=summary)
        if code is None:
            p.error = "no program in the model's reply"
            return self.add(p), None
        dup = self.archive.duplicate(code, parent.id)
        if dup:
            p.error, p.duplicate_of = f"identical to {dup} (same code on the same base): not run again", dup
            return self.add(p), None
        p.diff = make_diff(parent.code, code)
        construction, alt = self.evaluate_child(p, parent, code)
        if p.valid and p.delta is not None and 0 < p.delta <= self.floor(p.start_score) and p.feedback:
            p.feedback = [p.feedback[0] + " (below the noise floor: counts as no gain)"] + p.feedback[1:]
        keep = None
        if p.valid and alt is not None:
            ref = p.start_score if p.start_score is not None else p.score
            if alt["score"] >= self.cfg.alt_min_ratio * ref:
                keep = alt
                p.feedback = p.feedback + [f"it also handed back an alternative construction scoring {alt['score']:.6f}, "
                                           f"kept as its own program"]
            else:
                p.feedback = p.feedback + [f"its alternative construction scored {alt['score']:.6f}, below "
                                           f"{self.cfg.alt_min_ratio:g} of its start's score: not kept"]
        p = self.add(p, construction)
        a = None
        if keep is not None:
            a = Program(id="", gen=gen, role="alt", parent=p.id, code=p.code, summary=p.summary,
                        intent=f"alternative construction handed back by {p.id} ({short(intent, 150)})",
                        plan={"alt_of": p.id, "track": self.track_of(p)},
                        valid=True, score=keep["score"], start_score=p.start_score,
                        delta=(keep["score"] - p.start_score) if p.start_score is not None else None,
                        feedback=[f"score {keep['score']:.6f} (an alternative handed back by {p.id})"]
                        + keep["feedback"][1:], cpu=0.0, n=keep["n"])
            a = self.add(a, keep["construction"])
        return p, a

    def deep_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            note = ""
            if exp.get("kind", "main") != "main":
                note = "\n\n" + P.EXPLORE_CODER_NOTE.format(kind=KIND_WORDS[exp["kind"]])
                f = self.memory.findings.get(exp.get("revives") or "")
                if f is not None:
                    pid, sc = self.memory.scope(f)
                    note += (f"\nThe earlier approach ({exp['revives']}, tried on {pid}'s construction"
                             + (f", which scored {sc:.6f}" if sc is not None else "") + f"): {f['claim']}")
            task = self.task_text("the base's")
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Target: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. {task}{note}\n\n"
                    f"{P4.CODE_FORMAT}")
            code, summary = self.write_code("coder", self.coder_system(), user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp, summary)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}")), None

    def wide_child(self, gen, parent, inspiration):
        tid = self.track_of(parent)
        try:
            user = f"{self.problem.DESCRIPTION}\n\n{self.program_block(parent, 'The program to improve')}\n\n"
            if inspiration is not None:
                user += (f"## Another strong program, for ideas: {inspiration.line()}\n```python\n"
                         f"{P4.clip(inspiration.code, 5000)}```\n\n")
            user += (f"Write an improved version of the program to improve. {self.task_text('its')}\n\n"
                     f"{P4.CODE_FORMAT}")
            code, summary = self.write_code("mutator", self.mutator_system(), user, gen)
            return self.child(gen, "wide", parent, code, summary or "(no summary)", {"track": tid}, summary)
        except Exception as exc:                                     # noqa: BLE001
            self.log(f"[{self.name}] gen {gen}: wide child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="wide", parent=parent.id, intent="(crashed)", code="",
                                    plan={"track": tid}, error=f"internal error: {exc}")), None

    def wide_parents(self, rng, pool, level):
        """v4's sampling over the whole archive; flatter when stalled, and at level 2 one parent off the main track."""
        if not pool:
            return []
        alpha = 1.0 if level == 0 else self.cfg.wide_alpha_stalled
        parents = [self.archive.sample_parent(rng, pool, alpha=alpha) for _ in range(self.cfg.wide)]
        if level >= 2 and parents:
            main = self.main_track()
            side = [p for p in pool if self.track_of(p) != main or p.role == "alt"]
            if side:
                parents[-1] = self.archive.sample_parent(rng, side, alpha=alpha)
        return parents

    # ---------------------------------------------------------------- the generation
    def seed(self):
        super().seed()
        self.calibrate()

    def calibrate(self):
        """Evaluates the starting program `calibrate` more times; the relative spread of its scores is the noise."""
        if self.cfg.calibrate <= 0 or (self.dir / "noise.json").exists():
            return
        p = self.archive.best()
        scores = [p.score]
        for i in range(self.cfg.calibrate):
            s = self.score_again(p, i)
            if s is not None:
                scores.append(s)
        self.write_noise(p, scores)

    def write_noise(self, p, scores):
        mean = sum(scores) / len(scores)
        rel = (max(scores) - min(scores)) / max(abs(mean), 1e-12) if len(scores) > 1 else 0.0
        self.noise = rel
        (self.dir / "noise.json").write_text(json.dumps({"program": p.id, "scores": scores, "rel": rel,
                                                         "floor": max(self.cfg.gain_floor, rel)}, indent=1))
        self.log(f"[{self.name}] calibration: {p.id} scored {', '.join(f'{s:.6f}' for s in scores)}: a gain counts "
                 f"above {100 * max(self.cfg.gain_floor, rel):.3f}% (relative)")

    def score_again(self, p, i):
        res = evaluate(self.problem, p.code, self.archive.construction(p.parent) if p.parent else None,
                       self.cfg.budget, self.cfg.mem_mb)
        return res["score"] if res["valid"] else None

    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        self.sync_tracks()
        prev_best = self.archive.best()
        lv, stall, typical = self.level(gen)
        early = self.warm_gen is None and gen <= self.cfg.early_gens
        n_explore = min(max(lv, 2 if early else 0), self.cfg.deep - 1)
        slots = self.make_slots(gen, n_explore)
        brief = self.brief(gen, slots)
        rng = random.Random(self.cfg.seed * 7919 + gen)
        pool = [p for p in self.archive.valid() if p.gen < gen]
        parents = self.wide_parents(rng, pool, max(lv, 1) if early else lv)
        top = sorted(pool, key=lambda p: -p.score)[:5]
        with ThreadPoolExecutor(max_workers=self.cfg.deep + self.cfg.wide) as ex:
            wide = []
            for par in parents:
                others = [q for q in top if q.id != par.id]
                wide.append(ex.submit(self.wide_child, gen, par, rng.choice(others) if others else None))
            plan, info = self.memory.plan(gen, slots, brief)
            exps = self.experiments(plan, slots, gen)
            deep = [ex.submit(self.deep_child, gen, e) for e in exps]
            pairs = [f.result() for f in deep + wide]
        children = [c for c, _ in pairs] + [a for _, a in pairs if a is not None]
        t_mem = time.time()
        mem_info = self.memory.update(gen, plan, children) or {}
        events = self.update_tracks(gen, children, exps, prev_best)
        best = self.archive.best()
        dc = [c for c, _ in pairs[: len(deep)]]
        wc = [c for c, _ in pairs[len(deep):]]
        alts = [a for _, a in pairs if a is not None]

        def best_of(cs):
            ok = [c.score for c in cs if c is not None and c.valid]
            return max(ok) if ok else None

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        record = best.score > prev_best.score + self.floor(prev_best.score)
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role, "best_track": self.track_of(best),
               "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": sum(1 for c in dc if outcome(c, self) == "gain"),
               "wide_gains": sum(1 for c in wc if outcome(c, self) == "gain"),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in dc + wc if c.duplicate_of), "new_best": record,
               "level": lv, "stall": stall, "typical_gap": typical, "early": early,
               "slots": [s["kind"] + (f":{s['track']}" if s["kind"] == "track" else "") for s in slots],
               "experiment_tracks": [e["track"] for e in exps], "track_events": events,
               "explore_best": best_of([c for c, e in zip(dc, exps) if e["kind"] != "main"]),
               "plan_parsed": info.get("parsed"), "plan_retried": info.get("retried"),
               "fallback_experiments": sum(1 for e in exps if e.get("fallback")),
               "base_fallbacks": sum(1 for e in exps if "base_requested" in e),
               "bases": [e["base"] for e in exps], "alternatives_kept": [a.id for a in alts],
               "builds_on_refs": len(refs),
               "builds_on_known": sum(1 for r in refs if str(r) in self.archive.programs or str(r) in self.memory.findings),
               "researcher_prompt_chars": info.get("prompt_chars"), "researcher_seconds": info.get("seconds"),
               "memory_seconds": round(time.time() - t_mem, 1), "calls": self.llm.calls - calls0,
               "seconds": round(time.time() - t0, 1), **self.memory.stats()}
        self._append("plans.jsonl", {"gen": gen, "plan": plan, "experiments": exps, "slots": slots, "info": info,
                                     "memory": mem_info})
        self._append("history.jsonl", row)
        self._append("tracks.jsonl", {"gen": gen, "main": self.main_track(), "tracks": list(self.tracks.values()),
                                      "revived": self.revived})
        self.checkpoint(gen)
        kinds = Counter(s["kind"] for s in slots)
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}, track {self.track_of(best)})"
                 f"{' RECORD' if record else ''}; stall {stall} (typical {typical:g}), level {lv}; slots "
                 + ", ".join(f"{n} {k}" for k, n in kinds.items())
                 + f"; deep {row['deep_gains']}/{len(dc)} gained, wide {row['wide_gains']}/{len(wc)} gained"
                 + (f"; {len(alts)} alternatives kept" if alts else "") + (f"; {'; '.join(events)}" if events else "")
                 + f"; {row['seconds']:.0f} s")
        return row

    def finish(self, seconds=None, stopped_at=None):
        best = self.archive.best()
        hist = self._jsonl("history.jsonl")
        progs = list(self.archive.programs.values())
        start, recs = self.records()
        summary = {"run": self.name, "version": "v7", "condition": self.cfg.condition, "seed": self.cfg.seed,
                   "gens": self.cfg.gens, "problem": self.cfg.problem, "budget": self.cfg.budget, "best": best.score,
                   "best_id": best.id, "best_n": best.n, "best_track": self.track_of(best),
                   "best_lineage": self.archive.lineage_line(best.id, depth=40),
                   "best_by_gen": [h["best"] for h in hist], "records_at": recs, "programs": len(progs),
                   "valid": sum(p.valid for p in progs), "calls": self.llm.calls,
                   "tokens_in": getattr(self.llm, "tokens_in", 0), "tokens_out": getattr(self.llm, "tokens_out", 0),
                   "memory": self.memory.stats(), "config": asdict(self.cfg), "seconds_this_session": seconds,
                   "gens_done": self.gen_done, "stopped_by_deadline_at": stopped_at, "warm": self.warm,
                   "warm_gen": self.warm_gen, "noise": self.noise, "tracks": list(self.tracks.values()),
                   "alternatives": sum(1 for p in progs if p.role == "alt"),
                   "levels": Counter(str(h.get("level")) for h in hist if "level" in h)}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
        (self.dir / "best.py").write_text(best.code)
        c = self.archive.construction(best.id)
        if c is not None:
            import numpy as np
            np.save(self.dir / "best.npy", c)
        self.log(f"done: {self.name} (v7, seed {self.cfg.seed}): best {best.score:.6f} ({best.id}, track "
                 f"{self.track_of(best)}) after {self.gen_done} generations, {len(progs)} programs, {self.llm.calls} "
                 f"model calls")
        return summary


# ---------------------------------------------------------------------------------------------- the fake model
def fake_answer(role, system, user):
    if role in ("coder", "mutator"):
        return "```python\n" + FAKE_CODE.replace("{tag}", str(random.randint(1, 10 ** 9))) + "```\nSUMMARY: fake search"
    if role == "researcher":
        tail = user.split("## This generation's experiments, slot by slot")[-1]
        best = re.findall(r"The best program so far: (p\d{4})", user)
        exps = []
        for m in re.finditer(r"^Slot (\d+) \(([^)]*)\)(.*?)(?=^Slot \d+ \(|\Z)", tail, re.S | re.M):
            n, kind, body = int(m.group(1)), m.group(2), m.group(3)
            ids = re.findall(r"\bp\d{4}\b", body)
            e = {"slot": n, "base": ids[0] if ids and "main" not in kind else (best[0] if best else "p0001"),
                 "hypothesis": f"fake hypothesis {n} ({kind})", "change": f"perturb heights, variant {n}",
                 "prediction": "a gain", "builds_on": ids[:1]}
            fs = re.findall(r"\bF\d+\b", body)
            if "revive" in kind and fs:
                e["revives"] = fs[0]
            exps.append(e)
        return "```json\n" + json.dumps({"analysis": "fake analysis", "experiments": exps}) + "\n```"
    return fake_answer4(role, system, user)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--deep", type=int, default=3)
    ap.add_argument("--wide", type=int, default=3)
    ap.add_argument("--effort", default="low", help="the Researcher's thinking effort")
    ap.add_argument("--label", default="")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model writes random-search programs)")
    a = ap.parse_args(argv)
    cfg = Config(seed=a.seed, gens=a.gens or 20, budget=a.budget, deep=a.deep, wide=a.wide,
                 researcher_effort=a.effort, label=a.label)
    llm = FakeLLM(fake_answer) if a.fake else None
    run = Run(a.out, cfg, llm=llm, gens=a.gens, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()


if __name__ == "__main__":
    sys.exit(main())
