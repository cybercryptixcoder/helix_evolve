"""Tune a program's numbers: the LLM designs the structure, a cheap local search polishes the constants.

Each generation the search hands this the champion (and the best untuned newcomer). It finds the
program's numeric constants with `ast`, then runs a few rounds of random ±10-30% perturbations,
scored in parallel on the train split, keeping any improvement. Only the numbers change, never the
code around them, so a tuned program is the same idea with better weights.

  python -m helix.tune programs/tuned_params.py      try it on one program
"""
import ast
import difflib
import math
import random
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .sandbox import evaluate_code, evaluate_file

# Integers are tuned only where they act as a weight or an exponent; elsewhere they're usually indexes or shapes.
_INT_OPS = (ast.Mult, ast.Div, ast.Pow)


def constants(code, lines=None):
    """The tunable numeric literals in a program: [(line, start_byte, end_byte, value)], in source order.

    Tunable means a coefficient: a number in arithmetic (`0.35 * comp`, `x ** 2`), a threshold in a
    comparison (`left <= 0.15`), or a named constant (`W = 0.3`, `A, B = 0.2, 1.9`). Numbers passed to a
    function (`np.minimum(x, 1.0)`, `np.maximum(cap, 1e-9)`, `axis=1`) are bounds and guards, not weights,
    and are left alone, as are zero and tiny values. `lines` restricts the search to those line numbers."""
    tree = ast.parse(code)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or isinstance(node.value, bool) or node.lineno != node.end_lineno:
            continue
        if lines is not None and node.lineno not in lines:
            continue
        v = node.value
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v == 0 or abs(v) < 1e-6:
            continue               # zero can't be scaled; tiny values are division guards
        parent = parents.get(node)
        while isinstance(parent, ast.UnaryOp):          # -0.35 is the constant 0.35 under a minus sign
            parent = parents.get(parent)
        if isinstance(v, int):
            if abs(v) < 2 or not (isinstance(parent, ast.BinOp) and isinstance(parent.op, _INT_OPS)):
                continue
        elif not _is_coefficient(parent, parents):
            continue
        out.append((node.lineno, node.col_offset, node.end_col_offset, float(v)))
    return sorted(out)


def _is_coefficient(parent, parents):
    if isinstance(parent, (ast.BinOp, ast.Compare)):
        return True
    if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return True
    if isinstance(parent, (ast.Tuple, ast.List)):                # A, B = 0.2, 1.9
        return isinstance(parents.get(parent), (ast.Assign, ast.AnnAssign))
    return False


def changed_lines(old, new):
    """Line numbers (1-based) of `new` that were added or changed relative to `old`."""
    return {line for line, _ in _changes(old, new)}


def new_constants(old, new):
    """The constants of `new` that `old` didn't have: those on added lines, and those on changed lines whose
    value isn't among the numbers of the lines they replaced. Numbers carried over unchanged stay out, so
    tuning a test's new part doesn't quietly retune the rest of its base program."""
    changes = _changes(old, new)
    old_consts, new_consts = constants(old), constants(new, {line for line, _ in changes})
    out = []
    # Changed lines come in blocks that replace a block of old lines; within a block, a number counts as
    # carried over as many times as the old block had it, and the surplus (the later copies) is new.
    blocks = {}
    for line, replaced in changes:
        blocks.setdefault(frozenset(replaced), []).append(line)
    for replaced, lines in blocks.items():
        left = Counter(o[3] for o in old_consts if o[0] in replaced)
        mine = [c for c in new_consts if c[0] in lines]
        keep = Counter(c[3] for c in mine)
        for value in keep:
            keep[value] = max(0, keep[value] - left[value])        # how many copies of this value are new
        for c in reversed(mine):
            if keep[c[3]] > 0:
                out.append(c)
                keep[c[3]] -= 1
    return sorted(out)


def _changes(old, new):
    """[(line in new, set of lines in old it replaced)] for every added or changed line of `new`."""
    a, b = old.splitlines(), new.splitlines()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [x.strip() for x in a], [x.strip() for x in b],
                                                       autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out += [(j, set(range(i1 + 1, i2 + 1))) for j in range(j1 + 1, j2 + 1)]
    return out


def substitute(code, consts, values):
    """The program with each constant replaced by its new value (offsets are UTF-8 bytes, as ast gives them)."""
    lines = code.splitlines(keepends=True)
    for (line, start, end, old), value in sorted(zip(consts, values), key=lambda t: (t[0][0], t[0][1]), reverse=True):
        if value == old:
            continue               # untouched constants keep their original text (an int stays an int)
        raw = lines[line - 1].encode()
        lines[line - 1] = (raw[:start] + repr(value).encode() + raw[end:]).decode()
    return "".join(lines)


def _perturb(value, sigma, rng):
    new = value * math.exp(rng.gauss(0, sigma))
    return float(f"{new:.4g}")


def tune(code, base_score, evaluate_many, evals=48, batch=12, seconds=None, rng=None, sigma=0.25, consts=None):
    """Local search over the constants of `code` (or just `consts`, a subset of `constants(code)`). Returns a
    dict, or None if there's nothing to tune: {"code", "score", "result", "tried", "changes": [(old, new), ...]};
    "code" is None if nothing beat `base_score`."""
    rng = rng or random.Random()
    consts = constants(code) if consts is None else list(consts)
    if not consts:
        return None
    start = [c[3] for c in consts]
    best_vals, best_score, best_result = list(start), base_score, None
    tried, deadline = 0, (time.time() + seconds) if seconds else None
    while tried < evals and not (deadline and time.time() > deadline):
        cands = []
        for _ in range(min(batch, evals - tried)):
            vals = list(best_vals)
            k = rng.choice([1, 1, 2, 2, 3, len(vals)])            # mostly a few constants at a time
            for i in rng.sample(range(len(vals)), min(k, len(vals))):
                vals[i] = _perturb(vals[i], sigma, rng)
            cands.append(vals)
        results = evaluate_many([substitute(code, consts, v) for v in cands])
        tried += len(cands)
        improved = False
        for vals, res in zip(cands, results):
            if res.get("valid") and res["score"] > best_score:
                best_vals, best_score, best_result, improved = vals, res["score"], res, True
        if not improved:
            sigma = max(0.05, sigma * 0.7)                        # nothing better nearby: look closer
    if best_result is None:
        return {"code": None, "score": base_score, "result": None, "tried": tried, "changes": []}
    changes = [(a, b) for a, b in zip(start, best_vals) if a != b]
    return {"code": substitute(code, consts, best_vals), "score": best_score, "result": best_result,
            "tried": tried, "changes": changes}


def evaluator(split="train", timeout=60.0, workers=4):
    """A function that scores a list of programs in parallel, each in its own temporary file."""
    pool = ThreadPoolExecutor(max_workers=workers)

    def evaluate_many(codes):
        with tempfile.TemporaryDirectory(prefix="helix-tune-") as tmp:
            paths = [Path(tmp) / f"t{i}.py" for i in range(len(codes))]
            return list(pool.map(lambda cp: evaluate_code(cp[0], cp[1], split, timeout), zip(codes, paths)))
    return evaluate_many


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("programs/tuned_params.py")
    src = path.read_text()
    base = evaluate_file(path, "train")
    print(f"{path}: {len(constants(src))} constants, train score {base['score']:.3f}")
    t = time.time()
    out = tune(src, base["score"], evaluator(), evals=48, rng=random.Random(0))
    if out is None or out["code"] is None:
        print(f"no improvement after {out['tried'] if out else 0} tries ({time.time() - t:.0f}s)")
    else:
        print(f"tuned to {out['score']:.3f} after {out['tried']} tries ({time.time() - t:.0f}s): "
              + ", ".join(f"{a:g}→{b:g}" for a, b in out["changes"]))
