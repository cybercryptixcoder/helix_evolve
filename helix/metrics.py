"""Readable units for the score, next to the evaluator's own.

The evaluator's score is −(mean excess %): bins above a lower bound that ignores job shapes, so it is
negative, and even a perfect packing can't reach 0. It stays the score the search optimises (so runs stay
comparable), and this module adds two units measured against the best packing that could possibly exist
(the optimal packing, bounded in helix/bounds.py):

  waste      extra bins per 100 the optimal packing needs, averaged over the families.
             0 = as good as the optimum; lower is better. (Against the optimum's proven lower bound,
             so it never flatters a program.)
  progress   how far a program has come from Code Zero towards the optimum, in %:
             0% = Code Zero, 100% = the optimal packing. Higher is better.

Both are computed from the per-family results the evaluator already reports, so they apply to every
run, including runs made before this module existed. Without stored bounds (python -m helix.bounds
--compute) they're None and only the evaluator's score is shown.
"""
from functools import lru_cache
from pathlib import Path

from . import bounds
from .sandbox import REPO_ROOT, evaluate_file

CODE_ZERO = REPO_ROOT / "programs" / "code_zero.py"
REFERENCES_DIR = Path(__file__).resolve().parent / "references"


def waste(families, split="train"):
    """Extra bins per 100 the optimal packing needs (mean over families), or None without bounds."""
    floor = bounds.family_floor(split)
    if not floor or not families:
        return None
    vals = [(1 + families[f] / 100) / (1 + floor[f]["lower"] / 100) - 1 for f in floor if f in families]
    if len(vals) != len(floor):
        return None
    return round(100 * sum(vals) / len(vals), 4)


def progress(families, start_families, split="train"):
    """% of the way from `start_families` (Code Zero's) to the optimal packing."""
    w, w0 = waste(families, split), waste(start_families, split)
    if w is None or w0 is None or w0 <= 0:
        return None
    return round(100 * (1 - w / w0), 2)


def units(families, start_families, split="train"):
    return {"waste": waste(families, split), "progress": progress(families, start_families, split)}


@lru_cache(maxsize=None)
def code_zero_families(split="train"):
    r = evaluate_file(CODE_ZERO, split, 120)
    return _families(r) if r.get("valid") else None


def references(split="train"):
    """The yardsticks, each in all three units: Code Zero, the classic online heuristics from the
    literature (helix/references/), the offline packer that sees every job, and the optimum."""
    return _references(split, bounds.version())


@lru_cache(maxsize=None)
def _scored_references(split):
    out = {}
    for path in sorted(REFERENCES_DIR.glob("*.py")):
        r = evaluate_file(path, split, 120)
        if r.get("valid"):
            out[path.stem] = (_first_comment(path) or path.stem, _families(r), r["score"])
    return out


@lru_cache(maxsize=4)
def _references(split, _version):
    start = code_zero_families(split)
    out = {}

    def add(key, label, families, kind, score=None):
        score = score if score is not None else (-round(sum(families.values()) / len(families), 4) if families else None)
        out[key] = {"label": label, "kind": kind, "score": score, **units(families, start, split)}

    if start:
        add("code_zero", "Code Zero (first fit)", start, "start")
    for key, (label, families, score) in _scored_references(split).items():
        add(key, label, families, "classic", score)
    try:
        from .reference import offline_reference
        off = offline_reference(split)
        add("offline_ffd", "Offline best-fit decreasing (sees every job in advance)", off["families"], "offline",
            off["score"])
    except Exception:
        pass
    floor = bounds.family_floor(split)
    if floor:
        fams = {f: v["lower"] for f, v in floor.items()}
        out["optimal"] = {"label": "Optimal packing (proven lower bound)", "kind": "optimal",
                          "score": -round(sum(fams.values()) / len(fams), 4), "waste": 0.0, "progress": 100.0}
    classic = [v for v in out.values() if v["kind"] == "classic" and v["score"] is not None]
    if classic:
        out["best_classic"] = dict(max(classic, key=lambda v: v["score"]), kind="best_classic")
    return out


def _families(result):
    return {f: v["excess_pct"] for f, v in result["families"].items()}


def _first_comment(path):
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").split(":")[0].strip()
    return ""
