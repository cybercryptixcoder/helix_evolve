"""A reference point for the score: an offline packer that sees every job before placing any.

The score is excess over a lower bound that ignores job shapes, so 0% can't be reached and "−6.8"
says little on its own. This packer sorts all jobs biggest first and puts each into the bin it fills
most tightly (best-fit decreasing, the classic offline heuristic). An online program never sees the
jobs ahead of it, so this is a strong practical reference (not a proof of optimality, and an online
program can beat it on some families). Progress is then reported as the share of the gap between
Code Zero and this reference that the search has closed.

  python -m helix.reference           print the reference on the train and test splits

Instances come from the evaluator's own code (read, never changed), so they are exactly the ones
programs are scored on.
"""
import sys
from functools import lru_cache

import numpy as np

from .sandbox import REPO_ROOT


def _best_fit_decreasing(items, cap, key):
    items, cap = np.asarray(items, dtype=np.int64), np.asarray(cap, dtype=np.int64)
    order = np.argsort(-key(items / cap), kind="stable")
    remaining = np.empty((len(items), 2), dtype=np.int64)
    n_open = 0
    for item in items[order]:
        rem = remaining[:n_open]
        fits = (rem >= item).all(axis=1)
        if fits.any():
            slack = ((rem - item) / cap).sum(axis=1)
            slack[~fits] = np.inf
            remaining[int(np.argmin(slack))] -= item
        else:
            remaining[n_open] = cap - item
            n_open += 1
    return n_open


def bins_used(items, cap):
    """The fewer bins of two orderings: by the larger normalised demand, and by the sum of both."""
    return min(_best_fit_decreasing(items, cap, lambda d: d.max(axis=1)),
               _best_fit_decreasing(items, cap, lambda d: d.sum(axis=1)))


@lru_cache(maxsize=None)
def offline_reference(split="train"):
    """{"score", "families": {family: excess %}} for the offline packer, in the evaluator's units."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from evaluator.problem import load_split
    per_family = {}
    for inst in load_split(split):
        used = bins_used(inst["items"], inst["capacity"])
        per_family.setdefault(inst["family"], []).append(used / inst["lower_bound"] - 1)
    families = {f: round(100 * sum(v) / len(v), 4) for f, v in per_family.items()}
    return {"score": -round(sum(families.values()) / len(families), 4), "families": families}


def gap_closed(score, start, reference):
    """Share (%) of the gap between the starting program and the reference that `score` has closed."""
    if score is None or start is None or reference is None or reference <= start:
        return None
    return round(100 * (score - start) / (reference - start), 1)


if __name__ == "__main__":
    for split in ("train", "test"):
        r = offline_reference(split)
        print(f"{split}: score {r['score']:.3f} | " + " | ".join(f"{f} {v:.2f}" for f, v in r["families"].items()))
