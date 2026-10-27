"""Choosing where to jump on the design map: drops (2-4 axes at once) and flips (one axis) (docs/V9_DESIGN.md).

A drop is a coordinate the coder is asked to build: start from a base's coordinate (the record's, or another hill's
top), change k of its axes (kick size k between `kmin` and `kmax`), keep the rest. The coordinate is chosen by Thompson
sampling: draw one model from the landscape model's posterior and take the candidate it rates highest. Untried values
(and "a new option" of an axis) keep their prior uncertainty, so some draws rate them high: exploration without an
extra rule.

Constraints:
- at least `min_dist` axes from every known hill's top (on axes known for both), so a drop is not a polish of a known
  hill (a kick too small returns to the same basin; too large is a restart);
- not a target already dropped (tabu), and no pair of values known to be incompatible;
- only reliable axes (the run decides which).

Without a usable model (too few annotated programs), candidates are drawn uniformly: a random drop is still a directed
restart, unlike "write a fresh program", which samples the coder's default design.
"""
from __future__ import annotations

from itertools import combinations

from helix9.codebook import NEW, hamming


def options(levels, a, base_value, include_new=True):
    vs = [v for v in levels.get(a, []) if v != base_value and v != "?" and not v.endswith("." + NEW)]
    if include_new:
        vs.append(f"{a}.{NEW}")
    return vs


def candidates(base, axes, levels, kmin, kmax, n, rng, include_new=True):
    """Up to n distinct coordinates that change between kmin and kmax of `axes` in `base`."""
    axes = [a for a in axes if options(levels, a, base.get(a), include_new)]
    out, seen = [], set()
    if not axes:
        return out
    ks = [k for k in range(kmin, kmax + 1) if k <= len(axes)]
    if not ks:
        return out
    tries = 0
    while len(out) < n and tries < 20 * n:
        tries += 1
        k = ks[int(rng.integers(len(ks)))]
        chosen = sorted(rng.choice(len(axes), size=k, replace=False).tolist())
        change = {}
        for i in chosen:
            a = axes[i]
            opts = options(levels, a, base.get(a), include_new)
            change[a] = opts[int(rng.integers(len(opts)))]
        key = tuple(sorted(change.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(({**base, **change}, change))
    return out


def single_changes(base, axes, levels, include_new=True):
    out = []
    for a in axes:
        for v in options(levels, a, base.get(a), include_new):
            out.append(({**base, a: v}, {a: v}))
    return out


def admissible(coord, change, avoid, min_dist, tabu, compatible, axes):
    if compatible is not None and not compatible({k: v for k, v in coord.items() if not v.endswith("." + NEW)}):
        return False
    if tuple(sorted(change.items())) in tabu:
        return False
    for c in avoid:
        if hamming(coord, c, axes) < min_dist:
            # a coordinate is only "near" a hill on axes both know; with too few known axes it can't be judged near
            known = sum(1 for a in axes if coord.get(a) and c.get(a))
            if known >= min_dist:
                return False
    return True


def choose_drop(sample, base, axes, levels, rng, avoid=(), min_dist=2, tabu=(), compatible=None, kmin=2, kmax=4,
                n=1500, include_new=True):
    """The drop target: (coord, change, rating) or None. `sample` is a posterior draw (coords -> ratings) or None."""
    tabu = set(tabu)
    cands = [(c, ch) for c, ch in candidates(base, axes, levels, kmin, kmax, n, rng, include_new)
             if admissible(c, ch, avoid, min_dist, tabu, compatible, axes)]
    if not cands:
        return None
    if sample is None:
        c, ch = cands[int(rng.integers(len(cands)))]
        return c, ch, None
    ratings = sample([c for c, _ in cands])
    i = int(max(range(len(cands)), key=lambda j: ratings[j]))
    return cands[i][0], cands[i][1], float(ratings[i])


def choose_flip(sample, base, axes, levels, rng, tried=(), compatible=None, include_new=True):
    """The flip: one axis of `base` changed. (coord, change, rating) or None. `tried`: changes already flipped."""
    tried = set(tried)
    cands = [(c, ch) for c, ch in single_changes(base, axes, levels, include_new)
             if tuple(sorted(ch.items())) not in tried
             and (compatible is None or compatible({k: v for k, v in c.items() if not v.endswith("." + NEW)}))]
    if not cands:
        return None
    if sample is None:
        c, ch = cands[int(rng.integers(len(cands)))]
        return c, ch, None
    ratings = sample([c for c, _ in cands])
    i = int(max(range(len(cands)), key=lambda j: ratings[j]))
    return cands[i][0], cands[i][1], float(ratings[i])


def shared_axes(coords, axes):
    """Axes on which every given coordinate has the same known value: the frozen axes."""
    out = {}
    for a in axes:
        vals = {c.get(a) for c in coords}
        if len(vals) == 1 and None not in vals:
            out[a] = vals.pop()
    return out


def pairs_untried(coords, axes):
    """Pairs of axes whose value combinations seen so far are few: where interactions are unexplored."""
    seen = {}
    for c in coords:
        for a, b in combinations(axes, 2):
            if c.get(a) and c.get(b):
                seen.setdefault((a, b), set()).add((c[a], c[b]))
    return seen
