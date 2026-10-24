"""One Helix v8 run: v7, plus a register of hills, so that new hills are found, told apart from known ones, and
climbed (docs/V8_DESIGN.md).

    python -m helix8.run --seed 1 --gens 30 --out runs/v8/v8-s1
    python -m helix8.run --out runs/v8/v8-s1                     # resumes (state.json is there)
    python -m helix8.run --gens 2 --fake --out /tmp/x            # no model calls

Everything in v7 (helix7/run.py) stays: the roles, 3 planned experiments and 3 mutations a generation, the stall
levels, the main track's guaranteed slot, tracks that are never closed, alternatives, the noise floor, warm starts.

What v8 adds:
- **Hills, measured by code.** A hill is a family of programs whose outputs are nearly the same (helix8/hills.py:
  the shape of the construction; a plug-in can give its own, as the VRP does with the trips of its solutions). Each
  track's best is placed on the nearest known hill if it is within the radius (`hill_radius`, raised to the run's own
  step size on a hill if that is larger); a best far from every known hill, after its track's opening and at least
  one follow-up, founds a new hill. The register (hills.jsonl) keeps each hill's top, who found it, how often other
  tracks landed on it, and a description of its design.
- **A track's best counts only programs that changed their start.** In v7 a side track opened on the record was
  judged against an unchanged copy of the record (22 of 22 revives handed it back), so no follow-up could gain.
- **The exploration slots** (v7's levels decide how many) are:
  - flip: change one design decision that every known hill shares, on the record (or another hill's top), keeping
    the rest, so its chain of improvements carries over (revive's findings are one source of what to change);
  - restart: a design unlike every known hill, given the map of known hills and the record's whole chain of
    improvements to apply at once; a restart that lands on a known hill below its top stops there;
  - backtrack (v7's), each option shown with the hill it is on;
  - continuing a live side track (v7's), with where it stands on the map.
  Flips and restarts get `explore_patience` (2) follow-ups without a gain before they pause (v7: 1).
- **The map.** A mapping step (the Cartographer, one model call when needed) describes each new hill by its design
  decisions, and lists the decisions every known hill shares (`scan_every` generations apart while exploring). The
  planner sees the hills, their tops, how often each was reached, and the shared decisions.
- On a warm start, the first generation registers the hills the run already knows: every earlier track's best is
  placed (on the VRP, the best ones are evaluated again to get their signatures).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from helix4 import prompts as P4
from helix4.archive import Program, make_diff, short
from helix4.llm import FakeLLM
from helix7 import prompts as P7
from helix7.memory import outcome
from helix7.run import (Config as Config7, FALLBACK as FALLBACK7, FAKE_CODE, KIND_WORDS as KIND_WORDS7, Run as Run7,
                        fake_answer as fake_answer7)
from helix8 import prompts as P
from helix8.hills import shape_distance, shape_signature

EXPLORE = ("flip", "backtrack", "restart")
NEW_KINDS = ("flip", "restart")
KIND_WORDS = {**KIND_WORDS7, "flip": "change a decision every known hill shares",
              "restart": "a new design, unlike the known hills"}
FALLBACK = {**FALLBACK7,
            "flip": "Change one design decision that every program in the tree makes the same way, keeping the rest.",
            "restart": "Build a genuinely different kind of program, unlike every known hill, applying the record's "
                       "improvements that fit it."}


@dataclass
class Config(Config7):
    condition: str = "v8"
    hill_radius: float = 0.075       # outputs closer than this are on the same hill (the shape distance, 64 bins)
    hill_bins: int = 64
    explore_patience: int = 2        # follow-ups a flip or restart track gets without beating its own best
    alt_min_ratio_explore: float = 0.5   # explorations' alternatives are kept down to this fraction of their start
    scan_every: int = 5              # generations between two scans of the shared decisions, while exploring
    scan_decisions: int = 8
    survey_max: int = 12             # on a warm start: earlier tracks whose bests are evaluated again for signatures
    map_hills: int = 10              # hills shown to the planner


class Run(Run7):
    CONFIG = Config
    VERSION = "v8"

    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print, problem=None):
        super().__init__(out, cfg, llm=llm, gens=gens, log=log, problem=problem)
        self.sig_lock = threading.Lock()
        self._sig, self._moved = {}, {}
        self.signatures = {}
        rows = self._jsonl("signatures.jsonl")
        keep = [r for r in rows if r.get("id") in self.archive.programs]
        if len(keep) != len(rows):          # a resume dropped programs; their ids will be reused
            (self.dir / "signatures.jsonl").write_text("".join(json.dumps(r) + "\n" for r in keep))
        self.signatures = {r["id"]: r["sig"] for r in keep}
        if (self.dir / "hills.jsonl").exists():
            self._truncate_jsonl(self.dir / "hills.jsonl")
        last = (self._jsonl("hills.jsonl")[-1:] or [{}])[0]
        self.hills = {h["id"]: h for h in last.get("hills", [])}
        self.shared = last.get("shared", [])
        self.scan_gen = last.get("scan_gen")
        self.flipped = last.get("flipped", [])
        self.hill_steps = last.get("hill_steps", [])
        self.to_describe = [h for h, x in self.hills.items() if not x.get("description")]

    # ---------------------------------------------------------------- what a program produces
    def output_signature(self, p):
        """What p produces, for telling hills apart: the shape of its construction (a plug-in can override)."""
        if p.id in self.signatures:
            return self.signatures[p.id]
        c = self.archive.construction(p.id)
        return shape_signature(c, self.cfg.hill_bins) if c is not None else None

    def signature_distance(self, a, b):
        return shape_distance(a, b)

    def store_signature(self, pid, sig):
        if sig is None:
            return
        with self.sig_lock:
            self.signatures[pid] = sig
            self._sig[pid] = sig
            with (self.dir / "signatures.jsonl").open("a") as f:
                f.write(json.dumps({"id": pid, "sig": sig}) + "\n")

    def sig(self, pid):
        with self.sig_lock:
            if pid in self._sig:
                return self._sig[pid]
        p = self.archive.programs.get(pid)
        s = self.output_signature(p) if p is not None and p.valid else None
        if s is not None:
            with self.sig_lock:
                self._sig[pid] = s
        return s

    def dist(self, a, b):
        sa, sb = self.sig(a), self.sig(b)
        return None if sa is None or sb is None else self.signature_distance(sa, sb)

    def moved(self, p):
        """True if p's output differs from its base's: an unchanged copy of its start tells nothing about its track."""
        if p is None or not p.valid:
            return False
        if p.id in self._moved:
            return self._moved[p.id]
        if p.role in ("alt", "seed", "warm") or not p.parent or p.parent not in self.archive.programs:
            m = True
        else:
            d = self.dist(p.id, p.parent)
            m = (p.delta is None or abs(p.delta) > 1e-12) if d is None else d > 1e-9
        self._moved[p.id] = m
        return m

    # ---------------------------------------------------------------- tracks (v7's, with moved-only bests)
    def patience(self, t):
        return self.cfg.explore_patience if t.get("kind") in NEW_KINDS else self.cfg.track_patience

    def live(self, t):
        if t["id"] == self.main_track() or t.get("misses", 0) >= self.patience(t):
            return False
        return not (t.get("kind") == "restart" and t.get("hill_status") == "on")    # it landed on a known hill

    def open_track(self, gen, kind, root, revives=None, flips=None):
        if kind not in NEW_KINDS:
            return super().open_track(gen, kind, root, revives)
        n = len(self.tracks) + 1
        while f"T{n}" in self.tracks:
            n += 1
        tid = f"T{n}"
        src = (f"a flip of {short(flips, 90)} on {root}" if kind == "flip" and flips else
               f"a flip on {root}" if kind == "flip" else f"a restart towards a new hill, from {root}")
        self.tracks[tid] = {"id": tid, "kind": kind, "root": root, "opened": gen, "source": src, "revives": revives,
                            "flips": flips, "best": None, "best_id": None, "misses": 0, "last_gain": gen,
                            "closing": None, "exps": 0, "hill": None, "hill_status": None}
        return tid

    def update_tracks(self, gen, children, exps, prev_best):
        events = []
        had = Counter(x["track"] for x in exps)
        main = self.main_track()
        for tid, t in self.tracks.items():
            t.pop("synced", None)
            if tid in had:
                t["exps"] = t.get("exps", 0) + had[tid]
            mine = [c for c in children if c is not None and c.valid and self.track_of(c) == tid and self.moved(c)]
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
                if t["misses"] == self.patience(t) and tid != main:
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

    # ---------------------------------------------------------------- the register of hills
    def radius(self):
        """The same-hill radius: the configured one, or twice the median recent step of a hill's top along its own
        climb if that is larger (at most twice the configured one), so it follows the problem's own scale."""
        r = self.cfg.hill_radius
        steps = sorted(d for d in self.hill_steps[-20:] if d is not None)
        if len(steps) >= 3:
            r = max(r, min(2 * self.cfg.hill_radius, 2 * steps[len(steps) // 2]))
        return r

    def moved_best(self, t):
        mem = [p for p in self.track_members(t) if self.moved(p)]
        return mem[0] if mem else None

    def new_hill(self, gen, top, founder, how, nearest=None, d=None):
        n = len(self.hills) + 1
        while f"H{n}" in self.hills:
            n += 1
        hid = f"H{n}"
        p = self.archive.programs[top]
        self.hills[hid] = {"id": hid, "top": top, "top_score": p.score, "found_gen": gen, "founder": founder,
                           "how": how, "reached": 0, "landings": [], "nearest": nearest,
                           "distance": round(d, 4) if d is not None else None, "description": None}
        self.to_describe.append(hid)
        return hid

    def land(self, gen, t, h, d, events, seeding):
        """t's best is within the radius of h, a hill t doesn't carry: t is on h (and h's top if t beats it)."""
        pid = t["placed"]
        p = self.archive.programs[pid]
        if t.get("hill") != h["id"]:
            t["hill"] = h["id"]
            h["reached"] += 1
            h["landings"] = (h["landings"] + [[gen, t["id"]]])[-20:]
            if not seeding:
                events.append(f"{t['id']} landed on {h['id']} (distance {d:.3f})")
        if h.get("fixed"):                       # the starting program's hill stays where it is
            t["hill_status"] = "on"
        elif p.score > h["top_score"] + self.floor(h["top_score"]):
            h["top"], h["top_score"] = pid, p.score
            t["hill_status"] = "top"
            if not seeding:
                events.append(f"{t['id']} is now the top of {h['id']} ({p.score:.6f})")
        else:
            t["hill_status"] = "top" if h["top"] == pid else "on"

    def place(self, gen, t, pid, events, seeding=False):
        """Puts a track's best on the map.
        - A track that carries a hill (it founded it, or holds its top) moves that hill's top as it climbs, unless it
          has climbed into another known hill, below that hill's top.
        - Any other track is on the nearest known hill if within the radius; if it is far from every known hill, it
          founds a new hill after its opening and at least one follow-up (at once on a warm start, or for the main
          track), and is a candidate until then."""
        p = self.archive.programs[pid]
        t["placed"] = pid
        near = [(self.dist(pid, h["top"]), h) for h in self.hills.values()]
        near = [(d, h) for d, h in near if d is not None]
        if not near:
            if not self.hills and self.sig(pid) is not None:
                hid = self.new_hill(gen, pid, t["id"], "the record when the map began")
                self.hills[hid]["seeded"] = True
                t["hill"], t["hill_status"] = hid, "founder"
            return
        r = self.radius()
        own = self.hills.get(t.get("hill")) if t.get("hill_status") in ("founder", "top") else None
        if own is not None and own.get("fixed"):
            own = None
        if own is not None:
            others = [(d, h) for d, h in near if h["id"] != own["id"]]
            if others:
                d2, h2 = min(others, key=lambda x: x[0])
                if d2 <= r and h2["top_score"] >= p.score - self.floor(p.score) and own["top"] != pid:
                    t["hill_distance"], t["hill_nearest"] = round(d2, 4), h2["id"]
                    self.land(gen, t, h2, d2, events, seeding)
                    if not seeding:
                        events.append(f"{t['id']} climbed from {own['id']} into {h2['id']}")
                    return
            d_own = self.dist(pid, own["top"])
            t["hill_distance"], t["hill_nearest"] = (round(d_own, 4) if d_own is not None else None), own["id"]
            if own["top"] != pid and p.score > own["top_score"] + self.floor(own["top_score"]):
                if d_own is not None and abs(p.score - own["top_score"]) < 0.01 * abs(own["top_score"]):
                    self.hill_steps = (self.hill_steps + [round(d_own, 4)])[-40:]      # a step along its own climb
                own["top"], own["top_score"] = pid, p.score
            return
        d, h = min(near, key=lambda x: x[0])
        t["hill_distance"], t["hill_nearest"] = round(d, 4), h["id"]
        if d <= r:
            self.land(gen, t, h, d, events, seeding)
            return
        if seeding or t.get("exps", 0) >= 2 or t["id"] == self.main_track():
            hid = self.new_hill(gen, pid, t["id"], t["source"] + (" (an earlier run)" if seeding else ""), h["id"], d)
            self.hills[hid]["seeded"] = seeding
            t["hill"], t["hill_status"] = hid, "founder"
            if not seeding:
                events.append(f"new hill {hid}, found by {t['id']} ({t['kind']}): {p.score:.6f}, distance {d:.3f} from "
                              f"the nearest known hill ({h['id']})")
        else:
            t["hill"], t["hill_status"] = None, "candidate"

    def seed_hills(self, gen, events):
        """The hills the run already knows: the starting program's, the record's, and every earlier track's best."""
        self.survey()
        seed = next((p for p in self.archive.programs.values() if p.role == "seed" and p.valid), None)
        if seed is not None and self.sig(seed.id) is not None:
            hid = self.new_hill(gen, seed.id, None, "Code Zero, the starting program")
            self.hills[hid].update(description="the starting program (Code Zero)", fixed=True)
            self.to_describe.remove(hid)
        main = self.tracks.get(self.main_track())
        best = self.archive.best()
        if main is not None and best is not None and best.id != (seed.id if seed else None):
            self.place(gen, main, best.id, events, seeding=True)
        others = []
        for t in self.tracks.values():
            if t["id"] == self.main_track():
                continue
            b = self.moved_best(t)
            if b is not None:
                t["best"], t["best_id"] = b.score, b.id
                others.append((b.score, t, b.id))
        for _, t, pid in sorted(others, key=lambda x: -x[0]):
            if self.sig(pid) is not None:
                self.place(gen, t, pid, events, seeding=True)
        found = sorted(self.hills.values(), key=lambda h: -h["top_score"])
        events.append(f"the map begins with {len(found)} known hills: " + ", ".join(
            f"{h['id']} ({h['top_score']:.6f}, reached {h['reached']} more times)" for h in found[:8]))

    def survey(self):
        """A plug-in whose signatures need an evaluation (the VRP) gets them here for the best earlier programs."""
        return

    def update_hills(self, gen, events):
        if not self.hills:
            self.seed_hills(gen, events)
            return
        main = self.tracks.get(self.main_track())
        order = ([main] if main else []) + sorted((t for t in self.tracks.values() if t is not main and t.get("best_id")),
                                                  key=lambda t: -(t["best"] or -1e300))
        for t in order:
            pid = t.get("best_id") if t is not main else self.archive.best().id
            if pid and (t.get("placed") != pid or t.get("hill_status") == "candidate"):
                if self.sig(pid) is not None:
                    self.place(gen, t, pid, events)

    # ---------------------------------------------------------------- the Cartographer
    def chain(self, k=12):
        """The improvements that built the record: its lineage's steps that gained."""
        out = []
        for p in self.archive.lineage(self.archive.best().id, depth=100000):
            if p.parent and outcome(p, self) == "gain":
                out.append(f"- {short(p.intent, 170)} ({p.delta:+.6f}, {p.id})")
        return "\n".join(out[-k:]) or "- (none recorded)"

    def lineage_steps(self, pid, k=8):
        out = []
        for p in self.archive.lineage(pid, depth=100000):
            if p.parent and outcome(p, self) == "gain":
                out.append(short(p.intent, 140))
        return "; ".join(out[-k:]) or "(no recorded steps)"

    def describe_hills(self, gen, k=2):
        done = 0
        for hid in list(self.to_describe):
            if done >= k:
                break
            h = self.hills.get(hid)
            self.to_describe.remove(hid)
            if h is None or h.get("description"):
                continue
            top = self.archive.programs[h["top"]]
            user = (f"{self.problem.TITLE}\n\n## The program on the new hill: {top.line()}\nIts result:\n"
                    + "\n".join(f"  {l}" for l in top.feedback[:6]) + f"\n```python\n{P4.clip(top.code, 9000)}```\n\n"
                    f"## The steps that built the record ({self.archive.best().line()})\n{self.chain()}\n\n"
                    + P.DESCRIBE_ASK)
            text = self.call("cartographer", P.CARTOGRAPHER_SYSTEM, user, temperature=0.3, max_tokens=500,
                             effort="none", gen=gen)
            h["description"] = short(text, 400) if text and text.strip() else None
            done += 1

    def scan_due(self, gen, n_explore):
        if n_explore <= 0 or not self.hills:
            return False
        if self.scan_gen is None:
            return True
        found_since = any(h["found_gen"] > self.scan_gen for h in self.hills.values())
        return gen - self.scan_gen >= self.cfg.scan_every or (found_since and gen - self.scan_gen >= 2)

    def scan(self, gen):
        """Asks which design decisions every known hill shares: the axes the search has never moved along."""
        hills = sorted(self.hills.values(), key=lambda h: -h["top_score"])[:8]
        rows = [f"### {h['id']}: best {h['top']} ({h['top_score']:.6f})\nDescription: {h.get('description') or '-'}\n"
                f"The steps that built it: {self.lineage_steps(h['top'])}" for h in hills]
        best = self.archive.best()
        user = (f"{self.problem.TITLE}\n\n## The known hills\n" + "\n\n".join(rows)
                + f"\n\n## The record's program: {best.line()}\n```python\n{P4.clip(best.code, self.best_code_chars())}```\n\n"
                + P.SCAN_ASK.format(k=self.cfg.scan_decisions))
        text = self.call("cartographer", P.CARTOGRAPHER_SYSTEM, user, temperature=0.4, max_tokens=2500, effort="none",
                         gen=gen)
        js = P4.extract_json(text) or {}
        out = []
        for i, d in enumerate([x for x in (js.get("shared") or []) if isinstance(x, dict) and x.get("decision")]
                              [: self.cfg.scan_decisions], 1):
            alts = [short(a, 120) for a in (d.get("alternatives") or []) if isinstance(a, str)][:3]
            out.append({"id": f"D{i}", "decision": short(d["decision"], 160), "everyone": short(d.get("everyone"), 160),
                        "alternatives": alts, "gen": gen})
        self.scan_gen = gen
        if out:
            self.shared = out
        return out

    # ---------------------------------------------------------------- the planner's view
    def hill_label(self, pid):
        """Which known hill a program is on (or how far it is from the nearest)."""
        near = [(self.dist(pid, h["top"]), h) for h in self.hills.values()]
        near = [(d, h) for d, h in near if d is not None]
        if not near:
            return "not measured"
        d, h = min(near, key=lambda x: x[0])
        return f"on {h['id']}" if d <= self.radius() else f"on no known hill ({d:.2f} from {h['id']})"

    def map_view(self):
        if not self.hills:
            return ""
        main_hill = (self.tracks.get(self.main_track()) or {}).get("hill")
        hs = sorted(self.hills.values(), key=lambda h: (h["id"] != main_hill, -h["top_score"]))
        rows = []
        for h in hs[: self.cfg.map_hills]:
            tag = " (the record's hill)" if h["id"] == main_hill else ""
            how = ("known from the start" if not h.get("founder") else
                   f"known from earlier generations (by {h['founder']})" if h.get("seeded") else
                   f"found at generation {h['found_gen']} by {h['founder']}")
            reached = f"; other tracks landed on it {h['reached']} times" if h["reached"] else ""
            rows.append(f"- {h['id']}{tag}: top {h['top']} ({h['top_score']:.6f}); {how}{reached}. "
                        f"{h.get('description') or '(not described yet)'}")
        more = len(hs) - len(rows)
        out = (f"## The map: hills found so far ({len(hs)}; a hill is a family of programs whose outputs are nearly the "
               f"same, measured by code)\n" + "\n".join(rows) + (f"\n({more} lower hills not shown)" if more > 0 else ""))
        if self.shared:
            tried = {}
            for key, g, tid in self.flipped:
                tried.setdefault(key, []).append((g, tid))
            lines = []
            for d in self.shared:
                t = tried.get(d["id"], [])
                note = ""
                if t:
                    g, tid = t[-1]
                    tr = self.tracks.get(tid, {})
                    where = tr.get("hill_status")
                    note = (f" [flipped at generation {g} by {tid}: "
                            + (f"on {tr.get('hill')}" if where in ("on", "top") else
                               f"new hill {tr.get('hill')}" if where == "founder" else "not placed yet") + "]")
                lines.append(f"- {d['id']}: {d['decision']}: all use {d['everyone']}; alternatives: "
                             f"{'; '.join(d['alternatives']) or '-'}{note}")
            out += (f"\n\nDecisions every known hill shares (mapped at generation {self.shared[0]['gen']}):\n"
                    + "\n".join(lines))
        return out

    def tracks_view(self):
        text = super().tracks_view()
        if not text:
            return text
        for t in self.tracks.values():                 # each side track's place on the map
            if t.get("hill_status"):
                where = {"founder": f"founded {t.get('hill')}", "top": f"top of {t.get('hill')}",
                         "on": f"on {t.get('hill')}", "candidate": "a candidate new hill"}[t["hill_status"]]
                text = text.replace(f"- {t['id']}: ", f"- {t['id']} [{where}]: ", 1)
        return text

    def brief(self, gen, slots):
        parts = [x for x in (self.map_view(), self.tracks_view()) if x]
        parts.append("## This generation's experiments, slot by slot\n" + "\n".join(s["text"] for s in slots))
        return "\n\n".join(parts)

    def researcher_system(self, k):
        return P.RESEARCHER_SYSTEM.format(k=k, budget=self.cfg.budget)

    def plan_fields(self, slots):
        return P.FLIP_FIELD if any(s["kind"] == "flip" for s in slots) else ""

    def hills_text(self, k=8):
        hs = sorted(self.hills.values(), key=lambda h: -h["top_score"])[:k]
        return "\n".join(f"- {h['id']} (best {h['top_score']:.6f}): {h.get('description') or 'not described yet'}"
                         + (f"; reached {h['reached']} more times" if h["reached"] else "") for h in hs) or "- (none)"

    # ---------------------------------------------------------------- slots
    def flip_options(self):
        since = self.last_record()
        done = {k for k, g, _ in self.flipped if g > since}
        decs = [d for d in self.shared if d["id"] not in done]
        fids = self.revive_candidates()[:3]
        return decs, fids

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
            avail = [k for k in EXPLORE if k not in used and (k != "backtrack" or self.backtrack_candidates())]
            kind = min(avail, key=lambda k: (opened[k], EXPLORE.index(k))) if avail else "restart"
            used.append(kind)
            opened[kind] += 1
            slots.append({"kind": kind})
        best = self.archive.best()
        for n, s in enumerate(slots, 1):
            s["n"] = n
            k = s["kind"]
            if k == "main":
                s["text"] = P.SLOT_TEXT["main"].format(n=n)
            elif k == "flip":
                decs, fids = self.flip_options()
                s["options"] = [d["id"] for d in decs] + fids
                s["decisions"] = {d["id"]: d for d in decs}
                lines = [f"- {d['id']}: {d['decision']} (all use: {d['everyone']}; alternatives: "
                         f"{'; '.join(d['alternatives']) or '-'})" for d in decs]
                lines += [f"- {self.memory.finding_line(f, 200)}" for f in fids]
                tops = [h["top"] for h in self.hills.values() if h["top"] != best.id][:4]
                s["bases"] = [best.id] + tops
                if decs:
                    s["text"] = P.SLOT_TEXT["flip"].format(n=n, best=best.id, options="\n".join(lines)
                                                           + (f"\nOther hills' tops: {', '.join(tops)}" if tops else ""))
                else:
                    s["text"] = P.SLOT_TEXT["flip_open"].format(
                        n=n, best=best.id, options=("\nEarlier approaches you may re-apply as the change:\n"
                                                    + "\n".join(lines)) if lines else "")
            elif k == "restart":
                seed = self.seed_program()
                s["text"] = P.SLOT_TEXT["restart"].format(n=n, seed=self.bold_seed_text() if seed else "any program",
                                                          chain=self.chain())
            elif k == "backtrack":
                c = self.backtrack_candidates()
                s["options"] = [pid for pid, _ in c]
                opts = "\n".join(f"- {self.archive.programs[pid].line()}: {why}; {self.hill_label(pid)}; "
                                 f"{short(self.archive.programs[pid].intent, 100)}" for pid, why in c)
                s["text"] = P.SLOT_TEXT["backtrack"].format(n=n, options=opts)
            else:
                t = self.tracks[s["track"]]
                mem = [p for p in self.track_members(t) if self.moved(p)]
                newest = sorted(mem, key=lambda p: -int(p.id[1:]))[:3]
                show = list({p.id: p for p in mem[:3] + newest}.values())
                opts = "\n".join(f"- {p.line()}: {short(p.intent, 110)}" for p in show) or \
                    f"- (its first program didn't change its start: start again from its root, {t['root']})"
                if t.get("closing") is None:
                    why = (f"it was opened at generation {t['opened']} ({t['source']}) and is owed a follow-up, even if "
                           f"it started below its base")
                else:
                    why = f"it gained at generation {t['last_gain']} ({t['source']})"
                place = self.track_place_note(t)
                why += (". " + place[:-1]) if place else ""
                s["options"] = [p.id for p in mem] or [t["root"]]
                score = f"{t['best']:.6f}" if t["best"] is not None else "none yet"
                s["text"] = P.SLOT_TEXT["track"].format(n=n, track=t["id"], why=why, options=opts,
                                                        best=t["best_id"] or t["root"], score=score)
        return slots

    def track_place_note(self, t):
        st, hid, d = t.get("hill_status"), t.get("hill"), t.get("hill_distance")
        if st == "on":
            return (f"Its output is still on {hid} (distance {d:.3f}), below that hill's top: the change has not moved "
                    f"it off that hill yet; make the change take effect.")
        if st == "candidate":
            return f"Its output is far from every known hill ({d:.3f} from the nearest): a candidate new hill; climb it."
        if st == "founder":
            return f"It founded {hid}: climb it."
        if st == "top":
            return f"It holds the top of {hid}: climb it."
        return ""

    def assign(self, gen, s, e):
        k = s["kind"]
        if k not in NEW_KINDS:
            return super().assign(gen, s, e)
        a, best = self.archive, self.archive.best()
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
        flips = revives = None
        if k == "flip":
            bases = s.get("bases") or [best.id]
            base = req if req in bases else best.id
            fl = str((e or {}).get("flips") or "").strip()
            decs = {**{d["id"]: d for d in self.shared}, **(s.get("decisions") or {})}
            if fl in decs:
                flips, x["flips"] = f"{fl}: {decs[fl]['decision']}", fl
            elif fl in self.memory.findings:
                revives, x["revives"] = fl, fl
                flips = f"the approach of {fl}"
            elif fl:
                flips = x["flips"] = short(fl, 200)
            elif s.get("options"):
                opt = s["options"][0]
                if opt in decs:
                    flips, x["flips"] = f"{opt}: {decs[opt]['decision']}", opt
                else:
                    revives, x["revives"], flips = opt, opt, f"the approach of {opt}"
                if e is None:
                    x["change"] += f" ({flips})"
        else:
            base = req if ok else self.seed_program().id
        if req and req != base:
            x["base_requested"] = req
        x["base"] = base
        x["track"] = self.open_track(gen, k, base, revives=revives, flips=flips)
        if k == "flip":
            ids = {d["id"] for d in self.shared} | set(s.get("decisions") or {})
            key = x.get("flips") if x.get("flips") in ids else (revives or flips or "?")
            self.flipped.append([key, gen, x["track"]])
            if revives:
                self.revived.append([revives, best.id, gen])
        return x

    # ---------------------------------------------------------------- children
    def alt_note(self):
        return P.ALT_NOTE

    def deep_child(self, gen, exp):
        if exp.get("kind") not in NEW_KINDS and exp.get("kind") != "track":
            return super().deep_child(gen, exp)
        try:
            base = self.archive.programs[exp["base"]]
            if exp["kind"] == "flip":
                what = (self.tracks.get(exp["track"]) or {}).get("flips") or "one shared design decision"
                note = P.FLIP_CODER_NOTE.format(decision=what, alt=self.alt_note())
                f = self.memory.findings.get(exp.get("revives") or "")
                if f is not None:
                    note += f"\nThe earlier approach ({exp['revives']}): {f['claim']}"
            elif exp["kind"] == "restart":
                note = P.RESTART_CODER_NOTE.format(hills=self.hills_text(), chain=self.chain(), alt=self.alt_note())
            else:
                t = self.tracks.get(exp["track"]) or {}
                place = self.track_place_note(t)
                note = P7.EXPLORE_CODER_NOTE.format(kind=KIND_WORDS["track"]) + (" " + place if place else "")
            task = self.task_text("the base's")
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Target: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"Keep what the base does well unless the experiment says otherwise. {task}\n\n{note}\n\n"
                    f"{P4.CODE_FORMAT}")
            code, summary = self.write_code("coder", self.coder_system(), user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp,
                              summary)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: deep child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}")), None

    def exploring(self, plan):
        t = self.tracks.get((plan or {}).get("track") or "")
        return bool(t) and t.get("kind") in NEW_KINDS and t["id"] != self.main_track()

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
        ratio = self.cfg.alt_min_ratio_explore if self.exploring(plan) else self.cfg.alt_min_ratio
        if p.valid and alt is not None:
            ref = p.start_score if p.start_score is not None else p.score
            if alt["score"] >= ratio * ref:
                keep = alt
                p.feedback = p.feedback + [f"it also handed back an alternative construction scoring {alt['score']:.6f}, "
                                           f"kept as its own program"]
            else:
                p.feedback = p.feedback + [f"its alternative construction scored {alt['score']:.6f}, below "
                                           f"{ratio:g} of its start's score: not kept"]
        sig = getattr(p, "_signature", None)
        p = self.add(p, construction)
        self.store_signature(p.id, sig)
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

    # ---------------------------------------------------------------- the generation
    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        self.sync_tracks()
        prev_best = self.archive.best()
        lv, stall, typical = self.level(gen)
        early = self.warm_gen is None and gen <= self.cfg.early_gens
        n_explore = min(max(lv, 2 if early else 0), self.cfg.deep - 1)
        pre = []
        if not self.hills:
            self.update_hills(gen, pre)
        scanned = None
        if self.scan_due(gen, n_explore):
            self.describe_hills(gen, k=3)
            scanned = self.scan(gen)
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
        events = pre + self.update_tracks(gen, children, exps, prev_best)
        n_hills = len(self.hills)
        self.update_hills(gen, events)
        self.describe_hills(gen, k=2)
        best = self.archive.best()
        dc = [c for c, _ in pairs[: len(deep)]]
        wc = [c for c, _ in pairs[len(deep):]]
        alts = [a for _, a in pairs if a is not None]

        def best_of(cs):
            ok = [c.score for c in cs if c is not None and c.valid]
            return max(ok) if ok else None

        refs = [r for e in exps for r in (e.get("builds_on") or [])]
        record = best.score > prev_best.score + self.floor(prev_best.score)
        main_hill = (self.tracks.get(self.main_track()) or {}).get("hill")
        row = {"gen": gen, "best": best.score, "best_id": best.id, "best_role": best.role, "best_track": self.track_of(best),
               "best_hill": main_hill, "deep_best": best_of(dc), "wide_best": best_of(wc),
               "deep_gains": sum(1 for c in dc if outcome(c, self) == "gain"),
               "wide_gains": sum(1 for c in wc if outcome(c, self) == "gain"),
               "deep_failed": sum(1 for c in dc if not c.valid), "wide_failed": sum(1 for c in wc if not c.valid),
               "duplicates": sum(1 for c in dc + wc if c.duplicate_of), "new_best": record,
               "level": lv, "stall": stall, "typical_gap": typical, "early": early,
               "slots": [s["kind"] + (f":{s['track']}" if s["kind"] == "track" else "") for s in slots],
               "experiment_tracks": [e["track"] for e in exps], "track_events": events,
               "explore_best": best_of([c for c, e in zip(dc, exps) if e["kind"] != "main"]),
               "unchanged": sum(1 for c in dc + wc if c is not None and c.valid and not self.moved(c)),
               "hills": len(self.hills), "new_hills": len(self.hills) - n_hills, "hill_radius": round(self.radius(), 4),
               "scanned": len(scanned) if scanned is not None else None,
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
        self._append("hills.jsonl", {"gen": gen, "hills": list(self.hills.values()), "shared": self.shared,
                                     "scan_gen": self.scan_gen, "flipped": self.flipped, "hill_steps": self.hill_steps})
        self.checkpoint(gen)
        kinds = Counter(s["kind"] for s in slots)
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}, track {self.track_of(best)}, "
                 f"hill {main_hill})" f"{' RECORD' if record else ''}; stall {stall} (typical {typical:g}), level {lv}; "
                 f"slots " + ", ".join(f"{n} {k}" for k, n in kinds.items())
                 + f"; deep {row['deep_gains']}/{len(dc)} gained, wide {row['wide_gains']}/{len(wc)} gained; "
                 f"{len(self.hills)} hills" + (f", {row['new_hills']} new" if row["new_hills"] else "")
                 + (f"; {len(alts)} alternatives kept" if alts else "") + (f"; {'; '.join(events)}" if events else "")
                 + f"; {row['seconds']:.0f} s")
        return row

    def finish(self, seconds=None, stopped_at=None):
        summary = super().finish(seconds, stopped_at)
        summary["hills"] = list(self.hills.values())
        summary["shared_decisions"] = self.shared
        summary["flipped"] = self.flipped
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
        return summary


# ---------------------------------------------------------------------------------------------- the fake model
def fake_answer(role, system, user):
    if role == "cartographer":
        if "List the design decisions" in user:
            return "```json\n" + json.dumps({"shared": [
                {"decision": "how the first construction is built", "everyone": "from the start's construction",
                 "alternatives": ["from a random one", "from a smooth one"]},
                {"decision": "what is optimised", "everyone": "the score itself",
                 "alternatives": ["a smoothed score", "a proxy"]}]}) + "\n```"
        return "It builds its construction differently (fake description)."
    if role == "researcher":
        text = fake_answer7(role, system, user)
        js = P4.extract_json(text) or {}
        tail = user.split("## This generation's experiments, slot by slot")[-1]
        for e in js.get("experiments", []):
            m = re.search(rf"^Slot {e.get('slot')} \(explore: flip[^)]*\)(.*?)(?=^Slot \d+ \(|\Z)", tail, re.S | re.M)
            if m:
                ds = re.findall(r"\bD\d+\b", m.group(1))
                e["flips"] = ds[0] if ds else "how the start is built"
        return "```json\n" + json.dumps(js) + "\n```"
    return fake_answer7(role, system, user)


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
