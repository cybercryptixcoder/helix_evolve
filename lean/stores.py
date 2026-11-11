"""The context store and the guidance store: what we give a run before it starts, beside the Atlas (what it learns).

- **Context** (a problem's `context`, Markdown): facts about the problem and its domain, taken as true. Every agent
  sees it with the problem's description. It never changes during a run.
- **Guidance** (a problem's `guidance`, Markdown entries each starting `## G<n>: <title>`): approaches that may help,
  from the field or from us. Each entry is a hypothesis, never deleted. Experiments that draw on an entry cite it; the
  entry's record (how many attempts gained, didn't, or failed, and how each implemented it) is computed by code from
  the measured results of the programs that cited it, read from the archive, so it needs no file of its own and is
  right after a resume. The planner and the mutators see every entry with its record; a coder sees the full text of
  the entries its experiment cites. The Atlas's Distiller is told which entries each program drew on, so its findings
  can say how an entry was implemented and what that did.

A problem with neither changes nothing: every prompt is as before.
"""
from __future__ import annotations

import re

from lean.archive import short

ENTRY = re.compile(r"^## (G\d+)\s*[:.]\s*(.+)$", re.M)

CONTEXT = "## Context: facts about this problem and its domain (given; take them as true)\n"
GUIDANCE = (
    "## The guidance store: approaches that may help\n"
    "Each entry is a hypothesis from the field or from the people running this search, not a fact: it may or may not "
    "help on this problem. Under each entry is its record in this search, computed from measured results: how the "
    "programs that drew on it did, and what each one tried. An untested entry is worth a first try. An entry that has "
    "not helped yet may still help if implemented differently: try a way not already listed, or leave it for now. An "
    "experiment that draws on entries names them in its \"guidance\" field (for example \"guidance\": [\"G3\"]); its "
    "coder then receives those entries in full.\n\n")
CITED = "## From the guidance store (the entries this experiment draws on)\n"
FIELD = '"guidance": ["<ids of guidance entries it draws on, if any>"],\n    '        # in the planner's reply format
MUTATION_FIELD = ', "guidance": ["<ids of guidance entries it draws on, if any>"]'   # in the mutation plan's format
MUTATOR_LINE = "\nIf your change draws on guidance entries, add one more line:\nGUIDANCE: <their ids, e.g. G3, G7>"
DISTILLER_NOTE = ("\nWhen a program drew on guidance entries (\"guidance: G3\" above), say in its finding which entry "
                  "and how it was implemented, so that entry's record is explained (\"G3, implemented as ...: no gain "
                  "because ...\").")


def ids(value):
    """The entry ids cited: a list, or a text like "G3, G7"."""
    if isinstance(value, str):
        value = re.findall(r"G\d+", value)
    return [str(x).strip() for x in (value or []) if re.fullmatch(r"G\d+", str(x).strip())]


def outcome(p):
    """A citing program's outcome: "gained", "no gain" or "failed" (a duplicate, which never ran, is not counted)."""
    if p.duplicate_of:
        return None
    if not p.valid:
        return "failed"
    return "gained" if (p.delta or 0) > 1e-9 else "no gain"


class Guidance:
    def __init__(self, text):
        marks = list(ENTRY.finditer(text or ""))
        self.entries = {}                              # {id: full entry text}, in order
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            self.entries[m.group(1)] = text[m.start():end].strip()

    def __bool__(self):
        return bool(self.entries)

    def record(self, gid, archive, before, last=4):
        """One entry's record from the programs of generations before `before` (so it is the same for every agent of a
        generation): counts, the best gain, and the latest attempts."""
        tried = [p for p in archive.programs.values()
                 if p.round < before and gid in (p.plan or {}).get("guidance", [])]
        tried = [(p, outcome(p)) for p in tried if outcome(p)]
        if not tried:
            return "Record: untested."
        n = {o: sum(1 for _, x in tried if x == o) for o in ("gained", "no gain", "failed")}
        gains = [p.delta for p, o in tried if o == "gained"]
        best = f" (best {max(gains):+.6f})" if gains else ""
        lines = [f"Record: tried {len(tried)} times: {n['gained']} gained{best}, {n['no gain']} no gain, "
                 f"{n['failed']} failed."]
        for p, o in tried[-last:]:
            res = f"{p.delta:+.6f}" if o != "failed" and p.delta is not None else o
            lines.append(f"- {p.id} ({res}): {short(p.idea, 140)}")
        if len(tried) > last:
            lines.insert(1, f"(latest {last} of {len(tried)})")
        return "\n".join(lines)

    def whole(self, archive, before):
        """Every entry with its record, for the planner and the mutators."""
        if not self.entries:
            return ""
        return GUIDANCE + "\n\n".join(f"{body}\n{self.record(g, archive, before)}" for g, body in self.entries.items()) + "\n\n"

    def cited(self, gids):
        """The full text of the cited entries (unknown ids are ignored), for a coder."""
        bodies = [self.entries[g] for g in gids if g in self.entries]
        return CITED + "\n\n".join(bodies) + "\n\n" if bodies else ""
