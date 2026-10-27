"""Keeping the design map small and readable (docs/V9_DESIGN.md, "Keeping the map tidy").

The first live replay on v8's archive showed what happens without it: the model names the same decision and the same
option in new words every time, and word matching can't tell paraphrases apart, so 386 readings grew the codebook to
874 decisions, one of them with 296 options. Two readings of a program then picked different paraphrases of the same
option, and agreement fell to 55-80%. Three remedies, shared by the replay and the run:

- **consolidate** (one call): decisions that are the same in other words are merged, down to `max_axes`;
- **tidy** (one call per crowded decision): its options are grouped into at most `max_values` distinct choices,
  each with a short name; the most used option of a group survives under that name, the others become its aliases,
  so every reading made before still resolves;
- **prune**: decisions found by reading programs that, after a while, fewer than `min_support` programs make are
  dropped from the map (they were one program's detail, not a decision of the search).

`call(role, system, user, temperature, max_tokens) -> text` is any model call (the replay's, or the run's).
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from helix4 import prompts as P4
from helix9 import prompts as P
from helix9.codebook import consolidate, regroup


def uses_of(cb, coords):
    """How many programs use each (current) option: coords is {pid: coord} or {pid: {"coord": coord}}."""
    n = Counter()
    for c in coords.values():
        c = c.get("coord", c) if isinstance(c, dict) and "coord" in c else c
        for v in cb.canonical(c or {}).values():
            n[v] += 1
    return n


def support_of(cb, coords):
    n = Counter()
    for c in coords.values():
        c = c.get("coord", c) if isinstance(c, dict) and "coord" in c else c
        for a in cb.canonical(c or {}):
            n[a] += 1
    return n


def consolidate_axes(cb, call, max_axes, gen=None, rounds=3, force=False, log=print):
    """Merges decisions that are the same in other words: while there are more than `max_axes`, or once when `force`
    (decisions found since the last check may repeat old ones in other words, below the cap too)."""
    done = 0
    for i in range(rounds):
        n = len(cb.active_axes())
        if n <= max_axes and not (force and i == 0):
            break
        text = call("cartographer", P.MATCH_SYSTEM, P.CONSOLIDATE_ASK.format(axes=cb.text(max_values=3),
                                                                             k=min(n, max_axes)), 0.2, 3000)
        merged = consolidate(cb, P4.extract_json(text) or {}, gen)
        done += len(merged)
        if not merged:
            break
    if done:
        log(f"   consolidated: {done} decisions merged, {len(cb.active_axes())} left")
    return done


def tidy(cb, call, uses=None, max_values=6, gen=None, limit=None, workers=4, log=print):
    """Groups the options of every decision with more than `max_values` (the most crowded first, at most `limit`)."""
    uses = uses or {}
    crowded = sorted((a for a in cb.active_axes() if len(cb.values(a)) > max_values),
                     key=lambda a: -len(cb.values(a)))[:limit]
    if not crowded:
        return 0

    def ask(a):
        ax = cb.axes[a]
        opts = "\n".join(f"{v}: {ax['values'][v]['name']} ({uses.get(v, 0)} programs)" for v in cb.values(a))
        return call("cartographer", P.MATCH_SYSTEM,
                    P.TIDY_ASK.format(axis=f"{a}: {ax.get('question') or ax['name']}", options=opts, k=max_values),
                    0.2, 4000)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        texts = list(ex.map(ask, crowded))
    merged = 0
    for a, text in zip(crowded, texts):
        before = len(cb.values(a))
        merged += regroup(cb, a, P4.extract_json(text) or {}, gen, uses)
        log(f"   tidied {a}: {before} options -> {len(cb.values(a))}")
    return merged


def prune(cb, coords, min_support=3, gen=None, min_age=0, sources=("annotator", "replay-reading", "discovery"),
          log=print):
    """Drops decisions found by reading programs that fewer than `min_support` programs make (once they are at least
    `min_age` generations old)."""
    sup = support_of(cb, coords)
    dropped = []
    for a in cb.active_axes():
        ax = cb.axes[a]
        young = gen is not None and ax.get("born") is not None and gen - ax["born"] < min_age
        if ax.get("source") in sources and not young and sup.get(a, 0) < min_support:
            ax["status"] = "dropped"
            cb.log.append([gen, "drop-axis", a, f"{sup.get(a, 0)} programs", ""])
            dropped.append(a)
    if dropped:
        log(f"   dropped {len(dropped)} decisions that fewer than {min_support} programs make")
    return dropped
