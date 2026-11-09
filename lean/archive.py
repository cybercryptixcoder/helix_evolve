"""Every program ever written, as a tree (each points at the program it started from). Appended to
programs.jsonl and never changed; results (constructions) saved as .npy so a child can start from its parent's."""
from __future__ import annotations

import difflib
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import numpy as np


@dataclass
class Program:
    id: str
    round: int
    role: str                       # seed | planned | mutation
    parent: str | None
    idea: str                       # what it set out to do: the plan's hypothesis, or the author's summary
    code: str
    plan: dict = field(default_factory=dict)
    valid: bool = False
    score: float | None = None
    start_score: float | None = None
    delta: float | None = None      # score minus its start's score
    feedback: list = field(default_factory=list)
    error: str = ""
    cpu: float | None = None
    duplicate_of: str | None = None
    summary: str = ""               # the author's own one-line summary of the change
    diff: str = ""                  # the change from its parent (shown to the Atlas's Distiller and when opened)
    reply: str = ""                 # how its author's reply came: "full" (the whole program) or "edits", "+retry"

    def line(self):
        """How the agents see a program: v4's words exactly (gen, deep/wide), with 9 digits instead of 6."""
        role = SHOWN.get(self.role, self.role)
        if not self.valid:
            return f"{self.id} (gen {self.round}, {role}, from {self.parent}): FAILED: {self.error[:120]}"
        d = f", {self.delta:+.9f} on its start" if self.delta is not None and self.parent else ""
        return f"{self.id} (gen {self.round}, {role}, from {self.parent or '-'}): {self.score:.9f}{d}"


SHOWN = {"planned": "deep", "mutation": "wide"}   # the roles' names in v4's prompts (the planned loop was "deep")
KNOWN = {f.name for f in fields(Program)}      # older records may hold fields this version doesn't use


def short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def make_diff(old, new, limit=60):
    """v4's unified diff, at most `limit` lines."""
    lines = [l for l in difflib.unified_diff(old.strip().splitlines(), new.strip().splitlines(), lineterm="", n=1)
             if not l.startswith(("---", "+++"))]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit} more diff lines)"]
    return "\n".join(lines)


def code_key(code, parent):
    norm = "\n".join(l.rstrip() for l in code.strip().splitlines())
    return hashlib.sha1(norm.encode()).hexdigest()[:16] + (parent or "")


class Archive:
    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        (self.dir / "constructions").mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "programs.jsonl"
        self.programs, self.children, self.keys, self.counter = {}, {}, {}, 0
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._index(Program(**{k: v for k, v in row.items() if k in KNOWN}))

    def _index(self, p):
        self.programs[p.id] = p
        self.counter = max(self.counter, int(p.id[1:]))
        if p.parent:
            self.children[p.parent] = self.children.get(p.parent, 0) + 1
        self.keys.setdefault(code_key(p.code, p.parent), p.id)

    def add(self, p, construction=None):
        self.counter += 1
        p.id = f"p{self.counter:04d}"
        if construction is not None and p.valid:
            np.save(self.dir / "constructions" / f"{p.id}.npy", np.asarray(construction, dtype=float))
        self._index(p)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(p)) + "\n")
        return p

    def truncate(self, round_done):
        """Forget the programs of an unfinished round (on resume)."""
        keep = [p for p in self.programs.values() if p.round <= round_done]
        for p in self.programs.values():
            if p.round > round_done:
                (self.dir / "constructions" / f"{p.id}.npy").unlink(missing_ok=True)
        self.path.write_text("".join(json.dumps(asdict(p)) + "\n" for p in keep))
        self.programs, self.children, self.keys, self.counter = {}, {}, {}, 0
        for p in keep:
            self._index(p)

    def construction(self, pid):
        f = self.dir / "constructions" / f"{pid}.npy"
        return np.load(f) if f.exists() else None

    def duplicate(self, code, parent):
        return self.keys.get(code_key(code, parent))

    def ranked(self):
        return sorted((p for p in self.programs.values() if p.valid), key=lambda p: (-p.score, p.round, p.id))

    def best(self):
        r = self.ranked()
        return r[0] if r else None

    def lineage(self, pid, depth=8):
        out, p = [], self.programs.get(pid)
        while p is not None and len(out) < depth:
            out.append(p)
            p = self.programs.get(p.parent) if p.parent else None
        return list(reversed(out))

    def lineage_line(self, pid, depth=6):
        """The program's last `depth` steps of ancestry, oldest first: each step's score, and what it changed and
        gained (v4's line, with 9 digits instead of 5 so that small gains are visible)."""
        parts = []
        for p in self.lineage(pid, depth):
            if p.score is None:
                continue
            what = f" ({p.delta:+.9f}: {short(p.idea, 60)})" if p.parent and p.delta is not None else ""
            parts.append(f"{p.id} {p.score:.9f}{what}")
        return " -> ".join(parts)

    def sample_parent(self, rng, pool):
        """Rank-weighted (1 / (1 + rank)), divided by sqrt(1 + children): strong programs not yet built on much."""
        pool = sorted(pool, key=lambda p: (-p.score, p.round, p.id))
        w = [1.0 / (1 + i) / math.sqrt(1 + self.children.get(p.id, 0)) for i, p in enumerate(pool)]
        return rng.choices(pool, weights=w, k=1)[0]
