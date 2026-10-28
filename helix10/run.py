"""Helix v10: v9 plus the field's knowledge, and the fixes v9's job called for (docs/V10_DESIGN.md).

What v10 adds to v9 (everything of v9 stays):
- **The field's decisions on the design map** (helix10/sota.py, AXES): added by the warm start (helix10/warm.py), on a
  decision the map already has when it has one, else as a new decision. Exploration is biased towards them: every
  borrowed option is tried once as a flip of the record before the map's own choices take over (coverage), then
  about half of the new explorations target a borrowed option. The design table always shows them, marked.
- **The field's findings in the Atlas** (sota.FINDINGS, kind "field", with sources): shown to the planner as their
  own block, so it knows how far each known approach has gone.
- **The warm mode** (helix10/warm.py): the field's constructions (sota.IMPORTS) as programs with their own tracks and
  hills, and the field's methods (helix10/programs/) as programs run on the record's construction.
- **v9's failures, fixed**: an exploration of any kind that lands on a known hill below its top no longer races (v9
  stopped only drops and restarts, so copies of the record held the race); the race judges first at 3 experiments,
  not 2 (a new design climbs before it is judged); at most one of the wide loop's bases a generation sits on the
  record's hill (v9: about half); at least two of the three planned experiments explore; the map's upkeep runs every
  third generation (v9: every one, a fifth of the tokens).
- **Constructions up to 2,000,000 steps** (the arena's cap): a construction handed back unchanged is kept as a
  reference to its start, and large constructions nothing needs any more (not a hill's top, a track's best or root,
  the top programs, or a recent base) are removed after a few generations, so a run fits the VM's disk.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from helix4.archive import Archive, short
from helix4.llm import FakeLLM
from helix7.memory import Atlas7
from helix9 import prompts as P
from helix9.run import Config as Config9, Run as Run9, fake_answer as fake9

BIG_REF = ".ref"


@dataclass
class Config(Config9):
    condition: str = "v10"
    mode: str = "axes"                # "axes": the field's decisions and findings; "warm": also its constructions
    max_n: int = 2_000_000
    budget: float = 150.0
    mem_mb: int = 2000
    min_explore: int = 2              # planned experiments that explore, every generation (v9: 0 while climbing)
    borrow_share: float = 0.5         # after coverage, about this share of new explorations target a borrowed option
    race_rungs: tuple = (3, 6, 12, 24, 48)
    record_hill_wide: int = 1         # at most this many of the wide loop's bases on the record's hill a generation
    upkeep_every: int = 3
    max_axes: int = 30
    map_axes: int = 12
    big_n: int = 300_000              # constructions larger than this: kept by reference or removed when unneeded
    keep_top: int = 12
    gc_age: int = 2
    tidy_values: int = 12             # a decision is tidied above this many options (v9: 6; the field adds some)


class Archive10(Archive):
    """Archive whose large constructions handed back unchanged are kept as a reference to their start."""
    big_n = 300_000

    def add(self, p, construction=None):
        if construction is not None and p.valid and p.parent and np.asarray(construction).size > self.big_n:
            start = self.construction(p.parent)
            a = np.asarray(construction, dtype=float)
            if start is not None and start.shape == a.shape and a.max() > 0 and start.max() > 0 \
                    and np.allclose(a / a.max(), start / start.max(), rtol=0.0, atol=1e-14):
                self._add(p)
                with self.path.open("a") as f:
                    f.write(json.dumps(asdict(p)) + "\n")
                of = self.resolve(p.parent)
                (self.dir / "constructions" / f"{p.id}{BIG_REF}").write_text(of)
                with (self.dir / "refs.jsonl").open("a") as f:          # published, so a continuation keeps them
                    f.write(json.dumps({"id": p.id, "of": of, "gen": p.gen}) + "\n")
                return
        super().add(p, construction)

    def resolve(self, pid, depth=0):
        """The program whose .npy holds pid's construction."""
        ref = self.dir / "constructions" / f"{pid}{BIG_REF}"
        if ref.exists() and depth < 50:
            return self.resolve(ref.read_text().strip(), depth + 1)
        return pid

    def construction(self, pid):
        return super().construction(self.resolve(pid))

    def held(self, pid):
        return (self.dir / "constructions" / f"{self.resolve(pid)}.npy").exists()

    def truncate(self, gen_done):
        for p in [p for p in self.programs.values() if p.gen > gen_done]:
            (self.dir / "constructions" / f"{p.id}{BIG_REF}").unlink(missing_ok=True)
        rf = self.dir / "refs.jsonl"
        if rf.exists():
            rows = [json.loads(x) for x in rf.read_text().splitlines() if x.strip()]
            rf.write_text("".join(json.dumps(r) + "\n" for r in rows if r.get("gen", 0) <= gen_done))
        return super().truncate(gen_done)


class AtlasField(Atlas7):
    """The Atlas, plus the field's findings (kind "field"): what the literature and the arena measured, with sources."""

    def status(self, f):
        if f.get("kind") == "field":
            return "from the field"
        return super().status(f)

    def field_ids(self):
        return [i for i in sorted(self.findings, key=lambda i: int(i[1:])) if self.findings[i].get("kind") == "field"]

    def finding_line(self, fid, n=170):
        f = self.findings[fid]
        if f.get("kind") == "field":
            return f"{fid} [from the field] {short(f['claim'], n)}"
        return super().finding_line(fid, n)

    def findings_view(self, limit=None):
        text, shown = super().findings_view(limit)
        ids = self.field_ids()
        if not ids:
            return text, shown
        field = "\n".join(f"{i}: {self.findings[i]['claim']} (source: {short(self.findings[i].get('source'), 160)})"
                          for i in ids)
        return (f"What the field knows (the literature and EinsteinArena, measured by others; not tested in this run "
                f"unless a program here says so):\n{field}\n\nThis run's findings:\n{text}"), shown + len(ids)

    def open_finding(self, fid):
        f = self.findings.get(fid)
        if f is not None and f.get("kind") == "field":
            return f"## {fid} (from the field)\n{f['claim']}\nSource: {f.get('source')}"
        return super().open_finding(fid)


class Run(Run9):
    CONFIG = Config
    VERSION = "v10"

    def __init__(self, out, cfg: Config | None = None, llm=None, gens=None, log=print, problem=None):
        super().__init__(out, cfg, llm=llm, gens=gens, log=log, problem=problem)
        self.archive.__class__ = Archive10
        self.archive.big_n = self.cfg.big_n
        self.memory = AtlasField(self)
        bf = self.dir / "borrowed.json"
        self.borrowed = json.loads(bf.read_text()) if bf.exists() else {"axes": {}, "values": {}}
        self.rng10 = random.Random(self.cfg.seed * 7727 + max(self.gen_done, 0))

    # ---------------------------------------------------------------- constructions (2M steps)
    def has_construction(self, p):
        if p is None:
            return False
        if p.role == "seed" or self.archive.held(p.id):
            return True
        return super().has_construction(p)

    def gc_constructions(self, gen):
        """Removes large constructions nothing needs any more (logged in gc.jsonl)."""
        cdir = self.dir / "constructions"
        keep = {p.id for p in self.archive.ranked()[: self.cfg.keep_top]}
        keep |= {h.get("top") for h in self.hills.values()}
        for t in self.tracks.values():
            keep |= {t.get("best_id"), t.get("root"), t.get("placed")}
        keep |= {p.parent for p in self.archive.programs.values() if p.gen >= gen - 1 and p.parent}
        refs = {f.read_text().strip() for f in cdir.glob(f"*{BIG_REF}")}
        removed = []
        for f in cdir.glob("*.npy"):
            pid = f.stem
            p = self.archive.programs.get(pid)
            if p is None or pid in keep or pid in refs or p.gen > gen - self.cfg.gc_age:
                continue
            if (p.n or 0) <= self.cfg.big_n or p.role == "import":
                continue
            f.unlink(missing_ok=True)
            removed.append(pid)
        if removed:
            self._append("gc.jsonl", {"gen": gen, "removed": removed})
        return removed

    # ---------------------------------------------------------------- the borrowed axes
    def borrowed_axes(self):
        out = []
        for a in self.borrowed.get("axes", {}):
            r = self.cb.resolve(a)
            if r in self.cb.axes and r not in out and r in self.cb.active_axes():
                out.append(r)
        return out

    def borrowed_values(self):
        """[(axis, value, note)] for every borrowed option still on the map."""
        out, seen = [], set()
        for v, info in self.borrowed.get("values", {}).items():
            r = self.cb.resolve_value(v)
            a = self.cb.resolve(r.rsplit(".", 1)[0]) if "." in r else None
            if a is None or a not in self.cb.active_axes() or r not in self.cb.values(a) or r in seen:
                continue
            seen.add(r)
            out.append((a, r, info.get("note", "")))
        return out

    def borrow_tries(self):
        n = Counter()
        since = self.warm_gen or 0
        for t in self.tracks.values():
            if t.get("target") and t["opened"] > since:
                for a, v in t["target"].items():
                    n[self.cb.resolve_value(v)] += 1
        return n

    def pick_borrow(self, best):
        """A flip of the record to a borrowed option: the least tried first (coverage), axes in turn."""
        vals = self.borrowed_values()
        if not vals:
            return None
        base = self.coord(best.id) or {}
        tries = self.borrow_tries()
        by_axis = Counter()
        for a, v, _ in vals:
            by_axis[a] += tries[v]
        cands = [(tries[v], by_axis[a], i, a, v) for i, (a, v, _) in enumerate(vals) if base.get(a) != v]
        if not cands:
            return None
        low = min(c[0] for c in cands)
        if low > 0 and self.rng10.random() > self.cfg.borrow_share:
            return None                                  # coverage done: the map's own choices take this one
        cands = [c for c in cands if c[0] == low]
        cands.sort(key=lambda c: (c[1], self.rng10.random()))
        _, _, _, a, v = cands[0]
        coord = {**base, a: v}
        return coord, {a: v}, None

    def make_slots(self, gen, n_explore):
        if self.map_ready():
            n_explore = max(n_explore, min(self.cfg.min_explore, self.cfg.deep - 1))
        slots = super().make_slots(gen, n_explore)
        if not self.map_ready() or not self.borrowed.get("values"):
            return slots
        best = self.archive.best()
        pick = self.pick_borrow(best)
        if pick is None:
            return slots
        coord, change, rating = pick
        new = [i for i, s in enumerate(slots) if s["kind"] not in ("main", "track")]
        racing = [i for i, s in enumerate(slots) if s["kind"] == "track"]
        i = new[0] if new else (racing[-1] if racing and gen % 2 == 0 else None)
        if i is None:
            return slots
        old = slots[i]
        if old.get("kind") == "track":
            t = self.tracks.get(old.get("track"))
            if t is not None:
                t["served"] = t.get("served", gen) - 1          # it keeps its turn
        slots[i] = {"kind": "flip", "map": True, "target": change, "target_coord": coord, "rating": rating,
                    "base": best.id, "borrowed": True}
        slots = self.fill_slot_texts(slots, best)
        a, v = next(iter(change.items()))
        note = (self.borrowed.get("values", {}).get(v) or {}).get("note") or next(
            (n for aa, vv, n in self.borrowed_values() if vv == v), "")
        slots[i]["text"] += (f"\nThis option comes from the field (the literature or EinsteinArena), not from this run: "
                             f"{short(note, 300)}. Build it properly (it is a design to test, not a detail): the race "
                             f"gives it {self.cfg.race_rungs[0]} experiments before judging it.")
        return slots

    # ---------------------------------------------------------------- v9's failures, fixed
    def is_copy(self, t):
        """A racing exploration that, after its first rung, sits on a known hill below that hill's top: a copy of a
        known design (v9 stopped only drops and restarts this way, so copies of the record held the race)."""
        return (bool(t.get("race")) and t["id"] != self.main_track() and t.get("hill_status") == "on"
                and t.get("exps", 0) >= self.cfg.race_rungs[0])

    def live(self, t):
        if self.is_copy(t):
            return False
        return super().live(t)

    def race_pool(self, gen):
        """v9's cap on racing tracks, with two changes: a copy stops racing (is_copy), and a track that hasn't had its
        first rung's experiments yet is never sent to the queue (it climbs before it is judged)."""
        out = []
        for t in self.tracks.values():
            r = t.get("race") or {}
            if r.get("status") == "running" and self.is_copy(t):
                r["status"] = "paused"
                r.setdefault("decisions", []).append({"gen": gen, "rung": r.get("budget"), "best": t.get("best"),
                                                      "go": False, "why": "a copy: on a known hill below its top"})
                out.append(f"{t['id']} stops racing: after {t.get('exps', 0)} experiments it sits on {t.get('hill')} "
                           f"below that hill's top (a copy of a known design)")
        young = [t for t in self.tracks.values() if (t.get("race") or {}).get("status") == "running"
                 and t.get("exps", 0) < self.cfg.race_rungs[0]]
        for t in young:
            t["race"]["status"] = "young"
        try:
            out += super().race_pool(gen)
        finally:
            for t in young:
                t["race"]["status"] = "running"
        return out

    def on_record_hill(self, p):
        main = self.tracks.get(self.main_track()) or {}
        tid = self.track_of(p)
        if tid == main.get("id"):
            return True
        t = self.tracks.get(tid) or {}
        return bool(main.get("hill")) and t.get("hill") == main.get("hill")

    def wide_parents(self, rng, pool, level):
        parents = super().wide_parents(rng, pool, level)
        if not parents:
            return parents
        on = [i for i, p in enumerate(parents) if self.on_record_hill(p)]
        extra = on[self.cfg.record_hill_wide:]
        if extra:
            side = [q for q in pool if not self.on_record_hill(q) and self.has_construction(q)]
            for i in extra:
                if side:
                    parents[i] = self.archive.sample_parent(rng, side, alpha=self.cfg.wide_alpha_stalled)
        return parents

    def upkeep(self, gen):
        """v9's upkeep, every `upkeep_every` generations; a borrowed option is never merged away into one of the
        run's own (when options are grouped, it stands for its group), so the field's choices stay targets."""
        if self.cfg.upkeep_every > 1 and gen % self.cfg.upkeep_every != 0:
            return
        from helix9 import upkeep as U
        orig = U.uses_of
        keep = {v for _, v, _ in self.borrowed_values()}

        def uses_of(cb, coords):
            n = orig(cb, coords)
            for v in keep:
                n[v] += 10 ** 6
            return n
        U.uses_of = uses_of
        try:
            return super().upkeep(gen)
        finally:
            U.uses_of = orig

    # ---------------------------------------------------------------- the planner's view
    def design_view(self):
        """v9's design table, plus every decision and option from the field (marked), whatever its use so far."""
        axes = self.cb.active_axes()
        if not axes:
            return ""
        imp = self.model.importance() if self.model is not None else {}
        battx = self.borrowed_axes()
        bvals = {}
        for a, v, _ in self.borrowed_values():
            bvals.setdefault(a, []).append(v)
        order = sorted(axes, key=lambda a: -imp.get(a, -1.0))[: self.cfg.map_axes]
        order += [a for a in battx if a not in order]
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
        rows = [P.MAP_HEADER.format(axes=len(axes), rows=len(self.coords)),
                "Decisions and options marked [from the field] come from the literature and EinsteinArena (others "
                "measured them; see the Atlas's field findings), not from this run's programs."]
        for a in order:
            rel = "" if a in self.axes() else " [read unreliably: not used to steer]"
            share = f"; importance {100 * imp[a]:.0f}%" if a in imp else ""
            tag = " [a decision from the field]" if a in battx and not self.borrowed["axes"].get(a, {}).get("attached") \
                else ""
            rows.append(f"- {a}: {self.cb.axes[a]['question'] or self.cb.name(a)}{share}{rel}{tag}")
            eff = self.model.effects(a) if (self.model is not None and a in self.model.axes) else {}
            vals = sorted(self.cb.values(a), key=lambda v: (-count[v], v))[: self.cfg.map_values]
            vals += [v for v in bvals.get(a, []) if v not in vals]
            for v in vals:
                mark = " (the record's)" if rec.get(a) == v else ""
                field = " [from the field]" if v in bvals.get(a, []) else ""
                if count[v]:
                    b = best_by.get(v)
                    e = eff.get(v)
                    es = f", effect {e[0]:+.6f} ± {e[1]:.6f}" if e else ""
                    rows.append(f"    {v} {short(self.cb.value_name(v), 90)}{mark}{field}: {count[v]} programs, best "
                                f"{b[0]:.6f} ({b[1]}){es}")
                else:
                    rows.append(f"    {v} {short(self.cb.value_name(v), 90)}{field}: untried")
        more = len(axes) - len(order)
        if more > 0:
            rows.append(f"({more} more decisions not shown)")
        if self.model is not None and self.model.pairs:
            rows.append("Decisions that interact (the best option of one depends on the other): "
                        + ", ".join(f"{a} x {b}" for a, b in self.model.pairs))
        return "\n".join(rows)

    # ---------------------------------------------------------------- the generation
    def generation(self, gen):
        best = self.archive.best()
        if self.cfg.annotate and self.borrowed.get("axes") and best is not None and self.cb.active_axes():
            rc = self.coord(best.id)
            miss = [a for a in self.borrowed_axes() if rc is None or a not in rc]
            if miss and gen - self.record_read.get(best.id, -99) >= 5:
                self.record_read[best.id] = gen               # the record read on the field's decisions
                self.annotate_one(gen, best)
        pending = [t for t in self.tracks.values() if t.get("kind") == "import" and not t.get("placed")]
        if pending:
            ev = []
            for t in pending:
                if t.get("best_id"):
                    self.place(gen, t, t["best_id"], ev, seeding=True)
            for e in ev:
                self.log(f"[{self.name}] gen {gen}: {e}")
            self.log(f"[{self.name}] gen {gen}: the field's constructions placed on the map of hills "
                     f"({len(pending)} tracks)")
        out = super().generation(gen)
        removed = self.gc_constructions(gen)
        if removed:
            self.log(f"[{self.name}] gen {gen}: {len(removed)} large construction(s) nothing needs any more removed")
        return out


def fake_answer(role, system, user):
    return fake9(role, system, user)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--fake", action="store_true")
    a = ap.parse_args(argv)
    cfg = Config(seed=a.seed, gens=a.gens or 20, budget=a.budget)
    llm = FakeLLM(fake_answer) if a.fake else None
    run = Run(a.out, cfg, llm=llm, gens=a.gens, log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    run.go()


if __name__ == "__main__":
    sys.exit(main())
