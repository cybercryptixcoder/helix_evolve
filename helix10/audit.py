"""The invariant audit (docs/IDEAS.md, section 3.4; Shreyas, October 28): "What does every programme do in the same
way?", asked over and over until nothing uniformly common is left.

A design decision every program makes the same way is invisible to the rest of the map: nothing varies, so nothing
says whether another choice would be better (the residual test can't see it either). The audit names such decisions so
they can be varied. One round:

1. **Propose.** A describer reads a sample of the run's most different strong programs (the tops of the best hills
   and the record) and lists what they all do the same way, at the level of design concepts, sorting each answer:
   (1) a constraint of the problem (not an axis), (2) a detail below the level of design (Python, arrays, floating
   point), or (3/4) a real design decision that could be made otherwise, with 2-3 concrete alternatives. Decisions
   already on the map are shown so they aren't repeated.
2. **Verify.** A second reading, on a different sample (the best programs of other tracks, recent programs), sorts
   each proposed decision again, independently, and checks it program by program. It counts only if that reading also
   calls it a design decision and at least `min_share` of the programs do the same thing: the describer can't invent
   an invariant, and a constraint of the problem or a computing detail misread as a decision doesn't survive (found
   live: a first reading called the scorer's formula and the timing code "decisions"), and one the map already has in
   other words is dropped too. Both readings get the full problem statement, so they can tell what the problem fixes.
3. **Split.** Each confirmed invariant becomes a decision on the map: the shared choice as one option, the alternatives
   as the others, queued as targets exactly like the field's options (helix10/run.py: every one is built as a flip of
   the record, then raced). Building the alternatives is what tells "varyable but irrelevant" (the race stops them; the
   decision stays on the map as tested) from a real frozen axis (one opens a hill).
4. **Stop.** A round that confirms nothing new counts as empty. After `stop_after` empty rounds in a row the audit
   rests until the record moves; then it asks again, since new programs bring new shared assumptions.

Its ceiling is the describer: it names only what it has words for. The verification on a second sample and the
"already on the map" list are the guards; the honest claim is "nothing more these readings can articulate".
"""
from __future__ import annotations

import json
import re

from helix4.archive import short

SYSTEM = """You audit programs written to solve one optimisation problem, to find what they ALL do the same way. A \
design decision that every program makes identically is invisible to a search that compares programs: nothing \
varies, so nothing tells whether another choice would be better. Your job is to name those decisions, at the level \
of design concepts, so they can be varied. Be concrete and specific to these programs. Answer with JSON only."""

PROPOSE = """{problem}

## Decisions already on the design map (these vary already; don't repeat them)
{known}

## The programs ({k}, the strongest and most different the run has; each clipped)
{programs}

## Your task
List what EVERY one of these programs does the same way, at the level of design concepts: how the solution is \
represented (its form, its size, its grid), what is optimised and how the maximum or other hard parts are handled, \
how the search starts, what moves it makes, what it accepts, how it spends its time, what it assumes about the \
solution's shape. Sort each item strictly:
- "problem": fixed by the problem statement above, so every valid program must do it: how the score is defined or \
computed, the form of a valid answer, the interface, the time limit. Not a choice.
- "detail": how a program computes or organises things without changing which solution it finds: the convolution \
routine (direct or FFT), how time is measured or enforced, caching, numeric types, array layout, logging.
- "decision": a choice about the solution or the search that could change which solution is found or how good it is. \
For each, give 2-3 concrete alternatives a program could build instead, each in at most 15 words.
When unsure between "decision" and the other two, choose the other two: a false "decision" wastes experiments.

Answer: {{"invariants": [{{"what": "...", "category": "problem" | "detail" | "decision", "alternatives": ["...", \
"..."], "why": "one line: why another choice might change the result"}}]}} with at most 8 items, decisions first."""

VERIFY = """{problem}

## Decisions already on the design map
{known}

## The claims to check: each says something every program does
{claims}

## The programs ({k}; each clipped)
{programs}

## Your task
For each claim, first sort it, independently of how it was proposed:
- "problem": fixed by the problem statement above (how the score is defined or computed, the form of a valid \
answer, the interface, the time limit);
- "detail": changes how a program computes or organises things but not which solution it finds (the convolution \
routine, timing code, caching, numeric types);
- "decision": a choice about the solution or the search that could change which solution is found or how good it is.
Say also whether it is the same decision as one already on the map (its id, like "A4"), or null if it is new.
Then, for each program in order, say whether it does that same thing (true) or something different (false). If a \
program doesn't show it either way, answer true only if its approach clearly implies it.

Answer: {{"checks": [{{"claim": 1, "category": "problem" | "detail" | "decision", "on_map": "A4" | null, "same": \
[true, false, ...]}}, ...]}} with one list of {k} booleans per claim."""


def program_block(p, chars):
    return f"### {p.id} (score {p.score:.6f}, {p.n} steps)\n```python\n{(p.code or '')[:chars]}\n```"


def samples(run, k=8):
    """(proposer sample, verifier sample): different programs. Proposer: the record and the tops of the best hills;
    verifier: the best programs of other tracks, then the most recent strong programs."""
    a = run.archive
    ok = lambda p: p is not None and p.valid and p.code and run.archive.in_class(p) and p.role != "import"  # noqa: E731
    first, seen = [], set()
    best = a.best()
    if ok(best):
        first.append(best)
        seen.add(best.id)
    for h in sorted(run.hills.values(), key=lambda h: -(h.get("top_score") or 0)):
        p = a.programs.get(h.get("top"))
        if ok(p) and p.id not in seen and len(first) < k:
            first.append(p)
            seen.add(p.id)
    second = []
    for t in sorted(run.tracks.values(), key=lambda t: -(t.get("best") or 0)):
        p = a.programs.get(t.get("best_id") or "")
        if ok(p) and p.id not in seen and len(second) < k:
            second.append(p)
            seen.add(p.id)
    for p in sorted(a.valid(), key=lambda p: -int(p.id[1:])):
        if len(second) >= k:
            break
        if ok(p) and p.id not in seen and p.score >= 0.9 * (best.score if best else 0):
            second.append(p)
            seen.add(p.id)
    return first, second


def parse(text, key):
    from helix4.prompts import extract_json
    js = extract_json(text or "") or {}
    out = js.get(key) if isinstance(js, dict) else None
    return out if isinstance(out, list) else []


def audit(run, gen, k=8, chars=3500, min_share=0.75, log=print):
    """One round. Returns the row written to audits.jsonl (new decisions included)."""
    first, second = samples(run, k)
    row = {"gen": gen, "proposer": [p.id for p in first], "verifier": [p.id for p in second], "proposed": [],
           "confirmed": [], "new_axes": [], "empty": True}
    if len(first) < 3 or len(second) < 3:
        row["skipped"] = "too few programs to compare"
        return row
    problem = run.problem.DESCRIPTION              # the full statement: what is fixed by the problem, and what isn't
    known = "\n".join(f"- {a}: {run.cb.axes[a]['question'] or run.cb.name(a)}" for a in run.cb.active_axes()) or "-"
    user = PROPOSE.format(problem=problem, known=known, k=len(first),
                          programs="\n\n".join(program_block(p, chars) for p in first))
    items = parse(run.call("auditor", SYSTEM, user, temperature=0.3, max_tokens=4000, effort="low", gen=gen),
                  "invariants")
    items = [x for x in items if isinstance(x, dict) and x.get("what")][:8]
    row["proposed"] = [{"what": short(x.get("what"), 200), "category": x.get("category"),
                        "alternatives": [short(y, 120) for y in (x.get("alternatives") or [])][:3]} for x in items]
    decisions = [x for x in items if str(x.get("category", "")).lower().startswith("decision")
                 and len(x.get("alternatives") or []) >= 1]
    if not decisions:
        return row
    claims = "\n".join(f"{i}. {short(x['what'], 200)}" for i, x in enumerate(decisions, 1))
    user = VERIFY.format(problem=problem, known=known, claims=claims, k=len(second),
                         programs="\n\n".join(program_block(p, chars) for p in second))
    checks = parse(run.call("auditor", SYSTEM, user, temperature=0.0, max_tokens=2000, effort="none", gen=gen),
                   "checks")
    share, sorted_out = {}, {}
    for c in checks:
        if not isinstance(c, dict):
            continue
        try:
            i = int(c.get("claim")) - 1
        except (TypeError, ValueError):
            continue
        same = [bool(v) for v in (c.get("same") or [])][: len(second)]
        if 0 <= i < len(decisions) and same:
            share[i] = sum(same) / len(second)
            if not str(c.get("category", "")).lower().startswith("decision"):
                sorted_out[i] = str(c.get("category") or "?")      # the second reading sorts it out of the decisions
            elif c.get("on_map") and run.cb.resolve(str(c["on_map"]).strip()) in run.cb.active_axes():
                sorted_out[i] = f"on the map already ({run.cb.resolve(str(c['on_map']).strip())})"
    row["sorted_out"] = [{"what": short(decisions[i]["what"], 200), "as": cat} for i, cat in sorted_out.items()]
    for i, x in enumerate(decisions):
        if share.get(i, 0.0) < min_share or i in sorted_out:
            continue
        what = " ".join(str(x["what"]).split())[:150]
        if run.cb.find_axis(what) is not None:
            continue                                      # the map has it already, in other words
        row["confirmed"].append({"what": what, "share": round(share[i], 2),
                                 "alternatives": [short(y, 120) for y in x["alternatives"]][:3],
                                 "why": short(x.get("why"), 200)})
    return row


def apply(run, row, gen):
    """Each confirmed invariant becomes a decision on the map, its alternatives targets (helix10/run.py)."""
    added = []
    for c in row.get("confirmed", []):
        q = f"Every program so far: {c['what']}. Is that the right choice?"
        aid = run.cb.add_axis(c["what"], gen, source="audit", question=q)
        shared = run.cb.add_value(aid, f"as every program so far: {short(c['what'], 100)}", gen, source="audit")
        run.borrowed.setdefault("axes", {})[aid] = {"key": "audit", "question": q, "attached": False,
                                                     "origin": "audit", "gen": gen}
        alts = []
        for alt in c["alternatives"]:
            vid = run.cb.add_value(aid, alt, gen, source="audit")
            if vid != shared:
                run.borrowed.setdefault("values", {})[vid] = {
                    "name": alt, "origin": "audit", "gen": gen,
                    "note": f"an alternative to what every program so far does ({c['what']}): the invariant audit, "
                            f"generation {gen}; {c.get('why') or ''}".strip()}
                alts.append(vid)
        added.append({"axis": aid, "shared": shared, "alternatives": alts})
    row["new_axes"] = added
    row["empty"] = not added
    return added


def due(rows, gen, last_record, every=10, stop_after=2, first=None):
    """True if an audit should run at generation `gen` (the first one not before generation `first`, if given)."""
    rows = [r for r in rows if not r.get("skipped")]      # a round skipped for want of programs doesn't count
    if not rows:
        return first is None or gen >= first     # a cold start's first programs share only their youth
    last = rows[-1]
    if gen - last["gen"] < every:
        return False
    empties = 0
    for r in reversed(rows):
        if not r.get("empty"):
            break
        empties += 1
    if empties >= stop_after and last_record <= last["gen"]:
        return False                       # resting: nothing new twice in a row, and the record hasn't moved since
    return True


def fake_reply(user):
    """A deterministic reply for tests (no model)."""
    if "## The claims to check" in user:
        k = int(re.search(r"## The programs \((\d+);", user).group(1))
        n = len(re.findall(r"^\d+\. ", user.split("## The claims to check")[1].split("## The programs")[0], re.M))
        return json.dumps({"checks": [{"claim": i + 1, "category": "decision", "same": [True] * k} for i in range(n)]})
    return json.dumps({"invariants": [
        {"what": "a fake shared grid of equal steps", "category": "decision",
         "alternatives": ["steps of free widths", "a smooth parametric bump"], "why": "a test"},
        {"what": "written in Python", "category": "detail", "alternatives": []}]})
