"""One Helix v9 run: v8, plus a design map with coordinates (docs/V9_DESIGN.md, docs/SEARCH_SPACE_MODEL.md).

    python -m helix9.run --seed 1 --gens 30 --out runs/v9/v9-s1
    python -m helix9.run --out runs/v9/v9-s1                     # resumes (state.json is there)
    python -m helix9.run --gens 2 --fake --out /tmp/x            # no model calls

Everything in v8 (helix8/run.py) stays: the roles, 3 planned experiments and 3 mutations a generation, the stall
levels, the main track's guaranteed slot, tracks never closed, alternatives, the noise floor, warm starts, the register
of hills by what programs produce, moved-only track bests, the Cartographer. While the record climbs (level 0), a
generation is v8's plus a read-only table and the annotation of its programs.

What v9 adds:
- **A codebook** of design decisions (axes) and options (values), with permanent ids (helix9/codebook.py). It grows
  from the run's own programs: the annotator's new values and axes, the Cartographer's scans (matched against it, not
  replacing it), and discoveries.
- **Coordinates.** Every new program is read by an annotator (helix9/annotate.py): from its diff, inheriting its base's
  coordinate, or in full (no base coordinate, a rewrite, a landing to check, and a sample read twice to measure each
  axis's reliability). An axis read unreliably (agreement below `reliable_min`) stops steering the search.
- **A model of the landscape** over coordinates (helix9/model.py): main effects, screened interactions, an effort
  term, empirical-Bayes shrinkage, frozen axes kept uncertain. The planner sees it as a table: each decision, its
  options, how many programs use each, their best, and the estimated effect with its uncertainty.
- **Exploration chosen from the map** (helix9/drops.py), by Thompson sampling, replacing v8's restart and its random
  flip: drops (2-4 decisions at once, at least 2 from every known hill's top), flips (one decision), and every
  `ablate_every` generations an ablation (one of the record's decisions undone, to measure what it is worth). The
  planner is given the target and plans how to build it; the coder gets it as a blueprint.
- **Read-back.** A drop's, flip's or ablation's program is read in full: if it doesn't make the target decisions, the
  track's next follow-up is told which are missing.
- **The fair race** (helix9/race.py) replaces v8's 2-follow-up patience for drops, flips and ablations: they are
  compared with tracks that started the same way, at the same effort, and continue while they keep rising. About half
  the exploration slots open new directions whatever races; at most `running_cap` race at once (the weakest at equal
  effort waits in a queue); racing tracks that gained at their last experiment are served first, then in turn.
- **Discovery.** Programs the map places at the same design, scoring further apart than the model explains, prompt the
  question "what design decision differs?"; the answer becomes a new axis.
- **Constructions on demand.** A base without a construction (a continuation from a pack that didn't hold it) is
  copied from a local folder (HELIX9_LOCAL_CONSTRUCTIONS) if one there verifies, else rebuilt by running its code from
  its nearest ancestor that has one (if close) or the program whose output is most like its own; rebuilds are
  approximate and logged. The wide loop samples the programs whose construction is at hand.
If the map can't steer (fewer than 2 reliable axes), exploration falls back to v8's kinds.
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
from dataclasses import dataclass, field

import numpy as np

from helix4 import prompts as P4
from helix4.archive import Program, make_diff, short
from helix4.llm import FakeLLM
from helix7.memory import outcome
from helix8.run import (Config as Config8, EXPLORE as EXPLORE8, KIND_WORDS as KIND_WORDS8, Run as Run8,
                        fake_answer as fake_answer8)
from helix9 import annotate as A
from helix9 import prompts as P
from helix9.codebook import Codebook, NEW, consolidate, hamming, is_new
from helix9.drops import choose_drop, choose_flip
from helix9.model import LandscapeModel
from helix9.race import RUNGS, Race, group_of, record_curve, take_waiting

MAP_KINDS = ("drop", "flip", "backtrack")
SEED_AXES = (    # generic design questions, with no options: every program-improvement problem has some version of them
    "How is a candidate solution represented?",
    "How is the first solution built?",
    "What quantity does the search optimise while it runs?",
    "Which moves or update steps change a solution?",
    "How does the search accept worse solutions or escape a local optimum?",
    "How is the problem's scale handled (all at once, coarse to fine, in parts)?",
    "Which parts, if any, are solved exactly?",
    "How is the time budget split between phases?",
)
RACE_KINDS = ("drop", "flip", "ablate", "restart")
KIND_WORDS = {**KIND_WORDS8, "drop": "a new design from the map", "ablate": "undo one of the record's decisions"}


@dataclass
class Config(Config8):
    condition: str = "v9"
    annotate: bool = True
    annotate_chars: int = 20000
    diff_lines: int = 250
    double_rate: float = 0.12         # programs read twice, independently, to measure each axis's reliability
    reliable_min: float = 0.5         # an axis read with less agreement than this stops steering
    model_min_rows: int = 12
    model_pairs: int = 6
    kmin: int = 2                     # a drop changes between kmin and kmax decisions ...
    kmax: int = 4
    drop_min_dist: int = 2            # ... and lands at least this many decisions from every known hill's top
    drop_candidates: int = 1500
    race_rule: str = "rising"
    race_rungs: tuple = RUNGS
    race_q: float = 0.5
    race_q_rising: float = 0.25
    race_min_cohort: int = 3
    running_cap: int = 3
    race_serve: str = "gain"          # racing tracks that gained at their last experiment are served first, then in turn
    breadth: str = "half"             # "half": about half the exploration slots open new directions whatever races, and
                                      # at most `running_cap` race at once (the weakest at equal effort waits in the
                                      # queue); "cap": a new direction opens only while fewer than `running_cap` race
    ablate_every: int = 12            # generations between two ablations (while exploring)
    discover_every: int = 4
    residual_z: float = 2.5
    map_axes: int = 10
    map_values: int = 6
    suggest_moves: bool = True
    seed_axes: bool = True            # an empty codebook starts with generic design questions (no options)
    max_axes: int = 16                # above this, a consolidation call merges axes that name the same decision


class Run(Run8):
    CONFIG = Config
    VERSION = "v9"

    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print, problem=None):
        super().__init__(out, cfg, llm=llm, gens=gens, log=log, problem=problem)
        self.map_lock = threading.Lock()
        self.record_read = {}
        for f in ("coords.jsonl", "codebook.jsonl", "annotations.jsonl", "rebuilt.jsonl"):
            if (self.dir / f).exists() and self.gen_done >= 0:
                self._truncate_jsonl(self.dir / f)
        rows = self._jsonl("codebook.jsonl")
        self.cb = Codebook(rows[-1]["codebook"]) if rows else Codebook()
        if not self.cb.axes and self.cfg.seed_axes:
            for q in SEED_AXES:
                self.cb.add_axis(q, max(self.gen_done, 0), "seed")
        self.coords = {}
        for r in self._jsonl("coords.jsonl"):
            if r.get("id") in self.archive.programs:
                self.coords[r["id"]] = r
        self.ann_rows = [r for r in self._jsonl("annotations.jsonl") if r.get("second") is not None]
        self.race = Race(rungs=self.cfg.race_rungs, q=self.cfg.race_q, q_rising=self.cfg.race_q_rising,
                         min_cohort=self.cfg.race_min_cohort, floor=self.floor, rule=self.cfg.race_rule)
        self.race.started = sum(1 for t in self.tracks.values() if t.get("race"))
        self.model = None
        self.asked = {tuple(x) for x in (self._jsonl("discoveries.jsonl") and
                                         [r.get("pair") for r in self._jsonl("discoveries.jsonl")] or []) if x}
        self.last_ablate = max([t["opened"] for t in self.tracks.values() if t.get("kind") == "ablate"] or [-10 ** 6])
        self.map_events = []
        self.ann_calls = 0
        self.rng9 = np.random.default_rng(self.cfg.seed * 104729 + max(self.gen_done, 0))

    # ---------------------------------------------------------------- the map's state
    def coord(self, pid):
        r = self.coords.get(pid)
        return self.cb.canonical(r["coord"]) if r else None

    def effort(self, pid):
        r = self.coords.get(pid)
        return r.get("effort") if r else None

    def set_coord(self, pid, gen, coord, how, effort=None, extra=None):
        p = self.archive.programs.get(pid)
        par = self.archive.programs.get(p.parent) if p is not None and p.parent else None
        if effort is None:
            pc = self.coord(par.id) if par is not None else None
            effort = A.effort_of(pc or {}, self.effort(par.id) if par is not None else None, coord,
                                 self.cb.active_axes()) if pc is not None else 1.0
        row = {"id": pid, "gen": gen, "coord": coord, "how": how, "effort": round(float(effort), 3), **(extra or {})}
        with self.map_lock:
            self.coords[pid] = row
            with (self.dir / "coords.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
        return row

    def axes(self):
        return self.cb.reliable_axes(self.cfg.reliable_min)

    def levels(self, axes=None):
        return {a: self.cb.values(a) + [f"{a}.{NEW}"] for a in (axes or self.axes())}

    def map_ready(self):
        return len(self.axes()) >= 2

    def fit_model(self):
        axes = self.axes()
        if len(axes) < 2:
            self.model = None
            return None
        rows, count = [], Counter()
        data, pids = [], []
        for pid, r in self.coords.items():
            p = self.archive.programs.get(pid)
            if p is None or not p.valid or p.score is None or not self.moved(p):
                continue
            c = {a: v for a, v in self.cb.canonical(r["coord"]).items() if a in axes}
            key = tuple(sorted(c.items()))
            count[key] += 1
            data.append((c, p.score, r.get("effort") or 1.0, key))
            pids.append(pid)
        for c, y, e, key in data:
            rows.append({"coord": c, "y": y, "effort": e, "w": 1.0 / count[key]})
        self.model_pids = pids
        m = LandscapeModel(self.levels(axes), pairs_max=self.cfg.model_pairs)
        m.fit(rows, min_rows=self.cfg.model_min_rows)
        self.model = m if m.ready else None
        return self.model

    def sample(self):
        return self.model.sample(self.rng9) if self.model is not None else None

    # ---------------------------------------------------------------- constructions on demand
    # ---------------------------------------------------------------- constructions of a continuation
    def local_folders(self):
        """Folders of constructions on this machine (HELIX9_LOCAL_CONSTRUCTIONS, comma-separated): the earlier run's
        own folder on the VM. Used on demand, each construction verified before use; nothing is copied in bulk."""
        if not hasattr(self, "_local_folders"):
            import os
            from pathlib import Path as _P
            self._local_folders = [_P(x) for x in os.environ.get("HELIX9_LOCAL_CONSTRUCTIONS", "").split(",")
                                   if x.strip() and _P(x.strip()).is_dir()]
        return self._local_folders

    def has_construction(self, p):
        if p is None:
            return False
        if p.role == "seed" or (self.dir / "constructions" / f"{p.id}.npy").exists():
            return True
        return any((f / f"{p.id}.npy").exists() for f in self.local_folders())

    def from_local(self, p):
        """Copies p's construction from a local folder if one there verifies (same steps, same score)."""
        from helix9.pack import verify
        for f in self.local_folders():
            c = f / f"{p.id}.npy"
            if not c.exists():
                continue
            try:
                arr = np.load(c)
            except Exception:                                    # noqa: BLE001
                continue
            ok, _why = verify(self.problem, arr, {"score": p.score, "n": p.n}) if hasattr(self.problem, "check") \
                else (True, "")
            if ok:
                np.save(self.dir / "constructions" / f"{p.id}.npy", np.asarray(arr, dtype=float))
                return str(f)
        return None

    def rebuild_start(self, p):
        """Where to run p's code from to rebuild its construction: its nearest ancestor with a construction if that is
        close (at most 3 steps up its lineage), else the program with a construction whose output is most like p's
        (by signature), else the farther ancestor."""
        anc, steps = self.archive.programs.get(p.parent) if p.parent else None, 1
        while anc is not None and self.archive.construction(anc.id) is None and anc.role != "seed":
            anc = self.archive.programs.get(anc.parent) if anc.parent else None
            steps += 1
        if anc is not None and steps <= 3:
            return anc, f"its ancestor {anc.id} ({steps} step{'s' if steps > 1 else ''} up)"
        sig = self.signatures.get(p.id)
        if sig is not None:
            have = [q for q in self.archive.valid() if q.id in self.signatures and q.id != p.id
                    and (self.dir / "constructions" / f"{q.id}.npy").exists()]
            if have:
                d = {q.id: self.signature_distance(sig, self.signatures[q.id]) for q in have}
                q = min(have, key=lambda q: (d[q.id], -(q.score or 0)))
                return q, f"{q.id}, the program with a construction whose output is most like {p.id}'s (distance {d[q.id]:.3f})"
        return anc, (f"its ancestor {anc.id} ({steps} steps up)" if anc is not None else "nothing")

    def ensure_construction(self, p, gen):
        """A base needs its construction. One missing (a continuation from GitHub, whose pack holds the constructions
        that matter most) is copied from a local folder if one verifies (lossless), else rebuilt by running its code
        again from the nearest start there is (rebuild_start); the rebuild is approximate and says so. Returns True if
        the construction is there now."""
        if p is None or not p.valid or self.archive.construction(p.id) is not None or p.role == "seed":
            return p is not None and (p.role == "seed" or self.archive.construction(p.id) is not None)
        src = self.from_local(p)
        if src:
            self._append("rebuilt.jsonl", {"gen": gen, "id": p.id, "from": src, "ok": True, "how": "local",
                                           "recorded": p.score, "rebuilt": p.score, "faithful": True})
            return True
        start_p, why = self.rebuild_start(p)
        start = self.archive.construction(start_p.id) if start_p is not None else None
        from helix47.evaluate import evaluate
        res = evaluate(self.problem, p.code, start, self.cfg.budget, self.cfg.mem_mb)
        ok = bool(res["valid"] and res["construction"] is not None)
        faithful = bool(ok and p.score is not None and abs(res["score"] - p.score) <= 1e-9 * max(abs(p.score), 1e-12))
        if ok:
            np.save(self.dir / "constructions" / f"{p.id}.npy", np.asarray(res["construction"], dtype=float))
        self._append("rebuilt.jsonl", {"gen": gen, "id": p.id, "from": start_p.id if start_p else None, "ok": ok,
                                       "how": "rebuilt", "recorded": p.score, "rebuilt": res.get("score"),
                                       "faithful": faithful})
        self.log(f"[{self.name}] gen {gen}: rebuilt the construction of {p.id} from {why}: "
                 + (f"{res['score']:.6f} (recorded {p.score:.6f}{', the same' if faithful else ''})" if ok
                    else f"failed ({res['error'][:120]})"))
        return ok

    def wide_parents(self, rng, pool, level):
        """v8's sampling over the archive, among the programs whose construction is at hand (in the run, or in a
        local folder): a continuation from GitHub alone samples the packed programs and everything new, instead of
        rebuilding a far-off program's construction for every wide child."""
        have = [q for q in pool if self.has_construction(q)]
        if len(have) < len(pool) and not getattr(self, "_said_wide_pool", False):
            self._said_wide_pool = True
            self.log(f"[{self.name}] the wide loop samples the {len(have)} of {len(pool)} programs whose construction "
                     f"is at hand (the pack, a local folder, or this run)")
        return super().wide_parents(rng, have or pool, level)

    def evaluate_child(self, p, parent, code):
        if parent is not None and parent.role != "seed" and self.archive.construction(parent.id) is None:
            self.ensure_construction(parent, p.gen)
        return super().evaluate_child(p, parent, code)

    # ---------------------------------------------------------------- the race
    def live(self, t):
        if t["id"] == self.main_track():
            return False
        if t.get("race"):
            if t.get("kind") in ("drop", "restart") and t.get("hill_status") == "on":
                return False                            # landed on a known hill below its top: nothing new
            return self.race.live(t)
        return super().live(t)

    def open_track(self, gen, kind, root, revives=None, flips=None, target=None):
        if kind not in ("drop", "ablate") and not (kind == "flip" and target is not None):
            tid = super().open_track(gen, kind, root, revives, flips)
            if kind in RACE_KINDS and self.map_ready():
                self.race.start(self.tracks[tid])
            return tid
        n = len(self.tracks) + 1
        while f"T{n}" in self.tracks:
            n += 1
        tid = f"T{n}"
        words = self.blueprint_short(target)
        src = {"drop": f"a drop to {words}, from {root}", "flip": f"a flip of {words} on {root}",
               "ablate": f"an ablation of {words} on {root}"}[kind]
        self.tracks[tid] = {"id": tid, "kind": kind, "root": root, "opened": gen, "source": src, "revives": None,
                            "flips": words if kind == "flip" else None, "best": None, "best_id": None, "misses": 0,
                            "last_gain": gen, "closing": None, "exps": 0, "hill": None, "hill_status": None,
                            "target": target, "base_coord": self.coord(root), "served": gen}
        self.race.start(self.tracks[tid])
        return tid

    def update_tracks(self, gen, children, exps, prev_best):
        events = super().update_tracks(gen, children, exps, prev_best)
        racing = {t["id"] for t in self.tracks.values() if t.get("race")}
        events = [e for e in events if not (e.endswith("paused (no gain on its own best)") and e.split()[0] in racing)]
        wide_gain = {c.plan.get("track") for c in children if c is not None and c.role == "wide" and c.valid
                     and outcome(c, self) == "gain"}
        for t in self.tracks.values():
            if not t.get("race"):
                continue
            if t["last_gain"] == gen and t["id"] in wide_gain and t["race"]["status"] in ("paused", "waiting"):
                if self.race.wake(t):
                    events.append(f"{t['id']} woken by a gain from the wide loop (race: on to {t['race']['budget']} "
                                  f"experiments)")
            record_curve(t, gen)
            if t["id"] != self.main_track():
                ev = self.race.decide(t, list(self.tracks.values()), gen)
                if ev:
                    events.append(ev)
        if self.cfg.breadth == "half":
            events += self.race_pool(gen)
        return events

    def race_pool(self, gen):
        """At most `running_cap` tracks race at once: the weakest at equal effort waits in the queue, to be taken
        again in turn (helix9/race.py, take_waiting)."""
        all_t = list(self.tracks.values())
        main = self.main_track()
        running = [t for t in all_t if t["id"] != main and (t.get("race") or {}).get("status") == "running"]
        if len(running) <= self.cfg.running_cap:
            return []
        stand = {t["id"]: self.race.standing(t, all_t) for t in running}
        running.sort(key=lambda t: (-stand[t["id"]], -(t["best"] if t.get("best") is not None else -1e300)))
        out = []
        for t in running[self.cfg.running_cap:]:
            t["race"]["status"] = "waiting"
            t["race"]["queue"] = round(1.0 - stand[t["id"]], 4)
            t["race"]["decisions"].append({"gen": gen, "rung": t["race"]["budget"], "best": t.get("best"), "go": True,
                                           "cap": True, "why": f"waits its turn: {len(running)} racing, and it is "
                                                               f"among the weakest at equal effort"})
            out.append(f"{t['id']} waits its turn to race ({len(running)} racing; among the weakest at equal effort)")
        return out

    # ---------------------------------------------------------------- targets from the map
    def blueprint_lines(self, change, base_coord=None):
        out = []
        for a, v in (change or {}).items():
            name = self.cb.name(a)
            if is_new(v):
                listed = "; ".join(self.cb.value_name(x) for x in self.cb.values(a)[:6]) or "-"
                out.append(f"- {a} ({name}): a new option of your choice, unlike the known ones ({listed})")
            else:
                was = (base_coord or {}).get(a)
                out.append(f"- {a} ({name}): {self.cb.value_name(v)}"
                           + (f" (the base uses: {self.cb.value_name(was)})" if was and was != v else ""))
        return "\n".join(out)

    def blueprint_short(self, change):
        return "; ".join(f"{a} -> {'a new option' if is_new(v) else short(self.cb.value_name(v), 50)}"
                         for a, v in (change or {}).items()) or "?"

    def tried_changes(self):
        since = self.last_record()
        out = set()
        for t in self.tracks.values():
            if t.get("target") and t["opened"] > since:
                out.add(tuple(sorted(t["target"].items())))
        return out

    def hill_coords(self):
        return [c for c in (self.coord(h["top"]) for h in self.hills.values()) if c]

    def pick_drop(self, best):
        base = self.coord(best.id)
        if base is None:
            return None
        # only decisions whose value the base is known to have: a change of an unknown value can't be read back
        pick = choose_drop(self.sample(), base, [a for a in self.axes() if a in base], self.levels(), self.rng9,
                           avoid=self.hill_coords(),
                           min_dist=self.cfg.drop_min_dist, tabu={tuple(sorted(t["target"].items())) for t in
                                                                  self.tracks.values() if t.get("target")},
                           compatible=self.cb.compatible, kmin=self.cfg.kmin, kmax=self.cfg.kmax,
                           n=self.cfg.drop_candidates)
        return pick

    def pick_flip(self, best):
        base = self.coord(best.id)
        if base is None:
            return None
        return choose_flip(self.sample(), base, [a for a in self.axes() if a in base], self.levels(), self.rng9,
                           tried=self.tried_changes(), compatible=self.cb.compatible)

    def pick_ablation(self, best):
        """One of the record's decisions that its lineage changed at some point, undone (least recently ablated)."""
        rc = self.coord(best.id) or {}
        done = Counter(a for t in self.tracks.values() if t.get("kind") == "ablate" for a in (t.get("target") or {}))
        cands = []
        for q in self.archive.lineage(best.id, depth=100000)[:-1]:
            qc = self.coord(q.id) or {}
            for a in self.axes():
                if rc.get(a) and qc.get(a) and qc[a] != rc[a]:
                    cands.append((done[a], -q.gen, a, qc[a]))
        if not cands:
            return None
        _, _, a, v = sorted(cands)[0]
        return {**rc, a: v}, {a: v}, None

    def suggestion(self, t):
        if not self.cfg.suggest_moves or self.model is None or not t.get("best_id"):
            return ""
        base = self.coord(t["best_id"])
        if base is None:
            return ""
        pick = choose_flip(self.sample(), base, self.axes(), self.levels(), self.rng9, compatible=self.cb.compatible)
        return P.MOVE_HINT.format(move=self.blueprint_short(pick[1])) if pick else ""

    # ---------------------------------------------------------------- slots
    def make_slots(self, gen, n_explore):
        if not self.map_ready():
            return super().make_slots(gen, n_explore)
        slots = [{"kind": "main"} for _ in range(self.cfg.deep - n_explore)]
        all_live = [t for t in self.tracks.values() if self.live(t)]
        racing = sorted((t for t in all_live if t.get("race")),
                        key=lambda t: ((t.get("misses", 0) > 0) if self.cfg.race_serve == "gain" else False,
                                       t.get("served", t["opened"]), t["opened"]))
        others = sorted((t for t in all_live if not t.get("race")), key=self.priority)
        if self.cfg.breadth == "half":  # breadth: about half the exploration slots open new directions
            live = (racing + others)[:(n_explore // 2 if n_explore >= 2 else gen % 2)]
        else:
            live = (racing + others)[:n_explore]
            if n_explore >= 2 and len(live) == n_explore and gen % 2 == 0 and len(racing) < self.cfg.running_cap:
                live = live[:-1]      # breadth: a new direction every other generation, while few tracks race
        opened = Counter(t["kind"] for t in self.tracks.values() if t["opened"] > (self.warm_gen or 0))
        # an earlier run's explorations that qualified to race again wait their turn (helix9/race.py, retro_judge):
        # one is taken as a new direction, about twice as often as each kind of new exploration
        opened["revive"] = sum(1 for t in self.tracks.values() for d in (t.get("race") or {}).get("decisions", [])
                               if d.get("why") == "its turn came: racing again") / 2
        used = []
        best = self.archive.best()
        for _ in range(n_explore):
            if live:
                t = live.pop(0)
                t["served"] = gen
                slots.append({"kind": "track", "track": t["id"]})
                continue
            kind = None
            if gen - self.last_ablate >= self.cfg.ablate_every and "ablate" not in used:
                kind = "ablate"
            waiting = any((t.get("race") or {}).get("status") == "waiting" for t in self.tracks.values())
            avail = [k for k in MAP_KINDS + (("revive",) if waiting else ()) if k not in used
                     and (k != "backtrack" or self.backtrack_candidates())]
            order = MAP_KINDS + ("revive",)
            for k in ([kind] if kind else []) + sorted(avail, key=lambda k: (opened[k], order.index(k))):
                if k == "revive":
                    t = take_waiting(list(self.tracks.values()), gen)
                    if t is None:
                        continue
                    t["served"] = gen
                    used.append(k)
                    opened[k] += 0.5
                    self.map_events.append(f"{t['id']} races again (its turn in the queue of earlier explorations)")
                    slots.append({"kind": "track", "track": t["id"]})
                    break
                s = self.target_slot(k, best)
                if s is not None:
                    used.append(k)
                    opened[k] += 1
                    slots.append(s)
                    break
            else:
                slots.append({"kind": "backtrack"} if self.backtrack_candidates() else {"kind": "restart"})
        return self.fill_slot_texts(slots, best)

    def target_slot(self, kind, best):
        if kind == "backtrack":
            return {"kind": "backtrack"}
        pick = {"drop": self.pick_drop, "flip": self.pick_flip, "ablate": self.pick_ablation}[kind](best)
        if pick is None:
            return None
        coord, change, rating = pick
        return {"kind": kind, "map": True, "target": change, "target_coord": coord, "rating": rating,
                "base": best.id}

    def fill_slot_texts(self, slots, best):
        for n, s in enumerate(slots, 1):
            s["n"] = n
            k = s["kind"]
            if s.get("map"):
                bp = self.blueprint_lines(s["target"], self.coord(s["base"]))
                key = {"drop": "drop", "flip": "flip9", "ablate": "ablate"}[k]
                s["text"] = P.SLOT_TEXT[key].format(n=n, blueprint=bp, base=s["base"])
                s["options"] = [s["base"]]
        for s in slots:
            if s.get("map"):
                continue
            n, k = s["n"], s["kind"]
            if k == "main":
                s["text"] = P.SLOT_TEXT["main"].format(n=n)
            elif k == "backtrack":
                c = self.backtrack_candidates()
                s["options"] = [pid for pid, _ in c]
                opts = "\n".join(f"- {self.archive.programs[pid].line()}: {why}; {self.hill_label(pid)}; "
                                 f"{short(self.archive.programs[pid].intent, 100)}" for pid, why in c)
                s["text"] = P.SLOT_TEXT["backtrack"].format(n=n, options=opts)
            elif k == "restart":
                seed = self.seed_program()
                s["text"] = P.SLOT_TEXT["restart"].format(n=n, seed=self.bold_seed_text() if seed else "any program",
                                                          chain=self.chain())
            elif k == "track":
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
                if t.get("race"):
                    r = t["race"]
                    why += (f". It is racing: {t.get('exps', 0)} experiments so far, judged at {r['budget']} against "
                            f"tracks that started the same way")
                if t.get("mismatch"):
                    why += ". " + P.MISS_NOTE.format(missing=self.blueprint_short(t["mismatch"]))[:-1]
                s["options"] = [p.id for p in mem] or [t["root"]]
                score = f"{t['best']:.6f}" if t["best"] is not None else "none yet"
                s["text"] = P.SLOT_TEXT["track"].format(n=n, track=t["id"], why=why, options=opts,
                                                        best=t["best_id"] or t["root"], score=score)
                hint = self.suggestion(t) if t.get("race") else ""
                if hint:
                    s["text"] += "\n" + hint
        return slots

    def assign(self, gen, s, e):
        if not s.get("map"):
            x = super().assign(gen, s, e)
            return x
        k = s["kind"]
        if e is None:
            x = {"base": None, "hypothesis": "(no plan: the researcher's reply was unusable)",
                 "change": f"Build the design the slot asks for: {self.blueprint_short(s['target'])}.", "prediction": "",
                 "builds_on": [], "fallback": True}
        else:
            x = {key: e.get(key) for key in ("base", "hypothesis", "change", "prediction", "builds_on")}
        if not isinstance(x.get("builds_on"), list):
            x["builds_on"] = [str(x["builds_on"])] if x.get("builds_on") else []
        x["slot"], x["kind"] = s["n"], k
        req = str(x.get("base") or "").strip()
        if req and req != s["base"]:
            x["base_requested"] = req
        x["base"] = s["base"]
        x["target"] = s["target"]
        x["track"] = self.open_track(gen, k, s["base"], target=s["target"])
        if k == "ablate":
            self.last_ablate = gen
        if k == "flip":
            self.flipped.append([self.blueprint_short(s["target"]), gen, x["track"]])
        return x

    # ---------------------------------------------------------------- children
    def deep_child(self, gen, exp):
        t = self.tracks.get(exp.get("track") or "") or {}
        if exp.get("kind") in ("drop", "ablate") or (exp.get("kind") == "flip" and exp.get("target")):
            return self.map_child(gen, exp)
        if exp.get("kind") == "track" and t.get("mismatch"):
            exp = {**exp, "change": f"{exp.get('change')}\n\n"
                                    + P.MISS_NOTE.format(missing=self.blueprint_lines(t["mismatch"], t.get("base_coord")))}
        return super().deep_child(gen, exp)

    def map_child(self, gen, exp):
        try:
            base = self.archive.programs[exp["base"]]
            bp = self.blueprint_lines(exp["target"], self.coord(base.id))
            note = {"drop": P.DROP_CODER_NOTE, "flip": P.FLIP_CODER_NOTE, "ablate": P.ABLATE_CODER_NOTE}[exp["kind"]]
            note = note.format(blueprint=bp, alt=self.alt_note())
            task = self.task_text("the base's")
            user = (f"{self.problem.DESCRIPTION}\n\n{self.program_block(base, 'The base program')}\n\n"
                    f"## The experiment to implement\nHypothesis: {exp.get('hypothesis')}\nChange: {exp.get('change')}\n"
                    f"Target: {exp.get('prediction')}\n\nImplement this experiment as a change to the base program. "
                    f"{task}\n\n{note}\n\n{P4.CODE_FORMAT}")
            code, summary = self.write_code("coder", self.coder_system(), user, gen)
            return self.child(gen, "deep", base, code, short(exp.get("hypothesis") or exp.get("change"), 300), exp,
                              summary)
        except Exception as exc:                                     # noqa: BLE001  (never lose the run)
            self.log(f"[{self.name}] gen {gen}: map child crashed: {exc}\n{traceback.format_exc()}")
            return self.add(Program(id="", gen=gen, role="deep", parent=exp.get("base"), intent="(crashed)", code="",
                                    plan=exp, error=f"internal error: {exc}")), None

    def exploring(self, plan):
        t = self.tracks.get((plan or {}).get("track") or "")
        return bool(t) and t.get("kind") in ("flip", "restart", "drop", "ablate") and t["id"] != self.main_track()

    # ---------------------------------------------------------------- annotation
    def ann_call(self, system, user, gen, temperature=0.2):
        self.ann_calls += 1
        return self.call("annotator", system, user, temperature=temperature, max_tokens=1500, effort="none", gen=gen)

    def annotate(self, gen, children, exps):
        """Coordinates for this generation's valid programs (calls in parallel, applied in order)."""
        if not self.cfg.annotate or not self.cb.active_axes():
            return []
        axes = self.cb.active_axes()
        rng = random.Random(self.cfg.seed * 31337 + gen)
        jobs = []
        firsts = {}
        for c in children:
            if c is None or not c.valid or c.role == "alt" or c.id in self.coords:
                continue
            t = self.tracks.get(self.track_of(c)) or {}
            par = self.archive.programs.get(c.parent)
            pc = self.coord(par.id) if par is not None else None
            readback = bool(t.get("target")) and (t.get("exps", 0) <= 1 or t.get("mismatch")) and c.role == "deep"
            diff = make_diff(par.code, c.code, limit=self.cfg.diff_lines) if par is not None else ""
            cut = "more diff lines)" in diff[-40:]
            if readback or pc is None or cut:
                jobs.append((c, "full", A.full_prompt(self.cb, axes, c, self.cfg.annotate_chars)))
            else:
                jobs.append((c, "diff", A.diff_prompt(self.cb, axes, par, pc, c, diff)))
            if readback:
                firsts[c.id] = t["id"]
            if rng.random() < self.cfg.double_rate:
                jobs.append((c, "second", A.full_prompt(self.cb, axes, c, self.cfg.annotate_chars)))
                if not any(j[0] is c and j[1] == "full" for j in jobs):
                    jobs.append((c, "full", A.full_prompt(self.cb, axes, c, self.cfg.annotate_chars)))
        if not jobs:
            return []
        with ThreadPoolExecutor(max_workers=6) as ex:
            texts = list(ex.map(lambda j: self.ann_call(A.SYSTEM, j[2], gen, 0.7 if j[1] == "second" else 0.2), jobs))
        done, landings = {}, []
        order = sorted(range(len(jobs)), key=lambda i: (int(jobs[i][0].id[1:]), jobs[i][1] != "full",
                                                       jobs[i][1] == "second"))
        seconds = {}
        for i in order:
            c, mode, _ = jobs[i]
            if mode == "second":
                seconds[c.id] = A.apply_full_reply(self.cb, texts[i], axes, gen)[0]
                continue
            if c.id in done:
                continue
            par = self.archive.programs.get(c.parent)
            if mode == "full":
                coord, info = A.apply_full_reply(self.cb, texts[i], axes, gen)
                pc = self.coord(par.id) if par is not None else None
                if pc and not info["readable"]:
                    coord = dict(pc)
            else:
                coord, info = A.apply_diff_reply(self.cb, texts[i], self.coord(par.id), gen)
            done[c.id] = self.set_coord(c.id, gen, coord, mode, extra={"readable": info["readable"]})
        for pid, second in seconds.items():
            if pid in done:
                row = {"id": pid, "gen": gen, "first": done[pid]["coord"], "second": second}
                self.ann_rows.append(row)
                self._append("annotations.jsonl", row)
        for c in children:                  # alternatives take their program's design
            if c is not None and c.valid and c.role == "alt" and c.parent in self.coords and c.id not in self.coords:
                r = self.coords[c.parent]
                self.set_coord(c.id, gen, r["coord"], "alt", effort=r.get("effort"))
        for pid, tid in firsts.items():     # read-back: did the coder build the target?
            t = self.tracks[tid]
            got = self.coord(pid) or {}
            target, base = t["target"], t.get("base_coord") or {}
            missing = {}
            for a, v in target.items():
                if is_new(v):
                    if not got.get(a) or got.get(a) == base.get(a):
                        missing[a] = v
                elif got.get(a) != self.cb.resolve_value(v):
                    missing[a] = v
            t["landing"] = {"gen": gen, "pid": pid, "matched": len(target) - len(missing), "of": len(target)}
            if missing:
                t["mismatch"] = missing
            else:
                t.pop("mismatch", None)
            landings.append(f"{tid} landed {len(target) - len(missing)}/{len(target)} target decisions"
                            + (f" (missing: {self.blueprint_short(missing)})" if missing else ""))
        if self.ann_rows:
            A.update_agreement(self.cb, self.ann_rows[-200:])
        return landings

    # ---------------------------------------------------------------- growing the map
    def merge_scan(self, gen, decisions):
        """The Cartographer's shared decisions, matched against the codebook (one call), added as axes and values;
        the known hills' tops all use the shared option, so they get it as their coordinate on that axis."""
        if not decisions:
            return 0
        items = "\n".join(f"{i}. {d['decision']} (all use: {d.get('everyone')}; alternatives: "
                          f"{'; '.join(d.get('alternatives') or []) or '-'})" for i, d in enumerate(decisions, 1))
        matches = {}
        if self.cb.active_axes():
            text = self.call("cartographer", P.MATCH_SYSTEM, P.MATCH_ASK.format(
                axes=self.cb.text(max_values=4), items=items), temperature=0.2, max_tokens=1200, effort="none", gen=gen)
            js = P4.extract_json(text) or {}
            for m in js.get("matches") or []:
                if isinstance(m, dict):
                    try:
                        matches[int(m.get("item"))] = m
                    except (TypeError, ValueError):
                        pass
        n_new = 0
        tops = [h["top"] for h in self.hills.values()]
        for i, d in enumerate(decisions, 1):
            m = matches.get(i) or {}
            aid = self.cb.resolve(str(m.get("axis") or "").strip())
            if aid not in self.cb.axes:
                n0 = len(self.cb.axes)
                aid = self.cb.add_axis(m.get("question") or d["decision"], gen, "scan")
                n_new += len(self.cb.axes) - n0
            v_all = self.cb.add_value(aid, d.get("everyone") or "the shared option", gen, "scan")
            for alt in d.get("alternatives") or []:
                self.cb.add_value(aid, alt, gen, "scan")
            for pid in tops:
                c = self.coord(pid)
                if c is not None and aid not in c:
                    self.set_coord(pid, gen, {**c, aid: v_all}, "scan", effort=self.effort(pid))
                elif c is None and pid in self.archive.programs:
                    self.set_coord(pid, gen, {aid: v_all}, "scan", effort=1.0)
        return n_new

    def discover(self, gen):
        """Programs at the same design (as the map knows it) whose scores differ more than the model explains: ask
        what design decision differs, and add it."""
        if self.model is None or gen % self.cfg.discover_every:
            return None
        axes = self.axes()
        res = dict(self.model.residuals())
        rows = list(getattr(self, "model_pids", []))
        groups = {}
        for i, pid in enumerate(rows):
            if abs(res.get(i, 0.0)) >= self.cfg.residual_z:
                c = {a: v for a, v in (self.coord(pid) or {}).items() if a in axes}
                groups.setdefault(tuple(sorted(c.items())), []).append(pid)
        for key, pids in groups.items():
            same = [pid for pid, r in self.coords.items() if pid in self.archive.programs and self.archive.programs[pid].valid
                    and tuple(sorted({a: v for a, v in (self.coord(pid) or {}).items() if a in axes}.items())) == key]
            if len(same) < 2:
                continue
            same.sort(key=lambda pid: self.archive.programs[pid].score)
            lo, hi = self.archive.programs[same[0]], self.archive.programs[same[-1]]
            if (lo.id, hi.id) in self.asked or hi.score - lo.score <= 3 * self.model.noise_sd():
                continue
            self.asked.add((lo.id, hi.id))
            text = self.call("cartographer", P.DISCOVER_SYSTEM, P.DISCOVER_ASK.format(
                design=self.cb.describe(dict(key), axes), a=hi.id, b=lo.id, sa=hi.score, sb=lo.score,
                code_a=P4.clip(hi.code, 7000), code_b=P4.clip(lo.code, 7000)), temperature=0.3, max_tokens=800,
                effort="none", gen=gen)
            js = P4.extract_json(text) or {}
            row = {"gen": gen, "pair": [lo.id, hi.id], "reply": js}
            dec = js.get("decision")
            if dec and str(dec).strip().lower() not in ("null", "none"):
                n0 = len(self.cb.axes)
                aid = self.cb.add_axis(str(dec), gen, "discovery")
                for p in (hi, lo):
                    val = js.get(p.id)
                    if val:
                        v = self.cb.add_value(aid, str(val), gen, "discovery")
                        self.set_coord(p.id, gen, {**(self.coord(p.id) or {}), aid: v}, "discovery",
                                       effort=self.effort(p.id))
                row["axis"] = aid
                row["new"] = len(self.cb.axes) > n0
                self.map_events.append(f"discovery: {aid} ({short(dec, 80)})" + ("" if row["new"] else " (an existing axis)"))
            self._append("discoveries.jsonl", row)
            return row
        return None

    # ---------------------------------------------------------------- the planner's view
    def design_view(self):
        axes = self.cb.active_axes()
        if not axes:
            return ""
        imp = self.model.importance() if self.model is not None else {}
        order = sorted(axes, key=lambda a: -imp.get(a, -1.0))[: self.cfg.map_axes]
        best_by, count = {}, Counter()
        for pid, r in self.coords.items():
            p = self.archive.programs.get(pid)
            if p is None or not p.valid or p.score is None:
                continue
            for a, v in self.cb.canonical(r["coord"]).items():
                count[v] += 1
                if v not in best_by or p.score > best_by[v][0]:
                    best_by[v] = (p.score, pid)
        rec = self.coord(self.archive.best().id) or {}
        rows = [P.MAP_HEADER.format(axes=len(axes), rows=len(self.coords))]
        for a in order:
            ag = self.cb.axes[a].get("agreement") or {}
            rel = "" if a in self.axes() else " [read unreliably: not used to steer]"
            share = f"; importance {100 * imp[a]:.0f}%" if a in imp else ""
            rows.append(f"- {a}: {self.cb.axes[a]['question'] or self.cb.name(a)}{share}{rel}")
            eff = self.model.effects(a) if (self.model is not None and a in self.model.axes) else {}
            vals = self.cb.values(a)
            vals = sorted(vals, key=lambda v: (-count[v], v))[: self.cfg.map_values]
            for v in vals:
                tag = " (the record's)" if rec.get(a) == v else ""
                if count[v]:
                    b = best_by.get(v)
                    e = eff.get(v)
                    es = f", effect {e[0]:+.6f} ± {e[1]:.6f}" if e else ""
                    rows.append(f"    {v} {short(self.cb.value_name(v), 70)}{tag}: {count[v]} programs, best "
                                f"{b[0]:.6f} ({b[1]}){es}")
                else:
                    rows.append(f"    {v} {short(self.cb.value_name(v), 70)}: untried")
        more = len(axes) - len(order)
        if more > 0:
            rows.append(f"({more} more decisions not shown)")
        if self.model is not None and self.model.pairs:
            rows.append("Decisions that interact (the best option of one depends on the other): "
                        + ", ".join(f"{a} x {b}" for a, b in self.model.pairs))
        return "\n".join(rows)

    def tracks_view(self):
        text = super().tracks_view()
        if not text:
            return text
        for t in self.tracks.values():
            r = t.get("race")
            if r and t["id"] in text:
                tag = {"running": f"racing, judged at {r['budget']} experiments", "paused": "paused by the race",
                       "waiting": "waiting its turn to race again", "finished": "finished the race"}.get(r["status"], "")
                text = text.replace(f"- {t['id']} [", f"- {t['id']} [{tag}; ", 1) if f"- {t['id']} [" in text else \
                    text.replace(f"- {t['id']}: ", f"- {t['id']} [{tag}]: ", 1)
        return text

    def brief(self, gen, slots):
        parts = [x for x in (self.design_view(), self.map_view(), self.tracks_view()) if x]
        parts.append("## This generation's experiments, slot by slot\n" + "\n".join(s["text"] for s in slots))
        return "\n\n".join(parts)

    def researcher_system(self, k):
        return P.RESEARCHER_SYSTEM.format(k=k, budget=self.cfg.budget)

    # ---------------------------------------------------------------- the generation
    def generation(self, gen):
        t0, calls0 = time.time(), self.llm.calls
        self.map_events, self.ann_calls = [], 0
        self.sync_tracks()
        prev_best = self.archive.best()
        lv, stall, typical = self.level(gen)
        early = self.warm_gen is None and gen <= self.cfg.early_gens
        n_explore = min(max(lv, 2 if early else 0), self.cfg.deep - 1)
        pre = []
        if not self.hills:
            self.update_hills(gen, pre)
        rc = self.coord(prev_best.id)
        missing = [a for a in self.axes() if rc is not None and a not in rc]
        if self.cb.active_axes() and (rc is None or (len(missing) >= max(2, len(self.axes()) // 4)
                                                     and gen - self.record_read.get(prev_best.id, -99) >= 5)):
            self.record_read[prev_best.id] = gen        # the record read again in full: decisions found since
            self.annotate_one(gen, prev_best)
        scanned = None
        if self.scan_due(gen, n_explore):
            self.describe_hills(gen, k=3)
            scanned = self.scan(gen)
            if scanned:
                new = self.merge_scan(gen, scanned)
                if new:
                    self.map_events.append(f"the Cartographer's scan added {new} decision(s) to the map")
        if len(self.cb.active_axes()) > self.cfg.max_axes:
            text = self.call("cartographer", P.MATCH_SYSTEM, P.CONSOLIDATE_ASK.format(
                axes=self.cb.text(max_values=3), k=self.cfg.max_axes), temperature=0.2, max_tokens=2500, effort="none",
                gen=gen)
            merged = consolidate(self.cb, P4.extract_json(text) or {}, gen)
            if merged:
                self.map_events.append(f"{len(merged)} duplicate decision(s) merged")
        self.fit_model()
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
        landings = self.annotate(gen, children, exps)
        events = pre + self.update_tracks(gen, children, exps, prev_best)
        n_hills = len(self.hills)
        self.update_hills(gen, events)
        self.describe_hills(gen, k=2)
        self.fit_model()
        disc = self.discover(gen)
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
        imp = self.model.importance() if self.model is not None else {}
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
               "map": {"axes": len(self.cb.active_axes()), "reliable": len(self.axes()), "coords": len(self.coords),
                       "model_rows": self.model.n if self.model is not None else 0,
                       "noise": round(self.model.noise_sd(), 9) if self.model is not None else None,
                       "importance": {str(k): round(v, 3) for k, v in list(imp.items())[:6]},
                       "annotations": self.ann_calls, "landings": landings, "events": self.map_events,
                       "discovery": (disc or {}).get("axis"),
                       "racing": sorted(t["id"] for t in self.tracks.values() if t.get("race") and self.race.live(t))},
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
        self._append("codebook.jsonl", {"gen": gen, "codebook": self.cb.to_json()})
        self.checkpoint(gen)
        kinds = Counter(s["kind"] for s in slots)
        self.log(f"[{self.name}] gen {gen}: best {best.score:.6f} ({best.id}, {best.role}, track {self.track_of(best)}, "
                 f"hill {main_hill}){' RECORD' if record else ''}; stall {stall} (typical {typical:g}), level {lv}; "
                 f"slots " + ", ".join(f"{n} {k}" for k, n in kinds.items())
                 + f"; deep {row['deep_gains']}/{len(dc)} gained, wide {row['wide_gains']}/{len(wc)} gained; "
                 f"{len(self.hills)} hills; map {row['map']['axes']} decisions ({row['map']['reliable']} steering), "
                 f"{len(self.coords)} programs placed"
                 + (f"; {'; '.join(landings)}" if landings else "") + (f"; {'; '.join(self.map_events)}" if self.map_events else "")
                 + (f"; {'; '.join(events)}" if events else "") + f"; {row['seconds']:.0f} s")
        return row

    def annotate_one(self, gen, p):
        """A full reading of one program: the record, when it has no coordinate yet, or again when decisions found
        since are missing from it (the earlier reading is kept where the new one is silent, and so is its effort)."""
        text = self.ann_call(A.SYSTEM, A.full_prompt(self.cb, self.cb.active_axes(), p, self.cfg.annotate_chars), gen)
        coord, info = A.apply_full_reply(self.cb, text, self.cb.active_axes(), gen)
        old = self.coords.get(p.id)
        if old is not None:
            return self.set_coord(p.id, gen, {**(old.get("coord") or {}), **coord}, "reread",
                                  effort=old.get("effort", 1.0))
        return self.set_coord(p.id, gen, coord, "full", effort=1.0)

    def finish(self, seconds=None, stopped_at=None):
        summary = super().finish(seconds, stopped_at)
        summary["design_map"] = {"axes": len(self.cb.active_axes()), "reliable": len(self.axes()),
                                 "coords": len(self.coords),
                                 "model": self.model.summary() if self.model is not None else None}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
        (self.dir / "codebook.json").write_text(json.dumps(self.cb.to_json(), indent=1))
        return summary


# ---------------------------------------------------------------------------------------------- the fake model
def fake_answer(role, system, user):
    if role == "annotator":
        return A.fake_reply("", user)
    if role == "cartographer" and "design decisions named elsewhere" in user:
        n = len(re.findall(r"^\d+\. ", user.split("Below are design decisions")[-1], re.M))
        return json.dumps({"matches": [{"item": i, "axis": "new", "question": f"fake decision {i}"} for i in range(1, n + 1)]})
    if role == "cartographer" and "What design decision differs" in user:
        ids = re.findall(r"^## (p\d{4})$", user, re.M)
        return json.dumps({"decision": "a fake hidden decision", **{i: f"option of {i}" for i in ids}})
    return fake_answer8(role, system, user)


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
