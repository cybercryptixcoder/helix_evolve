"""The annotator: gives every program a coordinate on the design map (docs/V9_DESIGN.md).

Two readings, both one cheap model call:
- **from the diff** (the usual case): the base program's coordinate is known; the annotator reads the change (the
  author's intent and summary, and the code diff) and says which axes it moved, and to which options. Everything else
  is inherited, so a reading error stays local instead of spreading over every axis. A change that only tunes numbers
  moves nothing.
- **in full**: the annotator reads the whole program and gives an option for every axis. Used when the base has no
  coordinate, when the diff is too long to read (a rewrite), for a drop's or flip's landing (the read-back: did the
  coder build what was asked?), and on a sample of programs read twice independently, to measure how reliable each
  axis is (agreement and Cohen's kappa).

Both may report an option no axis lists (a new value) or a decision no axis describes (a new axis): that is how the
codebook grows from the run's own programs. Names are matched against the codebook before anything is added
(helix9/codebook.py), so the same thing said differently doesn't become a second axis.

Problem-agnostic: the prompts talk about design decisions in general; the axes come from the run itself.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from helix4 import prompts as P4
from helix9.codebook import Codebook, axis_of, is_new

SYSTEM = """You read programs written in an evolutionary search and say which design decisions they make. A design \
decision is a choice of approach: how a solution is represented, built, searched, judged or how time is spent; not \
an implementation detail or a tuned number. You use the ids of a given list of decisions (axes) and their options \
(values). Be literal: report what the code does, not what its comments hope. Reply with JSON only."""

DIFF_ASK = """## The design decisions known so far (axes), with their options (values)
{codebook}

## The base program's design ({base})
{base_design}

## The new program ({pid})
What its author said: {intent}
{summary}
The change, as a unified diff (base -> new){cut}:
```diff
{diff}
```

Which design decisions did this change move, and to which options? Use the ids above.
- If an axis took an option that isn't listed, give it a short name as "new_value".
- If the change moved a design decision that no axis above describes, add it as "new_axis" (the decision, phrased \
as a question), with "base_value" (what the base did) and "value" (what the new program does).
- A change that only tunes numbers, fixes bugs or polishes the implementation moves no axis: reply with an empty list.
Reply with one JSON object and nothing else:
```json
{{"changes": [{{"axis": "A3", "value": "A3.v2"}}, {{"axis": "A5", "new_value": "short name"}},
              {{"new_axis": "the decision, as a question", "base_value": "short name", "value": "short name"}}]}}
```"""

FULL_ASK = """## The design decisions known so far (axes), with their options (values)
{codebook}

## The program ({pid})
```python
{code}
```

For every axis above, which option does this program use? Use the value ids.
- If it uses an option that isn't listed, give {{"new_value": "short name"}}.
- If the axis doesn't apply to this program, give "n/a".
- Then list up to 2 important design decisions of this program that no axis describes, as "new_axes".
Reply with one JSON object and nothing else:
```json
{{"design": {{"A1": "A1.v2", "A2": {{"new_value": "short name"}}, "A3": "n/a"}},
 "new_axes": [{{"axis": "the decision, as a question", "value": "short name"}}]}}
```"""


def _js(text):
    js = P4.extract_json(text or "")
    return js if isinstance(js, dict) else None


def _value(cb, aid, raw, gen, source):
    """A reply's option for axis aid: an existing id, a name to match or add, or None (n/a, unreadable)."""
    aid = cb.resolve(aid)
    if aid not in cb.axes:
        return None
    if isinstance(raw, dict):
        name = raw.get("new_value") or raw.get("value") or raw.get("name")
        return cb.add_value(aid, name, gen, source) if name and str(name).strip() else None
    raw = str(raw or "").strip()
    if not raw or raw.lower() in ("n/a", "na", "none", "unknown", "?"):
        return None
    if raw in cb.axes[aid]["values"] or (axis_of(raw) == aid and cb.resolve_value(raw) in cb.values(aid)):
        return cb.resolve_value(raw)
    if re.fullmatch(r"A\d+\.v\d+", raw):
        return None                                   # an id of another axis, or an unknown id: unreadable
    return cb.add_value(aid, raw, gen, source)        # a name instead of an id


def diff_prompt(cb, axes, base, base_coord, p, diff, cut=False, stats=None):
    return DIFF_ASK.format(codebook=cb.text(axes, stats=stats), base=base.id,
                           base_design=cb.describe(base_coord, axes) or "- (not known)",
                           pid=p.id, intent=(p.intent or "-")[:600],
                           summary=f"Its summary: {p.summary[:400]}" if p.summary else "",
                           cut=" (cut short: only its start is shown)" if cut else "", diff=diff)


def full_prompt(cb, axes, p, chars=20000):
    return FULL_ASK.format(codebook=cb.text(axes), pid=p.id, code=P4.clip(p.code, chars))


def apply_diff_reply(cb, text, base_coord, gen, source="annotator"):
    """(coordinate, info) from a diff reading. A reply that can't be read leaves the base's coordinate (and says
    so), so the program still has a usable, if uncertain, coordinate."""
    js = _js(text)
    coord = dict(base_coord or {})
    info = {"mode": "diff", "readable": js is not None, "changed": {}, "new_axes": [], "new_values": []}
    if js is None:
        return coord, info
    for ch in js.get("changes") or []:
        if not isinstance(ch, dict):
            continue
        if ch.get("new_axis"):
            n0 = len(cb.axes)
            aid = cb.add_axis(str(ch["new_axis"]), gen, source)
            if len(cb.axes) > n0:
                info["new_axes"].append(aid)
            bv = ch.get("base_value")
            if bv and aid not in coord:
                v0 = cb.add_value(aid, str(bv), gen, source)
                coord[aid] = v0                      # the base did this (recorded for the base's children)
            v = _value(cb, aid, ch.get("value"), gen, source)
            if v:
                coord[aid] = v
                info["changed"][aid] = v
            continue
        aid = cb.resolve(str(ch.get("axis") or "").strip())
        if aid not in cb.axes:
            continue
        before = set(cb.values(aid))
        v = _value(cb, aid, ch if ch.get("new_value") else ch.get("value"), gen, source)
        if v:
            if v not in before:
                info["new_values"].append(v)
            if coord.get(aid) != v:
                coord[aid] = v
                info["changed"][aid] = v
    return cb.canonical(coord), info


def apply_full_reply(cb, text, axes, gen, source="annotator"):
    js = _js(text)
    info = {"mode": "full", "readable": js is not None, "new_axes": [], "new_values": []}
    coord = {}
    if js is None:
        return coord, info
    design = js.get("design") or {}
    if isinstance(design, dict):
        for a, raw in design.items():
            aid = cb.resolve(str(a).strip())
            if aid not in cb.axes:
                continue
            before = set(cb.values(aid))
            v = _value(cb, aid, raw, gen, source)
            if v:
                coord[aid] = v
                if v not in before:
                    info["new_values"].append(v)
    for na in (js.get("new_axes") or [])[:2]:
        if isinstance(na, dict) and na.get("axis"):
            n0 = len(cb.axes)
            aid = cb.add_axis(str(na["axis"]), gen, source)
            if len(cb.axes) > n0:
                info["new_axes"].append(aid)
            v = _value(cb, aid, na.get("value"), gen, source)
            if v:
                coord[aid] = v
    return cb.canonical(coord), info


# ---------------------------------------------------------------------------------------------- reliability
def kappa(pairs):
    """Cohen's kappa for a list of (value, value) readings of one axis."""
    n = len(pairs)
    if n == 0:
        return None, 0, 0
    agree = sum(1 for a, b in pairs if a == b)
    pa = Counter(a for a, _ in pairs)
    pb = Counter(b for _, b in pairs)
    pe = sum(pa[k] * pb.get(k, 0) for k in pa) / (n * n)
    po = agree / n
    k = 1.0 if pe >= 1.0 - 1e-12 else (po - pe) / (1 - pe)
    return k, agree, n


def agreement(rows, axes):
    """{axis: (n, agree, kappa)} over rows of {"first": coord, "second": coord} (both full readings)."""
    out = {}
    for a in axes:
        pairs = [(r["first"].get(a), r["second"].get(a)) for r in rows
                 if r.get("first") is not None and r.get("second") is not None
                 and (r["first"].get(a) or r["second"].get(a))]
        k, agree, n = kappa(pairs)
        out[a] = (n, agree, k)
    return out


def update_agreement(cb, rows):
    for a, (n, agree, k) in agreement(rows, cb.active_axes()).items():
        if n:
            cb.set_agreement(a, n, agree, k)


# ---------------------------------------------------------------------------------------------- effort
def effort_of(parent_coord, parent_effort, coord, axes=None):
    """Experiments spent at (or next to) a design: +1 for a polish (no axis moved), a share carried over for one moved
    axis (the rest is re-tuned), little for two or more (a new design needs its own climb)."""
    if parent_effort is None:
        return 1.0
    keys = axes if axes is not None else set(parent_coord) | set(coord)
    moved = sum(1 for a in keys if parent_coord.get(a) and coord.get(a) and parent_coord[a] != coord[a])
    if moved == 0:
        return parent_effort + 1.0
    if moved == 1:
        return parent_effort * 0.6 + 1.0
    return min(parent_effort * 0.3, 2.0) + 1.0


def fake_reply(cb_text, user):
    """A fake annotator for tests: reads 'DESIGN = {...}' from a program, if there is one (see helix9/planted.py),
    else reports no change. Decisions the codebook in the prompt already names are given by their ids; the others are
    reported as new decisions (at most two in a full reading, as the real prompt allows). Mirrors the reply format."""
    ids = {}
    for m in re.finditer(r"^(A\d+): (.+)$", (cb_text or "") + "\n" + (user or ""), re.M):
        ids.setdefault(m.group(2).strip(), m.group(1))
    m = re.search(r"DESIGN = (\{[^}]*\})", user)
    if "## The program (" in user:
        if not m:
            return json.dumps({"design": {}, "new_axes": []})
        d = json.loads(m.group(1))
        return json.dumps({"design": {ids[k]: v for k, v in d.items() if k in ids},
                           "new_axes": [{"axis": k, "value": v} for k, v in d.items() if k not in ids][:2]})
    ms = re.findall(r"^\+DESIGN = (\{[^}]*\})", user, re.M)
    if not ms:
        return json.dumps({"changes": []})
    d = json.loads(ms[-1])
    old = re.findall(r"^-DESIGN = (\{[^}]*\})", user, re.M)
    o = json.loads(old[-1]) if old else {}
    return json.dumps({"changes": [{"axis": ids[k], "value": v} if k in ids else
                                   {"new_axis": k, "base_value": o.get(k), "value": v}
                                   for k, v in d.items() if o.get(k) != v]})


def is_value_new(vid):
    return is_new(vid)


def safe_float(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None
