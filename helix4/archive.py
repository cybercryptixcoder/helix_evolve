"""The population: every program ever written, as a tree (each program points at the program it improved on).

A program record holds its code, who wrote it and why (the intent), the diff from its parent, the result of its
evaluation (score, the change against the construction it started from, the evaluator's feedback lines, errors),
and where its construction is saved. Records are appended to `programs.jsonl` and never changed afterwards, except
the children count kept in memory. Constructions are saved as .npy files, so a child can start from its parent's.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Program:
    id: str
    gen: int
    role: str                      # seed | deep | wide
    parent: str | None
    intent: str                    # one line: what it set out to do
    code: str
    plan: dict = field(default_factory=dict)   # deep: the Researcher's experiment (hypothesis, change, prediction, builds_on)
    diff: str = ""
    valid: bool = False
    score: float | None = None
    start_score: float | None = None
    delta: float | None = None     # score minus the score of the construction it started from
    feedback: list = field(default_factory=list)
    error: str = ""
    cpu: float | None = None
    n: int | None = None           # steps in its construction
    summary: str = ""              # the author's own one-line summary of the change
    duplicate_of: str | None = None

    def line(self, digits=6):
        if not self.valid:
            return f"{self.id} (gen {self.gen}, {self.role}, from {self.parent}): FAILED: {self.error[:120]}"
        d = f", {self.delta:+.{digits}f} on its start" if self.delta is not None and self.parent else ""
        return f"{self.id} (gen {self.gen}, {self.role}, from {self.parent or '-'}): {self.score:.{digits}f}{d}"


def code_hash(code):
    return hashlib.sha1("\n".join(l.rstrip() for l in code.strip().splitlines()).encode()).hexdigest()[:16]


def make_diff(old, new, limit=60):
    lines = [l for l in difflib.unified_diff(old.strip().splitlines(), new.strip().splitlines(), lineterm="", n=1)
             if not l.startswith(("---", "+++"))]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit} more diff lines)"]
    return "\n".join(lines)


class Archive:
    def __init__(self, run_dir: Path):
        self.dir = Path(run_dir)
        (self.dir / "constructions").mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "programs.jsonl"
        self.programs: dict[str, Program] = {}
        self.children: dict[str, int] = {}
        self.hashes: dict[str, str] = {}
        self.counter = 0
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    try:
                        self._add(Program(**json.loads(line)))
                    except (TypeError, ValueError):
                        pass

    def _add(self, p: Program):
        self.programs[p.id] = p
        self.counter = max(self.counter, int(p.id[1:]))
        if p.parent:
            self.children[p.parent] = self.children.get(p.parent, 0) + 1
        self.hashes.setdefault(code_hash(p.code) + (p.parent or ""), p.id)

    def new_id(self):
        self.counter += 1
        return f"p{self.counter:04d}"

    def add(self, p: Program, construction=None):
        if construction is not None and p.valid:
            np.save(self.dir / "constructions" / f"{p.id}.npy", np.asarray(construction, dtype=float))
        self._add(p)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(p)) + "\n")

    def truncate(self, gen_done):
        """Forget programs of unfinished generations (for resume): rewrite the log without them."""
        drop = [p for p in self.programs.values() if p.gen > gen_done]
        if not drop:
            return 0
        for p in drop:
            (self.dir / "constructions" / f"{p.id}.npy").unlink(missing_ok=True)
        keep = [p for p in self.programs.values() if p.gen <= gen_done]
        self.path.write_text("".join(json.dumps(asdict(p)) + "\n" for p in keep))
        self.programs, self.children, self.hashes, self.counter = {}, {}, {}, 0
        for p in keep:
            self._add(p)
        return len(drop)

    def construction(self, pid):
        f = self.dir / "constructions" / f"{pid}.npy"
        return np.load(f) if f.exists() else None

    def duplicate(self, code, parent):
        """The program with the same code built on the same parent, if any (it would be the same experiment)."""
        return self.hashes.get(code_hash(code) + (parent or ""))

    # ---------------------------------------------------------------- views
    def valid(self):
        return [p for p in self.programs.values() if p.valid]

    def ranked(self):
        return sorted(self.valid(), key=lambda p: (-p.score, p.gen, p.id))

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
        parts = []
        for p in self.lineage(pid, depth):
            if p.score is None:
                continue
            what = f" ({p.delta:+.5f}: {short(p.intent, 60)})" if p.parent and p.delta is not None else ""
            parts.append(f"{p.id} {p.score:.5f}{what}")
        return " -> ".join(parts)

    def sample_parent(self, rng: random.Random, pool=None, alpha=1.0):
        """Rank-based (weight 1/(1+rank)), divided by sqrt(1 + children): favours strong programs that haven't been
        built on much, so the wide loop keeps several branches alive instead of hill-climbing one champion."""
        pool = sorted(pool if pool is not None else self.valid(), key=lambda p: (-p.score, p.gen, p.id))
        if not pool:
            return None
        w = [1.0 / (1 + i) ** alpha / math.sqrt(1 + self.children.get(p.id, 0)) for i, p in enumerate(pool)]
        return rng.choices(pool, weights=w, k=1)[0]



def short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"
