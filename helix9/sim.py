"""Stage 1 of the proof of concept: a planted landscape with a known best (docs/V9_DESIGN.md, section 7 of
docs/SEARCH_SPACE_MODEL.md).

    python -m helix9.sim --family broad --policy v9 --seed 3                # one run, printed
    python -m helix9.sim --batch --seeds 24 --out results/v9sim             # every family x policy
    python -m helix9.mapview sim --family easy --policy v9 --seed 3 --out viz/data/x.json   # for viz/mapview.html

A model of our situation, not our situation. Its value is that the truth is known, so it says whether the search
logic finds a taller hill, how often, how fast, and which part of v9 does it, cheaply and over many seeds.

The world:
- **Designs** are coordinates: d axes with k values each. Some axes are hidden from the searcher at first (decisions
  nobody has named); they can be discovered.
- **Hills** are planted: each has a centre, a peak, a width (how fast height falls per axis away from the centre),
  and a maturation time. Height at a design is the best hill's peak minus its distance penalty, plus a little
  ruggedness. A trap hill sits where the coder's habits are (its centre is the prior's mode): broad, quick to climb,
  low. The record's hill is taller and far from the trap. A taller hill sits 3 coordinated changes away from the
  record's, and is deceptive: one or two of those changes lead downhill.
- **Climbing:** a program's score is its design's height minus a gap that closes with the effort spent at (or next
  to) the design: score = height - gap * exp(-effort / tau) + noise. A slow hill (large tau) looks worse than a trap
  for a long time: a hill's height is not visible from its foot.
- **The coder:** writing a fresh program samples its habits (the prior: each axis takes the trap's value with
  probability `prior`); asked for a change, each asked-for axis lands with probability `fidelity`, and each other
  axis drifts to a habit with probability `drift` (the v8 flips that "abandoned the whole lineage"). A polish that
  doesn't gain hands back its start unchanged most of the time (68% did in v7).
- **The annotator** reads each known axis correctly with probability `annot`.

The searchers (the same skeleton for all: 3 planned experiments and 3 mutations a generation, v7's stall levels, the
main track's slot, tracks never closed, v8's register of hills by behaviour):
- `v8`: exploration rotates flip (one shared decision, chosen at random), backtrack and restart (a fresh program);
  flips and restarts get 2 follow-ups without a gain, others 1.
- `v9`: exploration rotates drop (2-4 axes, chosen by Thompson sampling from the landscape model), flip (one axis,
  chosen the same way) and backtrack; drops and flips race (helix9/race.py); every landing is read back by the
  annotator; residuals trigger the discovery of hidden axes. It uses helix9's own model, race and drop code.
- ablations of v9 (`v9-random`: drops and flips without the model; `v9-norace`; `v9-noreadback`; `v9-nodiscovery`;
  `v9-level` and `v9-hedge`: other race rules), `v8-race` (v8 with the race), and `scs`, a simple baseline:
  every experiment improves a random earlier program (sequential conditioned sampling).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from helix9.codebook import Codebook, hamming
from helix9.drops import choose_drop, choose_flip, shared_axes
from helix9.model import LandscapeModel
from helix9.race import Race, record_curve, retro_judge, take_waiting

# ---------------------------------------------------------------------------------------------- the worlds
FAMILIES = {
    # name: overrides of Spec (defaults: a taller hill 3 coordinated changes from the record's, of medium width,
    # maturing as slowly as the record's own). P = the share of random 2-4-axis drops from the record that land where
    # a climb ends above the record (measured over 20 worlds).
    "broad": {},                                                    # P ~ 2%
    "easy": {"tall_width": 0.01},                                   # P ~ 9%
    "slow": {"tall_tau": 25.0},                                     # the taller hill matures slowly
    "fast": {"tall_tau": 5.0},                                      # ... or quickly
    "hidden": {"hidden": 2, "tall_hidden": True},                   # one of its 3 changes is on a hidden axis
    "narrow": {"tall_width": 0.035},                                # P ~ 0.1%: hardly reachable in the budget
    "smooth": {"tall_peak": 0.0, "decoys": 0, "rugged": 0.0, "smooth": True},   # one hill, no interactions
    "rugged": {"decoys": 8, "rugged": 0.012},                       # many decoy hills, a rougher surface
    "cold": {"warm": False, "gens": 150},                           # from Code Zero, nothing known
}
POLICIES = ("v8", "v9", "v9-random", "v9-norace", "v9-noreadback", "v9-nodiscovery", "v9-level", "v9-hedge",
            "v9-gain", "v9-standing", "v9-cap6", "v9-nocap", "v9-v8flip", "v9-restart", "v8-race", "scs")


@dataclass
class Spec:
    family: str = "broad"
    d: int = 8
    k: int = 4
    hidden: int = 1                  # axes hidden from the searcher at the start
    tall_hidden: bool = False
    prior: float = 0.7               # a fresh program takes the trap's value on each axis with this probability
    fidelity: float = 0.75           # an asked-for axis lands as asked
    drift: float = 0.12              # an untouched axis drifts to the coder's habit
    annot: float = 0.9               # the annotator reads an axis right
    noise: float = 0.0015
    fail: float = 0.08               # a program fails
    unchanged: float = 0.7           # a polish that doesn't gain hands back its start
    trap_peak: float = 0.88
    trap_width: float = 0.02
    trap_tau: float = 2.0
    rec_peak: float = 0.94
    rec_width: float = 0.03
    rec_tau: float = 12.0
    tall_peak: float = 0.962
    tall_width: float = 0.015
    tall_tau: float = 12.0
    tall_dist: int = 3
    gap: float = 0.22
    decoys: int = 3
    rugged: float = 0.004
    smooth: bool = False
    warm: bool = True
    gens: int = 120
    deep: int = 3
    wide: int = 3
    seed: int = 1


def spec_for(family, seed, **kw):
    s = Spec(family=family, seed=seed)
    for k, v in {**FAMILIES[family], **kw}.items():
        setattr(s, k, v)
    return s


class World:
    """The planted landscape. Coordinates are tuples of ints; the searcher sees them as codebook ids."""

    def __init__(self, s: Spec):
        self.s = s
        rng = np.random.default_rng(10_000 + s.seed)
        d, k = s.d, s.k
        self.axes = [f"A{i + 1}" for i in range(d)]
        hidden = set(rng.choice(d, size=s.hidden, replace=False).tolist()) if s.hidden else set()
        self.hidden = sorted(hidden)
        trap = tuple(int(x) for x in rng.integers(k, size=d))
        visible = [i for i in range(d) if i not in hidden]
        rec = list(trap)
        for i in rng.choice(visible, size=3, replace=False):
            rec[i] = int((trap[i] + 1 + rng.integers(k - 1)) % k)
        rec = tuple(rec)
        hills = [{"name": "trap", "c": trap, "peak": s.trap_peak, "width": s.trap_width, "tau": s.trap_tau}]
        hills.append({"name": "record", "c": rec, "peak": s.rec_peak, "width": s.rec_width, "tau": s.rec_tau})
        if s.tall_peak > 0:
            cands = [i for i in range(d) if rec[i] == trap[i]]       # change axes the record shares with the trap
            if s.tall_hidden and hidden:
                h0 = sorted(hidden)[0]
                pick = [h0] + rng.choice([i for i in cands if i != h0], size=s.tall_dist - 1, replace=False).tolist()
            else:
                pick = rng.choice([i for i in cands if i not in hidden], size=s.tall_dist, replace=False).tolist()
            tall = list(rec)
            for i in pick:
                tall[i] = int((rec[i] + 1 + rng.integers(k - 1)) % k)
            hills.append({"name": "tall", "c": tuple(tall), "peak": s.tall_peak, "width": s.tall_width,
                          "tau": s.tall_tau})
        for j in range(s.decoys):
            c = tuple(int(x) for x in rng.integers(k, size=d))
            hills.append({"name": f"decoy{j + 1}", "c": c, "peak": float(rng.uniform(0.86, 0.925)),
                          "width": float(rng.uniform(0.02, 0.035)), "tau": float(rng.uniform(3, 15))})
        for h in hills:
            h["w"] = rng.uniform(0.6, 1.4, size=d)
        self.hills = hills
        self.trap, self.rec = trap, rec
        self.best_peak = max(h["peak"] for h in hills)
        self.rug = rng.standard_normal((d, k, k)) * s.rugged     # each axis interacts with the next (NK, K=1)
        self.main = rng.standard_normal((d, k)) * 0.01 if s.smooth else None

    def height(self, x):
        s = self.s
        if s.smooth:
            return 0.9 + float(sum(self.main[i, x[i]] for i in range(s.d))) + 0.03 * sum(
                1 for i in range(s.d) if x[i] == self.rec[i]) / s.d
        best = -1e9
        for h in self.hills:
            dist = float(np.sum(h["w"] * (np.array(x) != np.array(h["c"]))))
            best = max(best, h["peak"] - h["width"] * dist)
        rug = float(sum(self.rug[i, x[i], x[(i + 1) % s.d]] for i in range(s.d)))
        return max(best, 0.5) + rug

    def basin(self, x):
        if self.s.smooth:
            return 1
        vals = [h["peak"] - h["width"] * float(np.sum(h["w"] * (np.array(x) != np.array(h["c"])))) for h in self.hills]
        return int(np.argmax(vals))

    def tau(self, x):
        return 10.0 if self.s.smooth else self.hills[self.basin(x)]["tau"]

    def score(self, x, e, rng):
        return self.height(x) - self.s.gap * math.exp(-e / self.tau(x)) + float(rng.normal(0, self.s.noise))

    def habit(self, i, rng):
        if rng.random() < self.s.prior:
            return self.trap[i]
        return int(rng.integers(self.s.k))

    def fresh(self, rng):
        return tuple(self.habit(i, rng) for i in range(self.s.d))

    def decode(self, base, change, rng):
        """The coder asked to change axes (index -> value) of `base`; returns what it actually built."""
        x = list(base)
        for i in range(self.s.d):
            if i in change:
                if rng.random() < self.s.fidelity:
                    x[i] = change[i]
            elif rng.random() < self.s.drift:
                x[i] = self.habit(i, rng)
        return tuple(x)

    def mutate(self, base, rng):
        """An idea of the coder's own: one axis changed to one of its habits (or anything)."""
        i = int(rng.integers(self.s.d))
        x = list(base)
        v = self.habit(i, rng)
        if v == x[i]:
            v = int((x[i] + 1 + rng.integers(self.s.k - 1)) % self.s.k)
        x[i] = v
        return tuple(x)


def vid(a, v):
    return f"{a}.v{v + 1}"


def vidx(value):
    return int(str(value).rsplit(".v", 1)[1]) - 1


# ---------------------------------------------------------------------------------------------- the searchers
@dataclass
class Prog:
    id: str
    gen: int
    parent: str | None
    x: tuple
    obs: dict
    e: float                         # true effort at its design
    e_obs: float                     # the effort the searcher computes from what it observes
    y: float | None
    track: str
    kind: str
    moved: bool = True
    valid: bool = True
    basin: int = -1


@dataclass
class Policy:
    name: str
    kinds: tuple = ("flip", "backtrack", "restart")
    model: bool = False
    readback: bool = False
    race: str | None = None          # None (v8's patience), "rising", "level", "hedge"
    flip: str = "auto"               # how a flip is chosen: "auto" (v9: from the map; v8: a shared decision), "shared"
    cap: int = 3                     # a new direction opens only while fewer than this many tracks race
    serve: str = "turn"              # the race's schedule: "turn" (least recently served first), "gain" (tracks that
                                     # gained at their last experiment first, then in turn), "standing" (the best at
                                     # equal effort first)
    discovery: bool = False
    scs: bool = False
    kmin: int = 2
    kmax: int = 4


def policy(name):
    v9 = dict(kinds=("drop", "flip", "backtrack"), model=True, readback=True, race="rising", discovery=True)
    table = {
        "v8": dict(),
        "v9": v9,
        "v9-random": {**v9, "model": False},
        "v9-norace": {**v9, "race": None},
        "v9-noreadback": {**v9, "readback": False},
        "v9-nodiscovery": {**v9, "discovery": False},
        "v9-level": {**v9, "race": "level"},
        "v9-hedge": {**v9, "race": "hedge"},
        "v9-gain": {**v9, "serve": "gain"},
        "v9-cap6": {**v9, "cap": 6},
        "v9-v8flip": {**v9, "flip": "shared"},
        "v9-restart": {**v9, "kinds": ("restart", "flip", "backtrack")},
        "v9-nocap": {**v9, "cap": 99},
        "v9-standing": {**v9, "serve": "standing"},
        "v8-race": dict(race="rising"),
        "scs": dict(scs=True),
    }
    return Policy(name=name, **table[name])


class Sim:
    PATIENCE = {"flip": 2, "restart": 2, "drop": 2}
    RUNNING_CAP = 3

    def __init__(self, spec: Spec, pol: Policy, record_events=False):
        self.s, self.p = spec, pol
        self.w = World(spec)
        self.rng = np.random.default_rng(spec.seed * 7919 + sum(ord(ch) * (i + 1) for i, ch in enumerate(pol.name)))
        self.progs, self.byid = [], {}
        self.tracks, self.main = {}, "T1"
        self.hills = {}                  # basin -> {"top": pid, "score", "found", "by"}
        self.hist = []
        self.events = [] if record_events else None
        self.revived = 0
        self.cb = Codebook()
        for i, a in enumerate(self.w.axes):
            if i not in self.w.hidden:
                self.cb.add_axis(f"decision {a}", 0, "seed", values=[f"option {v + 1} of {a}" for v in range(spec.k)])
        self.axis_map = {f"decision {a}": a for a in self.w.axes}
        self.known = {self.cb_axis(a): i for i, a in enumerate(self.w.axes) if i not in self.w.hidden}
        self.flipped, self.dropped = set(), set()
        brackets = (0, 0, 2) if pol.race == "hedge" else (0,)
        rule = "level" if pol.race in ("level", "hedge") else "rising"
        self.race = Race(rule=rule, brackets=brackets, floor=self.floor) if pol.race else None
        self.model = None
        self.last_record_gen, self.records = 0, []
        self.calls = Counter()

    # ---------------------------------------------------------------- the codebook view of the world
    def cb_axis(self, a):
        return self.cb.find_axis(f"decision {a}", threshold=0.99)

    def misread(self, v):
        return int((v + 1 + self.rng.integers(self.s.k - 1)) % self.s.k)

    def observe(self, x, base=None):
        """The annotator's reading of design x. With a base (diff-based, as v9 annotates): the base's coordinate,
        with the axes the change touched read again (each right with probability annot) and, rarely, an untouched
        axis misreported as changed. Without (a full reading, as for a drop's landing): every known axis read."""
        out = {}
        for aid, i in self.known.items():
            if base is not None and aid in base.obs:
                if x[i] != base.x[i]:
                    v = x[i] if self.rng.random() < self.s.annot else self.misread(x[i])
                    out[aid] = f"{aid}.v{v + 1}"
                elif self.rng.random() < (1 - self.s.annot) / 4:
                    out[aid] = f"{aid}.v{self.misread(x[i]) + 1}"
                else:
                    out[aid] = base.obs[aid]
                continue
            v = x[i] if self.rng.random() < self.s.annot else self.misread(x[i])
            out[aid] = f"{aid}.v{v + 1}"
        return out

    def to_x(self, coord, base_x):
        """Turns a codebook coordinate change into world axis indices (for the coder)."""
        ch = {}
        for aid, v in coord.items():
            i = self.known.get(aid)
            if i is None:
                continue
            if v.endswith(".new"):
                opts = [u for u in range(self.s.k) if u != base_x[i]]
                ch[i] = int(self.rng.choice(opts))
            else:
                ch[i] = vidx(v)
        return ch

    def words(self, change):
        """A codebook change in the world's own names: 'A4 -> option 1, A6 -> option 4'."""
        out = []
        for aid, v in change.items():
            i = self.known.get(aid)
            name = self.w.axes[i] if i is not None else aid
            out.append(f"{name} -> {'a new option' if v.endswith('.new') else 'option ' + v.rsplit('.v', 1)[1]}")
        return ", ".join(out)

    # ---------------------------------------------------------------- bookkeeping
    def floor(self, ref):
        return 3 * self.s.noise

    def add(self, gen, parent, x, track, kind, obs=None, e=None, e_obs=None, moved=True, y=None, valid=True):
        pid = f"p{len(self.progs) + 1:04d}"
        par = self.byid.get(parent)
        if e is None:
            if par is None:
                e = 1.0
            else:
                c = sum(1 for a, b in zip(par.x, x) if a != b)
                e = par.e + 1 if c == 0 else (par.e * 0.6 + 1 if c == 1 else min(par.e * 0.3, 2.0) + 1)
        if obs is None:
            obs = self.observe(x, par)
        if e_obs is None:
            if par is None:
                e_obs = 1.0
            else:
                c = hamming(par.obs, obs)
                e_obs = par.e_obs + 1 if c == 0 else (par.e_obs * 0.6 + 1 if c == 1 else min(par.e_obs * 0.3, 2.0) + 1)
        if valid and y is None:
            y = self.w.score(x, e, self.rng)
        p = Prog(pid, gen, parent, x, obs, e, e_obs, y if valid else None, track, kind, moved, valid, self.w.basin(x))
        self.progs.append(p)
        self.byid[pid] = p
        return p

    def best(self):
        return max((p for p in self.progs if p.valid), key=lambda p: p.y)

    def open_track(self, gen, kind, root, race=True):
        tid = f"T{len(self.tracks) + 1}"
        t = {"id": tid, "kind": kind, "root": root, "opened": gen, "best": None, "best_id": None, "misses": 0,
             "exps": 0, "curve": [], "landed": False, "last_gain": gen}
        if race and self.race is not None and kind in ("drop", "flip", "restart"):
            self.race.start(t)
        self.tracks[tid] = t
        return t

    # ---------------------------------------------------------------- the start
    def start(self):
        w = self.w
        t1 = self.open_track(0, "seed", None)
        zero = self.add(0, None, w.trap, "T1", "seed", e=0.0, e_obs=0.0)
        t1["root"] = zero.id
        if not self.s.warm:
            self.update_track_best(t1, [zero])
            self.records = [0]
            return 0
        # warm: a climbed record hill (a lineage of 12 programs up to effort ~300) and a few earlier explorations
        x = w.trap
        path = list(range(self.s.d))
        self.rng.shuffle(path)
        prev = zero
        for i in [i for i in path if w.rec[i] != w.trap[i]]:
            x = tuple(w.rec[j] if j == i else x[j] for j in range(self.s.d))
            prev = self.add(0, prev.id, x, "T1", "deep")
        for step in range(9):
            prev = self.add(0, prev.id, x, "T1", "deep", e=prev.e + 35, e_obs=prev.e_obs + 35)
        for j in range(4):           # the earlier run's restarts, paused by its patience after 3 experiments
            t = self.open_track(0, "restart", zero.id, race=False)
            t["misses"] = 2
            q = self.add(0, zero.id, w.fresh(self.rng), t["id"], "restart")
            t["exps"] = 1
            self.update_track_best(t, [q])
            record_curve(t)
            for _ in range(2):
                q = self.add(0, q.id, q.x, t["id"], "deep")
                t["exps"] += 1
                self.update_track_best(t, [q])
                record_curve(t)
        self.update_track_best(t1, [p for p in self.progs if p.track == "T1"])
        self.main = "T1"
        for t in self.tracks.values():
            self.place(0, t)
        if self.race is not None:    # a v9 continuation judges them as the race would have (helix9/warm.py)
            retro_judge(self.race, list(self.tracks.values()), 0, keep=max(1, min(self.p.cap, 4) - 1), kinds=("restart",),
                        main=self.main)
        self.records = [-6, -4, -2, 0]
        return 0

    # ---------------------------------------------------------------- tracks and hills
    def update_track_best(self, t, mine):
        top = max((p for p in mine if p.valid and p.moved), key=lambda p: p.y, default=None)
        if top is not None and (t["best"] is None or top.y > t["best"] + self.floor(t["best"])):
            t["best"], t["best_id"] = top.y, top.id
            return True
        return False

    def same_hill(self, x, y):
        """v8's register compares what programs produce, within a radius: here, designs at most one decision apart
        in the same basin produce nearly the same output."""
        return self.w.basin(x) == self.w.basin(y) and sum(1 for a, b in zip(x, y) if a != b) <= 1

    def place(self, gen, t):
        """v8's register: a track's best lands on a known hill (within the radius) or founds a new one."""
        if not t["best_id"]:
            return None
        p = self.byid[t["best_id"]]
        own = self.hills.get(t.get("hill")) if t.get("hill") is not None else None
        if own is not None and own.get("by") == t["id"]:          # it carries the hill it founded
            if p.y > own["score"]:
                own.update(top=p.id, score=p.y, x=p.x)
            return t["hill"]
        near = [hid for hid, h in self.hills.items() if self.same_hill(p.x, h["x"])]
        if near:
            hid = max(near, key=lambda h: self.hills[h]["score"])
            h = self.hills[hid]
            t["hill"] = hid
            if p.y > h["score"] + self.floor(h["score"]):
                h.update(top=p.id, score=p.y, x=p.x)
            elif t["kind"] in ("restart", "drop") and t["id"] != self.main:
                t["landed"] = True             # a new design that landed on a known hill below its top stops there
            return hid
        if t["exps"] >= 2 or t["id"] == self.main or gen == 0:
            hid = len(self.hills) + 1
            self.hills[hid] = {"top": p.id, "score": p.y, "x": p.x, "found": gen, "by": t["id"], "kind": t["kind"],
                               "basin": p.basin}
            t["hill"] = hid
            self.log(gen, "hill", f"new hill H{hid} by {t['id']} ({t['kind']}), in basin "
                                  f"{self.w.hills[p.basin]['name'] if not self.s.smooth else 'one'}")
        return t.get("hill")

    def live(self, t):
        if t["id"] == self.main or t.get("landed"):
            return False
        if t.get("race") is not None and self.race is not None:
            return self.race.live(t)
        return t["misses"] < self.PATIENCE.get(t["kind"], 1)

    # ---------------------------------------------------------------- levels (v7)
    def level(self, gen):
        pts = self.records[-9:]
        gaps = [b - a for a, b in zip(pts, pts[1:])][-8:]
        typ = 3.0 if len(gaps) < 2 else min(max(statistics.median(gaps), 1.0), 12.0)
        stall = max(0, gen - 1 - self.records[-1])
        return (2 if stall > 2 * typ + 1 else 1 if stall > typ else 0), stall

    # ---------------------------------------------------------------- the model
    def fit(self):
        rows, count = [], Counter()
        for p in self.progs:
            if p.valid and p.moved:
                count[tuple(sorted(p.obs.items()))] += 1
        for p in self.progs:
            if p.valid and p.moved:
                rows.append({"coord": p.obs, "y": p.y, "effort": p.e_obs, "w": 1.0 / count[tuple(sorted(p.obs.items()))]})
        levels = {a: self.cb.values(a) + [f"{a}.new"] for a in self.cb.active_axes()}
        self.model = LandscapeModel(levels, pairs_max=6).fit(rows)
        return self.model

    def levels(self):
        return {a: self.cb.values(a) + [f"{a}.new"] for a in self.cb.active_axes()}

    def discover(self, gen):
        """Programs with the same observed design but very different effort-adjusted scores: something unnamed
        differs. If it is a hidden axis, the (simulated) cartographer names it."""
        if not self.w.hidden or not self.model or not self.model.ready:
            return
        res = dict(self.model.residuals())
        rows = [p for p in self.progs if p.valid and p.moved]
        by = {}
        for i, p in enumerate(rows):
            if abs(res.get(i, 0)) > 2.5:
                by.setdefault(tuple(sorted(p.obs.items())), []).append(p)
        for key, ps in by.items():
            ps = sorted(ps, key=lambda p: p.y)
            for lo, hi in [(ps[0], ps[-1])] if len(ps) >= 2 else []:
                diff = [i for i in self.w.hidden if lo.x[i] != hi.x[i] and f"decision {self.w.axes[i]}" not in
                        [self.cb.axes[a]["name"] for a in self.cb.active_axes()]]
                self.calls["discover"] += 1
                if diff and self.rng.random() < 0.8:
                    i = diff[0]
                    a = self.w.axes[i]
                    aid = self.cb.add_axis(f"decision {a}", gen, "discovery",
                                           values=[f"option {v + 1} of {a}" for v in range(self.s.k)])
                    self.known[aid] = i
                    self.log(gen, "discovery", f"a hidden axis ({a}) was named, as {aid}")
                    for p in self.progs:                       # backfill: hill tops, track bests and their programs
                        if p.valid and (p.id in {h["top"] for h in self.hills.values()} or
                                        p.id in {t["best_id"] for t in self.tracks.values()} or p.gen >= gen - 3):
                            p.obs = {**p.obs, aid: f"{aid}.v{p.x[i] + 1}"}
                    return

    # ---------------------------------------------------------------- one generation
    def log(self, gen, kind, text):
        if self.events is not None:
            self.events.append({"gen": gen, "kind": kind, "text": text})

    def child(self, gen, base, kind, track, change=None, fresh=False):
        """One experiment. change: {axis index: value} asked of the coder; fresh: a new program from nothing."""
        t = self.tracks[track]
        t["exps"] += 1
        if self.rng.random() < self.s.fail:
            return self.add(gen, base.id, base.x, track, kind, valid=False)
        if fresh:
            x = self.w.decode(self.w.fresh(self.rng), {}, self.rng)
            return self.add(gen, base.id, x, track, kind, e=1.0, e_obs=1.0)
        if change:
            x = self.w.decode(base.x, change, self.rng)
        else:
            x = base.x
        if x == base.x:                                   # a polish
            y = self.w.score(x, base.e + 1, self.rng)
            if y <= base.y + self.floor(base.y) and self.rng.random() < self.s.unchanged:
                return self.add(gen, base.id, x, track, kind, obs=dict(base.obs), e=base.e, e_obs=base.e_obs,
                                moved=False, y=base.y)
            return self.add(gen, base.id, x, track, kind, obs=dict(base.obs), y=y)
        full = kind in ("drop", "flip") and self.p.readback          # a landing is read back in full
        obs = self.observe(x, None if full else base)
        if change and not self.p.readback:
            obs = {**base.obs}
            for i, v in change.items():
                aid = next((a for a, j in self.known.items() if j == i), None)
                if aid:
                    obs[aid] = f"{aid}.v{v + 1}"
        return self.add(gen, base.id, x, track, kind, obs=obs)

    def sample_parent(self, pool, alpha=1.0):
        pool = sorted(pool, key=lambda p: -p.y)
        kids = Counter(p.parent for p in self.progs)
        wts = np.array([1.0 / (1 + i) ** alpha / math.sqrt(1 + kids[p.id]) for i, p in enumerate(pool)])
        return pool[int(self.rng.choice(len(pool), p=wts / wts.sum()))]

    def explore(self, gen, kind):
        """Opens a new exploration track of this kind and runs its first experiment."""
        best = self.best()
        if kind == "backtrack":
            cands = [p for p in self.progs if p.valid and p.moved and p.track != self.main
                     and p.id not in {t["root"] for t in self.tracks.values()}]
            cands = sorted(cands, key=lambda p: -p.y)[:12] or [best]
            base = cands[int(self.rng.integers(len(cands)))]
            t = self.open_track(gen, kind, base.id)
            return self.child(gen, base, kind, t["id"])
        if kind == "restart":
            zero = self.progs[0]
            t = self.open_track(gen, kind, zero.id)
            self.log(gen, "open", f"{t['id']} restart")
            return self.child(gen, zero, kind, t["id"], fresh=True)
        axes = self.cb.reliable_axes()
        levels = self.levels()
        sample = None
        if self.p.model and self.model is not None and self.model.ready:
            sample = self.model.sample(self.rng)
        if kind == "flip":
            if self.p.flip != "shared" and (self.p.model or self.p.name.startswith("v9")):
                pick = choose_flip(sample, best.obs, axes, levels, self.rng, tried=self.flipped,
                                   compatible=self.cb.compatible)
                change = pick[1] if pick else None
            else:                                          # v8: one decision every known hill shares, at random
                tops = [self.byid[h["top"]].obs for h in self.hills.values()]
                sh = shared_axes(tops, axes) or {a: best.obs.get(a) for a in axes}
                a = list(sh)[int(self.rng.integers(len(sh)))]
                opts = [v for v in levels[a] if v != best.obs.get(a) and not v.endswith(".new")]
                change = {a: opts[int(self.rng.integers(len(opts)))]}
            if not change:
                return self.explore(gen, "backtrack")
            self.flipped.add(tuple(sorted(change.items())))
            t = self.open_track(gen, kind, best.id)
            self.log(gen, "open", f"{t['id']} flip: {self.words(change)}")
            return self.child(gen, best, kind, t["id"], change=self.to_x(change, best.x))
        if kind == "drop":
            avoid = [self.byid[h["top"]].obs for h in self.hills.values()]
            pick = choose_drop(sample, best.obs, axes, levels, self.rng, avoid=avoid, min_dist=2, tabu=self.dropped,
                               compatible=self.cb.compatible, kmin=self.p.kmin, kmax=self.p.kmax, n=600)
            if pick is None:
                return self.explore(gen, "restart")
            coord, change, rating = pick
            self.dropped.add(tuple(sorted(change.items())))
            t = self.open_track(gen, kind, best.id)
            self.log(gen, "open", f"{t['id']} drop: {self.words(change)}")
            return self.child(gen, best, kind, t["id"], change=self.to_x(change, best.x))
        raise ValueError(kind)

    def continue_track(self, gen, t):
        """A follow-up on a side track: mostly a polish; sometimes a one-axis move (v9: the move the model suggests
        from the track's best, as the planner's slot text does; v8: the coder's own idea)."""
        base = self.byid[t["best_id"]] if t["best_id"] else self.byid[t["root"]]
        t["served"] = gen
        change = None
        if self.rng.random() < 0.25:
            pick = None
            if self.p.model and self.model is not None and self.model.ready:
                pick = choose_flip(self.model.sample(self.rng), base.obs, self.cb.reliable_axes(), self.levels(),
                                   self.rng, compatible=self.cb.compatible)
            if pick:
                change = self.to_x(pick[1], base.x)
            else:
                x = self.w.mutate(base.x, self.rng)
                change = {i: x[i] for i in range(self.s.d) if x[i] != base.x[i]}
        return self.child(gen, base, "track", t["id"], change=change)

    def generation(self, gen):
        prev = self.best()
        lv, stall = self.level(gen)
        early = (not self.s.warm) and gen <= 3
        n_exp = min(max(lv, 2 if early else 0), self.s.deep - 1)
        kids = []
        if self.p.scs:
            pool = [p for p in self.progs if p.valid]
            for _ in range(self.s.deep + self.s.wide):
                base = pool[int(self.rng.integers(len(pool)))]
                r = self.rng.random()
                tr = base.track
                if r < 0.1:
                    kids.append(self.child(gen, self.progs[0], "scs", tr, fresh=True))
                elif r < 0.5:
                    x = self.w.mutate(base.x, self.rng)
                    kids.append(self.child(gen, base, "scs", tr, change={i: x[i] for i in range(self.s.d) if x[i] != base.x[i]}))
                else:
                    kids.append(self.child(gen, base, "scs", tr))
        else:
            # planned: main slots, then exploration slots (live tracks first, then new ones in rotation)
            mt = self.tracks[self.main]
            for _ in range(self.s.deep - n_exp):
                base = self.byid[mt["best_id"]] if mt["best_id"] else prev
                change = None
                if self.rng.random() < 0.25:
                    x = self.w.mutate(base.x, self.rng)
                    change = {i: x[i] for i in range(self.s.d) if x[i] != base.x[i]}
                kids.append(self.child(gen, base, "main", self.main, change=change))
            live = [t for t in self.tracks.values() if self.live(t)]
            if self.race is not None:
                # the race's schedule: running tracks are served in turn (least recently served first); a new track
                # opens only while fewer than RUNNING_CAP are running
                if self.p.serve == "gain":
                    live.sort(key=lambda t: (t["misses"] > 0, t.get("served", t["opened"]), t["opened"]))
                elif self.p.serve == "standing":
                    all_t = list(self.tracks.values())
                    live.sort(key=lambda t: (-self.race.standing(t, all_t), t.get("served", t["opened"])))
                else:
                    live.sort(key=lambda t: (t.get("served", t["opened"]), t["opened"]))
                live = live[:n_exp]
                if len([t for t in self.tracks.values() if self.live(t)]) < self.p.cap and len(live) == n_exp \
                        and n_exp >= 2 and gen % 2 == 0:
                    live = live[:-1]
            else:
                live.sort(key=lambda t: (t["misses"], -t["opened"]))
                live = live[:n_exp]
                if n_exp >= 2 and len(live) == n_exp and gen % 2 == 0:
                    live = live[:-1]
            opened = Counter(t["kind"] for t in self.tracks.values() if t["opened"] > 0)
            opened["revive"] = self.revived / 2
            for i in range(n_exp):
                if live:
                    kids.append(self.continue_track(gen, live.pop(0)))
                    continue
                waiting = self.race is not None and any((t.get("race") or {}).get("status") == "waiting"
                                                        for t in self.tracks.values())
                kinds = self.p.kinds + (("revive",) if waiting else ())
                kind = min(kinds, key=lambda k: (opened[k], kinds.index(k)))
                if kind == "revive":          # an earlier exploration's turn in the race's queue (helix9/race.py)
                    t = take_waiting(list(self.tracks.values()), gen)
                    self.revived += 1
                    opened["revive"] += 0.5
                    self.log(gen, "race", f"{t['id']} races again (its turn in the queue)")
                    kids.append(self.continue_track(gen, t))
                    continue
                opened[kind] += 1
                kids.append(self.explore(gen, kind))
            # the wide loop
            pool = [p for p in self.progs if p.valid and p.gen < gen]
            for j in range(self.s.wide):
                side = [p for p in pool if p.track != self.main]
                par = self.sample_parent(side if (lv >= 2 and j == self.s.wide - 1 and side) else pool,
                                         alpha=1.0 if lv == 0 else 0.5)
                change = None
                if self.rng.random() < 0.35:
                    x = self.w.mutate(par.x, self.rng)
                    change = {i: x[i] for i in range(self.s.d) if x[i] != par.x[i]}
                self.tracks[par.track]["exps"] += 0              # mutations don't spend a track's planned effort
                c = self.child(gen, par, "wide", par.track, change=change)
                self.tracks[par.track]["exps"] -= 1
                kids.append(c)
        # tracks
        planned = Counter(k.track for k in kids if k.kind != "wide")
        for tid, t in self.tracks.items():
            mine = [k for k in kids if k.track == tid]
            gained = self.update_track_best(t, mine) if mine else False
            if gained:
                t["misses"], t["last_gain"] = 0, gen
                if self.race is not None and t.get("race") and t["race"]["status"] in ("paused", "waiting") and \
                        any(k.kind == "wide" for k in mine):
                    self.race.wake(t)
            elif tid in planned and t["opened"] != gen:
                t["misses"] += 1
            if mine:
                record_curve(t)
            if self.race is not None and t.get("race") and t["id"] != self.main:
                ev = self.race.decide(t, list(self.tracks.values()), gen)
                if ev:
                    self.log(gen, "race", ev)
            if t["best_id"] and t.get("placed") != t["best_id"]:
                t["placed"] = t["best_id"]
                self.place(gen, t)
        best = self.best()
        if best.track != self.main:
            ms = self.tracks[self.main]["best"]
            if ms is None or best.y > ms + self.floor(ms):
                self.log(gen, "record", f"{best.track} took the record ({best.y:.4f}, basin "
                                        f"{self.w.hills[best.basin]['name'] if not self.s.smooth else best.basin})")
                self.main = best.track
        if best.y > prev.y + self.floor(prev.y):
            self.records.append(gen)
        # v9's map: the model, and discovery
        if self.p.model or self.p.discovery:
            self.fit()
            if self.p.discovery and gen % 4 == 0:
                self.discover(gen)
        self.hist.append({"gen": gen, "best": best.y, "true": self.w.height(best.x), "basin": best.basin,
                          "level": lv, "hills": len(self.hills)})

    def run(self):
        g0 = self.start()
        for gen in range(g0 + 1, g0 + self.s.gens + 1):
            self.generation(gen)
        return self.result()

    def result(self):
        best = self.best()
        tall = next((j for j, h in enumerate(self.w.hills) if h["name"] == "tall"), None)
        first = next((h["gen"] for h in self.hist if tall is not None and h["basin"] == tall
                      and h["true"] >= self.w.hills[tall]["peak"] - 0.02), None)
        visited = {p.basin for p in self.progs if p.valid}
        return {"family": self.s.family, "policy": self.p.name, "seed": self.s.seed, "best": best.y,
                "true": self.w.height(best.x), "best_peak": self.w.best_peak,
                "basin": self.w.hills[best.basin]["name"] if not self.s.smooth else "one",
                "tall_found": tall is not None and any(p.basin == tall and p.valid for p in self.progs),
                "tall_record": first, "basins_visited": len(visited), "hills": len(self.hills),
                "programs": len(self.progs), "discovered": len(self.cb.active_axes()) - (self.s.d - self.s.hidden)}

    # ---------------------------------------------------------------- the viewer's data (viz/mapview.html)
    def view(self):
        from helix9.mapview import sim_view
        return sim_view(self)


# ---------------------------------------------------------------------------------------------- batches
def run_one(family, pol, seed, **kw):
    return Sim(spec_for(family, seed, **kw), policy(pol)).run()


def _work(args):
    family, pol, seed = args
    t0 = time.time()
    try:
        r = run_one(family, pol, seed)
    except Exception as exc:                                     # noqa: BLE001  (one failure never sinks a batch)
        import traceback
        return {"family": family, "policy": pol, "seed": seed, "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-1500:]}
    r["seconds"] = round(time.time() - t0, 2)
    return r


def batch(families, policies, seeds, workers=2, out=None, log=print):
    """Every family x policy x seed; results are appended to `out` (sim_runs.jsonl) as they finish, and a run
    already there is not repeated (a batch can be resumed)."""
    done = {}
    if out is not None and Path(out).exists():
        for line in Path(out).read_text().splitlines():
            try:
                r = json.loads(line)
                if "error" not in r:
                    done[(r["family"], r["policy"], r["seed"])] = r
            except ValueError:
                pass
    jobs = [(f, p, s) for f in families for p in policies for s in range(1, seeds + 1) if (f, p, s) not in done]
    rows = list(done.values())
    fh = open(out, "a") if out is not None else None
    t0 = time.time()

    def take(r):
        rows.append(r)
        if fh:
            fh.write(json.dumps(r) + "\n")
            fh.flush()
        n = len(rows)
        if n % 50 == 0 or "error" in r:
            log(f"   {n} of {len(jobs) + len(done)} runs ({time.time() - t0:.0f} s)"
                + (f"; FAILED {r['family']}/{r['policy']}/{r['seed']}: {r['error']}" if "error" in r else ""))
    if workers > 1:
        from multiprocessing import Pool
        with Pool(workers) as pool:
            for r in pool.imap_unordered(_work, jobs, chunksize=2):
                take(r)
    else:
        for j in jobs:
            take(_work(j))
    if fh:
        fh.close()
    return rows


def summarise(rows):
    """Per family and policy: the mean true height of the final best, how often the taller hill was found and held
    the record, and the median generation it took."""
    out = {}
    for r in rows:
        if "error" in r:
            continue
        out.setdefault((r["family"], r["policy"]), []).append(r)
    table = {}
    for (f, p), rs in out.items():
        t = [r["true"] for r in rs]
        firsts = [r["tall_record"] for r in rs if r["tall_record"] is not None]
        table[(f, p)] = {"n": len(rs), "mean_true": statistics.mean(t),
                         "se": statistics.stdev(t) / math.sqrt(len(t)) if len(t) > 1 else 0.0,
                         "tall_record": sum(1 for r in rs if r["tall_record"] is not None) / len(rs),
                         "tall_found": sum(1 for r in rs if r["tall_found"]) / len(rs),
                         "median_gen": statistics.median(firsts) if firsts else None,
                         "basins": statistics.mean(r["basins_visited"] for r in rs)}
    return table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", default="broad", choices=sorted(FAMILIES))
    ap.add_argument("--policy", default="v9", choices=POLICIES)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--policies", default=",".join(POLICIES))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=None)
    ap.add_argument("--view", default=None, help="write the viewer's data for this run (viz/mapview.html)")
    a = ap.parse_args(argv)
    if a.batch:
        t0 = time.time()
        if a.out:
            Path(a.out).mkdir(parents=True, exist_ok=True)
        rows = batch(a.families.split(","), a.policies.split(","), a.seeds, a.workers,
                     out=(Path(a.out) / "sim_runs.jsonl") if a.out else None, log=lambda m: print(m, flush=True))
        tab = summarise(rows)
        for (f, p), x in sorted(tab.items()):
            print(f"{f:10s} {p:15s} true {x['mean_true']:.4f} ± {x['se']:.4f}  tall found {x['tall_found']:.0%} "
                  f"record {x['tall_record']:.0%}  median gen {x['median_gen']}  basins {x['basins']:.1f}")
        print(f"{len(rows)} runs in {time.time() - t0:.0f} s")
        return
    sim = Sim(spec_for(a.family, a.seed), policy(a.policy), record_events=bool(a.view))
    r = sim.run()
    print(json.dumps(r, indent=1))
    if a.view:
        Path(a.view).parent.mkdir(parents=True, exist_ok=True)
        Path(a.view).write_text(json.dumps(sim.view()))


if __name__ == "__main__":
    sys.exit(main())
