"""Tune a program's numbers: the LLM designs the structure, a cheap local search polishes the constants.

Each generation the search hands this the champion (and the best untuned newcomer). It finds the
program's numeric constants with `ast`, then runs a few rounds of random ±10-30% perturbations,
scored in parallel on the train split, keeping any improvement. Only the numbers change, never the
code around them, so a tuned program is the same idea with better weights.

  python -m helix.tune programs/tuned_params.py      try it on one program
"""
import ast
import math
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .sandbox import evaluate_code, evaluate_file

# Integers are tuned only where they act as a weight or an exponent; elsewhere they're usually indexes or shapes.
_INT_OPS = (ast.Mult, ast.Div, ast.Pow)


def constants(code):
    """The tunable numeric literals in a program: [(line, start_byte, end_byte, value)], in source order."""
    tree = ast.parse(code)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or isinstance(node.value, bool) or node.lineno != node.end_lineno:
            continue
        v = node.value
        if isinstance(v, float):
            if v == 0 or abs(v) < 1e-6 or not math.isfinite(v):
                continue           # zero can't be scaled; tiny values are division guards
        elif isinstance(v, int):
            parent = parents.get(node)
            if abs(v) < 2 or not (isinstance(parent, ast.BinOp) and isinstance(parent.op, _INT_OPS)):
                continue
        else:
            continue
        out.append((node.lineno, node.col_offset, node.end_col_offset, float(v)))
    return sorted(out)


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


def tune(code, base_score, evaluate_many, evals=48, batch=12, seconds=None, rng=None, sigma=0.25):
    """Local search over the constants of `code`. Returns a dict, or None if the program has no constants:
    {"code", "score", "result", "tried", "changes": [(old, new), ...]}; "code" is None if nothing beat the base."""
    rng = rng or random.Random()
    consts = constants(code)
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
