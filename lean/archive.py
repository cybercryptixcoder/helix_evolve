"""Every program ever written, as a tree (each points at the program it started from). Appended to
programs.jsonl and never changed; results (constructions) saved as .npy so a child can start from its parent's."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
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

    def line(self):
        if not self.valid:
            return f"{self.id} ({self.role}, round {self.round}, from {self.parent}): FAILED: {self.error[:120]}"
        d = f", {self.delta:+.9f} on its start" if self.delta is not None else ""
        return f"{self.id} ({self.role}, round {self.round}, from {self.parent or '-'}): {self.score:.9f}{d}"


def short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


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
                    self._index(Program(**json.loads(line)))

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

    def sample_parent(self, rng, pool):
        """Rank-weighted (1 / (1 + rank)), divided by sqrt(1 + children): strong programs not yet built on much."""
        pool = sorted(pool, key=lambda p: (-p.score, p.round, p.id))
        w = [1.0 / (1 + i) / math.sqrt(1 + self.children.get(p.id, 0)) for i, p in enumerate(pool)]
        return rng.choices(pool, weights=w, k=1)[0]
