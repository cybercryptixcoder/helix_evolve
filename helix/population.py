"""Programs, hypotheses, and the run's record on disk.

Everything a run produces goes into its run folder as plain files, so a crashed
run can be resumed and every decision can be read back afterwards:

  config.json        the settings the run was started with
  programs.jsonl     one line per scored program: code, scores, branch, parent, hypothesis
  hypotheses.jsonl   the research log: one line per tested hypothesis and its verdict
  generations.jsonl  one line per generation: survivors, best score, LLM calls, time
  llm_calls.jsonl    every prompt and reply (written by llm.py)
  best_program.py    the best program so far
  candidates/        every candidate as a .py file, named by its id
"""
import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Program:
    id: str
    code: str
    generation: int
    branch: str                       # seed | wide | deep | zeroshot | baseline
    parent_id: str | None = None
    hypothesis_id: str | None = None
    note: str = ""                    # the agent's own one-line description of what it did
    valid: bool = False
    score: float | None = None
    families: dict = field(default_factory=dict)   # family -> excess %
    error: str | None = None
    model: str = ""
    repaired: bool = False
    duplicate_of: str | None = None

    @property
    def rank_key(self):
        """Invalid programs rank below every valid one."""
        return self.score if self.valid and self.score is not None else float("-inf")


@dataclass
class Hypothesis:
    id: str
    generation: int
    base_id: str
    claim: str
    change: str
    prediction: str
    program_id: str | None = None
    base_score: float | None = None
    new_score: float | None = None
    delta: float | None = None
    verdict: str = "pending"          # supported | refuted | flat | invalid | unchanged
    family_shift: dict = field(default_factory=dict)   # family -> change in excess % (negative = better)


def judge(h, base, new, epsilon):
    """Fill in a hypothesis's verdict by comparing its program with the base program."""
    h.program_id = new.id
    h.base_score = base.score
    if new.duplicate_of == base.id:
        h.verdict = "unchanged"           # the Coder produced the base program again
        return h
    if not new.valid:
        h.verdict = "invalid"
        return h
    h.new_score = new.score
    h.delta = round(new.score - base.score, 4)
    h.family_shift = {f: round(new.families[f] - base.families[f], 3) for f in base.families if f in new.families}
    h.verdict = "supported" if h.delta > epsilon else "refuted" if h.delta < -epsilon else "flat"
    return h


def _code_hash(code):
    lines = [line.rstrip() for line in code.strip().splitlines()]
    return hashlib.sha1("\n".join(lines).encode()).hexdigest()


class Store:
    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        self.candidates = self.dir / "candidates"
        self.candidates.mkdir(parents=True, exist_ok=True)
        self.programs = {}
        self.hypotheses = []
        self._by_hash = {}
        self._counters = {"p": 0, "h": 0}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ ids and lookup
    def new_id(self, kind):
        with self._lock:
            self._counters[kind] += 1
            return f"{kind}{self._counters[kind]:04d}"

    def duplicate_of(self, code):
        """The already-scored program with identical code, if any."""
        with self._lock:
            pid = self._by_hash.get(_code_hash(code))
        return self.programs.get(pid) if pid else None

    def candidate_path(self, pid):
        return self.candidates / f"{pid}.py"

    def ranked(self, ids=None):
        with self._lock:
            progs = [self.programs[i] for i in ids] if ids is not None else list(self.programs.values())
        return sorted(progs, key=lambda p: p.rank_key, reverse=True)

    def best(self):
        with self._lock:
            return self._best_unlocked()

    def _best_unlocked(self):
        valid = [p for p in self.programs.values() if p.valid]
        return max(valid, key=lambda p: p.rank_key) if valid else None

    # ------------------------------------------------------------ recording
    def add_program(self, p):
        with self._lock:
            self.programs[p.id] = p
            self._by_hash.setdefault(_code_hash(p.code), p.id)
            self._append("programs.jsonl", asdict(p))
            if self._best_unlocked() is p:
                (self.dir / "best_program.py").write_text(
                    f"# {p.id} | score {p.score} | generation {p.generation} | {p.branch} branch\n{p.code}"
                )

    def add_hypothesis(self, h):
        with self._lock:
            self.hypotheses.append(h)
            self._append("hypotheses.jsonl", asdict(h))

    def log_generation(self, record):
        with self._lock:
            self._append("generations.jsonl", record)

    def save_config(self, config):
        (self.dir / "config.json").write_text(json.dumps(config, indent=2))

    def _append(self, name, record):
        with (self.dir / name).open("a") as f:
            f.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------ resume
    @classmethod
    def load(cls, run_dir):
        """Rebuild a store from a run folder. Returns (store, last generation record or None)."""
        store = cls(run_dir)
        for line in _read_lines(store.dir / "programs.jsonl"):
            p = Program(**json.loads(line))
            store.programs[p.id] = p
            store._by_hash.setdefault(_code_hash(p.code), p.id)
        for line in _read_lines(store.dir / "hypotheses.jsonl"):
            store.hypotheses.append(Hypothesis(**json.loads(line)))
        store._counters["p"] = max([int(i[1:]) for i in store.programs] or [0])
        store._counters["h"] = max([int(h.id[1:]) for h in store.hypotheses] or [0])
        gens = [json.loads(line) for line in _read_lines(store.dir / "generations.jsonl")]
        return store, (gens[-1] if gens else None)


def _read_lines(path):
    return [line for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
