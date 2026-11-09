"""The knowledge bank: the field's knowledge of a problem, given to the agents beside the Atlas.

A problem may supply `knowledge`, a Markdown text of entries, each starting with a line `## K<n>: <title>`. The planner
and the mutators see the whole bank; a coder sees the full text of the entries its experiment cites (the plan's
`knowledge` field). Knowledge, not programs: the bank describes methods and facts, it holds no code to copy. A problem
without a bank changes nothing.
"""
from __future__ import annotations

import re

ENTRY = re.compile(r"^## (K\d+)\s*[:.]\s*(.+)$", re.M)

INTRO = ("## The knowledge bank: what the field knows about this problem\n"
         "Use it to design better programs: the state of the art, methods that work, facts about this problem. An "
         "experiment that draws on an entry names it in its \"knowledge\" field (for example \"knowledge\": "
         "[\"K3\"]); its coder then receives that entry in full.\n\n")
FIELD = '"knowledge": ["<ids of knowledge-bank entries it draws on, if any>"],\n    '   # in the plan's reply format
CITED = "## From the knowledge bank (the entries this experiment draws on)\n"


def parse(text):
    """{id: (title, full entry text)}, in order."""
    out = {}
    marks = list(ENTRY.finditer(text or ""))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[m.group(1)] = (m.group(2).strip(), text[m.start():end].strip())
    return out


class Bank:
    def __init__(self, text):
        self.entries = parse(text)

    def __bool__(self):
        return bool(self.entries)

    def whole(self):
        """The whole bank, for the planner and the mutators."""
        if not self.entries:
            return ""
        return INTRO + "\n\n".join(body for _, body in self.entries.values()) + "\n\n"

    def cited(self, ids):
        """The full text of the cited entries (unknown ids are ignored), for a coder."""
        bodies = [self.entries[i][1] for i in ids if i in self.entries]
        return CITED + "\n\n".join(bodies) + "\n\n" if bodies else ""

    @staticmethod
    def ids(value):
        """The entry ids an experiment cites: a list, or a string like "K3, K7"."""
        if isinstance(value, str):
            value = re.findall(r"K\d+", value)
        return [str(x).strip() for x in (value or []) if re.fullmatch(r"K\d+", str(x).strip())]
