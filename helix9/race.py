"""The fair race between new hills (docs/V9_DESIGN.md; docs/SEARCH_SPACE_MODEL.md sections 2.2, 4.5).

A new design's height is not visible from its foot: across 15 from-scratch runs, a run's best after 20 programs had
no rank correlation with its final best, and v8 paused new hills after a median of 3 experiments. So exploration
tracks race in rungs of effort (successive halving), and a track is compared with the tracks that started the same
way **at the same effort**, never with a record that has a thousand experiments behind it:

- an exploration track's effort is the number of experiments spent on it;
- at each rung (2, 4, 8, 16, 32 experiments) its best so far is compared with the cohort: the other tracks of its
  group (new designs: drops, restarts, bold experiments; local changes: flips, ablations) at the same rung;
- the rule (`rule`):
  - "level" (successive halving): it goes on to the next rung if it is in the top part of the cohort (at or above
    the `q` quantile), or if it is still rising (it gained in the second half of the rung) and not in the bottom part
    (at or above the `q_rising` quantile);
  - "rising" (a rising bandit): it goes on while it is still rising, whatever its level, or if it is in the top part
    of the cohort; a track that has stopped rising has shown its height for now;
  with fewer than `min_cohort` others at that rung it goes on (the benefit of the doubt);
- brackets (Hyperband's hedge against unknown curve shapes): each new track gets a first rung in turn from
  `brackets` (indices into the rungs), so some tracks are first judged only after 8 or 16 experiments;
- otherwise it pauses (never closed: a later gain on it, from the wide loop, wakes it, as in v7);
- past the last rung the race is over: the track is a hill in its own right and follows v7's rules.

A continuation judges the earlier run's explorations the same way, as if they had raced (`retro_judge`): those still
rising when the earlier run paused them qualify. Only a few race again at once; the rest **wait** in a queue, the
strongest at equal effort first, and the run takes one from it whenever it opens a new exploration (in turn with new
drops, flips and backtracks), so every one gets its chance without the backlog crowding out new directions.

A track that beats the record becomes the main track whatever its rung, as before.
"""
from __future__ import annotations

import math

RUNGS = (2, 4, 8, 16, 32)
GROUPS = {"drop": "new", "restart": "new", "bold": "new", "flip": "local", "ablate": "local"}


def group_of(kind):
    return GROUPS.get(kind)


def best_at(curve, effort):
    """The track's best after `effort` experiments. curve: [[experiments so far, best so far (or None)], ...]."""
    out = None
    for e, b in curve or []:
        if e > effort:
            break
        if b is not None:
            out = b if out is None else max(out, b)
    return out


def rose_late(curve, rung, prev_rung, floor=None):
    """True if the track's best rose by more than the noise floor during the second half of the rung (it is still
    climbing; a best that creeps up by noise alone is not)."""
    mid = prev_rung + max(1, (rung - prev_rung) // 2)
    before, after = best_at(curve, mid - 1), best_at(curve, rung)
    if after is None:
        return False
    return before is None or after > before + (floor(before) if floor else 0.0)


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class Race:
    def __init__(self, rungs=RUNGS, q=0.5, q_rising=0.25, min_cohort=3, floor=None, rule="level", brackets=(0,)):
        self.rungs, self.q, self.q_rising, self.min_cohort = tuple(rungs), q, q_rising, min_cohort
        self.floor = floor or (lambda ref: 0.0)
        self.rule, self.brackets = rule, tuple(brackets) or (0,)
        self.started = 0

    def start(self, t, bracket=None):
        """Enters t in the race. Its first rung comes from the brackets in turn (or `bracket`)."""
        k = self.brackets[self.started % len(self.brackets)] if bracket is None else bracket
        k = min(max(int(k), 0), len(self.rungs) - 1)
        self.started += 1
        t["race"] = {"rung": k, "budget": self.rungs[k], "status": "running", "decisions": [], "bracket": k}
        t.setdefault("curve", [])

    def cohort(self, tracks, t, rung):
        """Bests at `rung` of the other tracks of t's group that have reached it."""
        g = group_of(t.get("kind"))
        out = []
        for u in tracks:
            if u is t or u.get("id") == t.get("id") or group_of(u.get("kind")) != g:
                continue
            if (u.get("exps") or 0) >= rung:
                b = best_at(u.get("curve"), rung)
                if b is not None:
                    out.append(b)
        return out

    def decide(self, t, tracks, gen=None, effort=None):
        """Called after a generation. Returns None, or an event string when the track reaches a rung. `effort`: judge
        as if the track had spent this many experiments (replaying an earlier run's curve); default: its own."""
        r = t.get("race")
        if not r or r["status"] not in ("running",):
            return None
        e = (t.get("exps") or 0) if effort is None else min(effort, t.get("exps") or 0)
        if e < r["budget"]:
            return None
        k = r["rung"]
        rung = r["budget"]                          # the effort it is judged at (a woken track's may be off-grid)
        prev = r.get("prev", self.rungs[k - 1] if k > 0 else 0)
        mine = best_at(t.get("curve"), rung)
        others = self.cohort(tracks, t, rung)
        top_q, low_q = quantile(others, self.q), quantile(others, self.q_rising)
        rising = rose_late(t.get("curve"), rung, prev, self.floor)
        if mine is None:
            go, why = False, "no valid program that changed its start"
        elif self.rule == "rising" and rising:
            go, why = True, f"still rising (best {mine:.6f} at {rung} experiments)"
        elif self.rule == "rising" and len(others) >= self.min_cohort and mine >= top_q - self.floor(top_q):
            go, why = True, (f"no longer rising, but best {mine:.6f} at {rung} experiments is at or above the cohort's "
                             f"{self.q:.0%} quantile ({top_q:.6f})")
        elif self.rule == "rising" and len(others) < self.min_cohort:
            go, why = False, f"stopped rising at {rung} experiments (best {mine:.6f})"
        elif self.rule == "rising":
            go, why = False, f"stopped rising at {rung} experiments (best {mine:.6f}, below the cohort's {self.q:.0%} quantile)"
        elif len(others) < self.min_cohort:
            go, why = True, f"only {len(others)} others reached {rung} experiments: benefit of the doubt"
        elif mine >= top_q - self.floor(top_q):
            go, why = True, f"best {mine:.6f} at {rung} experiments, at or above the cohort's {self.q:.0%} quantile ({top_q:.6f})"
        elif rising and mine >= low_q - self.floor(low_q):
            go, why = True, (f"still rising, best {mine:.6f} at {rung} experiments, above the cohort's "
                             f"{self.q_rising:.0%} quantile ({low_q:.6f})")
        else:
            go, why = False, (f"best {mine if mine is not None else float('nan'):.6f} at {rung} experiments, below the "
                              f"cohort's {self.q:.0%} quantile ({top_q:.6f})" + ("" if rising else ", and not rising"))
        pct = None if mine is None or not others else sum(1 for x in others if x <= mine) / len(others)
        r["decisions"].append({"gen": gen, "rung": rung, "best": mine, "cohort": len(others),
                               "percentile": None if pct is None else round(pct, 3), "go": go, "why": why})
        r["prev"] = rung
        if go and k + 1 < len(self.rungs):
            r["rung"], r["budget"] = k + 1, max(self.rungs[k + 1], e + 1)
            return f"{t['id']} goes on to the next rung ({r['budget']} experiments): {why}"
        if go:
            r["status"] = "finished"
            return f"{t['id']} finished the race ({rung} experiments): {why}; it is now an ordinary side track"
        r["status"] = "paused"
        return f"{t['id']} paused by the race at {rung} experiments: {why}"

    def wake(self, t):
        """A gain on a paused or waiting race track (from the wide loop) gives it one more rung."""
        r = t.get("race")
        if r and r["status"] in ("paused", "waiting"):
            r["status"] = "running"
            k = min(r["rung"] + 1, len(self.rungs) - 1)
            r["rung"], r["budget"] = k, max(self.rungs[k], (t.get("exps") or 0) + 2)
            return True
        return False

    def live(self, t):
        r = t.get("race")
        return bool(r) and r["status"] == "running"

    def standing(self, t, tracks):
        """The track's percentile in its cohort at its current effort (for ordering live tracks)."""
        e = t.get("exps") or 0
        mine = best_at(t.get("curve"), e)
        if mine is None:
            return 0.5
        others = []
        for u in tracks:
            if u is t or group_of(u.get("kind")) != group_of(t.get("kind")):
                continue
            if (u.get("exps") or 0) >= e and e > 0:
                b = best_at(u.get("curve"), e)
                if b is not None:
                    others.append(b)
        return 0.5 if not others else sum(1 for x in others if x <= mine) / len(others)


def retro_judge(race, tracks, gen, keep, kinds=("restart", "bold", "flip"), main=None):
    """Judges an earlier run's explorations as the race would have (each at the rungs its curve reached). Those that
    qualify to go on: the `keep` strongest at equal effort race again; the rest wait (status "waiting"), to be taken
    one at a time (`take_waiting`). Returns {status: count}."""
    for t in sorted(tracks, key=lambda t: t.get("opened") or 0):
        if t.get("kind") not in kinds or t.get("id") == main or t.get("race"):
            continue
        race.start(t, bracket=0)
        t["served"] = t.get("opened")
        for _ in range(len(race.rungs)):
            if t["race"]["status"] != "running" or (t.get("exps") or 0) < t["race"]["budget"]:
                break
            race.decide(t, tracks, gen, effort=t["race"]["budget"])
    running = [t for t in tracks if (t.get("race") or {}).get("status") == "running" and t.get("id") != main]
    if len(running) > keep:
        rank = {t["id"]: race.standing(t, tracks) for t in running}
        running.sort(key=lambda t: (-rank[t["id"]], -(t.get("best") if t.get("best") is not None else -1e300)))
        for i, t in enumerate(running[keep:]):
            t["race"]["status"] = "waiting"
            t["race"]["queue"] = round(1.0 - rank[t["id"]], 4)     # the strongest at equal effort first
            t["race"]["decisions"].append({
                "gen": gen, "rung": t["race"]["budget"], "best": t.get("best"), "go": True, "cap": True,
                "why": f"qualifies to race again; {len(running)} earlier explorations do, so it waits its turn "
                       f"(place {i + 1} of {len(running) - keep}, the strongest at equal effort first)"})
    status = {}
    for t in tracks:
        if t.get("race"):
            status[t["race"]["status"]] = status.get(t["race"]["status"], 0) + 1
    return status


def take_waiting(tracks, gen=None):
    """The next waiting track (the strongest first), made to race again; None if none waits."""
    waiting = [t for t in tracks if (t.get("race") or {}).get("status") == "waiting"]
    if not waiting:
        return None
    t = min(waiting, key=lambda t: (t["race"].get("queue", 0), t.get("opened") or 0))
    r = t["race"]
    r["status"] = "running"
    r["budget"] = max(r["budget"], (t.get("exps") or 0) + 1)
    r["decisions"].append({"gen": gen, "rung": r["budget"], "best": t.get("best"), "go": True,
                           "why": "its turn came: racing again"})
    return t


def record_curve(t, gen=None):
    """Appends the track's (experiments, best) point after a generation, if it changed."""
    c = t.setdefault("curve", [])
    pt = [t.get("exps") or 0, t.get("best")]
    if not c or c[-1] != pt:
        if c and c[-1][0] == pt[0]:
            c[-1] = pt
        else:
            c.append(pt)
    return c
