"""Features and policies: compiling agent code safely, composing a weighted sum, and writing it out.

A feature is code that defines `feature(*args)` returning one number per candidate (shape (k,)) or a few
columns (shape (k, c)). It runs with the evaluator's restricted builtins: only numpy and math import.
A policy is a list of (feature code, column weights); priority = sum over features of values @ weights,
rounded to 9 decimals so floating-point noise never breaks the "first candidate wins" tie rule.
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
_COMPILED = {}


class FeatureError(ValueError):
    pass


def safe_builtins():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from evaluator.evaluate import _SAFE_BUILTINS
    return _SAFE_BUILTINS


def code_hash(code):
    return hashlib.sha1(code.encode()).hexdigest()[:16]


def check_source(code, func="feature"):
    """Static checks: parses, defines `func`, imports only numpy/math, no dunder access."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise FeatureError(f"syntax error: {e}")
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if func not in names:
        raise FeatureError(f"no function defined; write `def {func}(...)`")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for m in mods:
                if m.split(".")[0] not in ("numpy", "math"):
                    raise FeatureError(f"import of '{m}' is not allowed: only numpy and math")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise FeatureError("dunder attributes are not allowed")
        if isinstance(node, ast.Name) and node.id in ("eval", "exec", "open", "compile", "globals", "locals"):
            raise FeatureError(f"'{node.id}' is not allowed")


def compile_feature(code, func="feature"):
    key = (code_hash(code), func)
    fn = _COMPILED.get(key)
    if fn is None:
        check_source(code, func)
        ns = {"__name__": "helix_feature", "__builtins__": safe_builtins()}
        try:
            exec(compile(code, "<feature>", "exec"), ns)
        except Exception as e:
            raise FeatureError(f"{type(e).__name__} while loading: {e}")
        fn = ns[func]
        if len(_COMPILED) > 400:
            _COMPILED.clear()
        _COMPILED[key] = fn
    return fn


def _readonly(args):
    """Read-only views of the array arguments: no copy, and a feature can't change the simulator's state."""
    out = []
    for a in args:
        if isinstance(a, np.ndarray):
            a = a.view()
            a.flags.writeable = False
        out.append(a)
    return out


def call_feature(fn, args, k, ro=None):
    """Run a feature on one decision; returns a (k, c) float array (always its own memory) or raises FeatureError.

    Arrays are passed as read-only views. A feature that writes into its inputs gets private copies instead
    (detected once, then remembered on the function)."""
    if getattr(fn, "_helix_copy", False):
        raw = fn(*[a.copy() if hasattr(a, "copy") else a for a in args])
    else:
        try:
            raw = fn(*(ro if ro is not None else _readonly(args)))
        except ValueError as e:
            if "read-only" not in str(e):
                raise
            fn._helix_copy = True
            raw = fn(*[a.copy() if hasattr(a, "copy") else a for a in args])
    v = np.array(raw, dtype=float)
    if v.ndim == 0:
        v = np.full((k, 1), float(v))
    elif v.ndim == 1:
        if v.shape[0] != k:
            raise FeatureError(f"returned shape {v.shape} for {k} candidates; return one value per candidate")
        v = v[:, None]
    elif v.ndim == 2:
        if v.shape[0] != k:
            raise FeatureError(f"returned shape {v.shape} for {k} candidates; the first axis must be the candidates")
    else:
        raise FeatureError(f"returned a {v.ndim}-d array; return shape (k,) or (k, c)")
    if not np.isfinite(v).all():
        v = np.nan_to_num(v, nan=0.0, posinf=1e3, neginf=-1e3)
    return v


def _sketch(args):
    """A cheap fingerprint of a decision's arguments (shapes, scalars, a strided sample of each array)."""
    parts = []
    for a in args:
        if isinstance(a, np.ndarray):
            flat = a.reshape(-1)
            parts.append((a.shape, flat[:: max(1, flat.size // 24)].tobytes()))
        else:
            parts.append(a if isinstance(a, (int, float, str)) else repr(a))
    return hash(tuple(parts))


class ValueCache:
    """Feature values per (feature, decision state), shared by every simulation in one worker process.

    The state key is a hash chain: the instance, then every choice made so far. Policies that made the same
    choices are in the same state (the simulator is deterministic and takes the argmax), so a weight vector
    near the champion's reuses the champion's feature values until its trajectory diverges. A sketch of the
    arguments is mixed in as a guard. Bounded by bytes; the oldest half is dropped when full."""

    def __init__(self, max_mb=256):
        self.max_bytes = int(max_mb * 2 ** 20)
        self.d, self.bytes, self.hits, self.misses = {}, 0, 0, 0

    def get(self, key):
        v = self.d.get(key)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def put(self, key, v):
        self.d[key] = v
        self.bytes += v.nbytes + 120
        if self.bytes > self.max_bytes:
            drop = list(self.d)[: len(self.d) // 2]
            for k2 in drop:
                self.bytes -= self.d.pop(k2).nbytes + 120

    def clear(self):
        self.d.clear()
        self.bytes = 0


def make_priority(feature_codes, weights, n_candidates, cache=None, tag=None):
    """priority(*args) for a list of feature codes and per-feature column weight arrays (already scaled).

    With a ValueCache and a tag naming the instance, feature values are reused across simulations."""
    fns = [compile_feature(c) for c in feature_codes]
    ws = [np.asarray(w, dtype=float) for w in weights]
    active = [(fn, w, hash(c)) for fn, w, c in zip(fns, ws, feature_codes) if w.any()]
    chain = [hash(tag)]

    def priority(*args):
        k = n_candidates(args)
        total = np.zeros(k)
        ro = None
        sk = hash((chain[0], k, _sketch(args))) if cache is not None else None
        for fn, w, fk in active:
            v = cache.get((fk, sk)) if cache is not None else None
            if v is None:
                if ro is None:
                    ro = _readonly(args)
                v = call_feature(fn, args, k, ro)
                if cache is not None:
                    cache.put((fk, sk), v)
            c = min(v.shape[1], len(w))
            total += v[:, :c] @ w[:c]
        total = np.round(total, 9)
        if cache is not None:
            chain[0] = hash((sk, int(np.argmax(total))))
        return total

    return priority


def docstring(code):
    try:
        for node in ast.parse(code).body:
            if isinstance(node, ast.FunctionDef):
                return (ast.get_docstring(node) or "").strip().split("\n")[0]
    except SyntaxError:
        pass
    return ""


def extract_code(text, func="feature"):
    """The python code block that defines `func` from a model reply."""
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    for b in blocks:
        if f"def {func}" in b:
            return b.strip() + "\n"
    for b in blocks:                                       # one function under another name: rename it
        names = re.findall(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(", b, re.M)
        if len(names) == 1:
            return re.sub(rf"\b{names[0]}\(", f"{func}(", b.strip(), count=1) + "\n"
    if f"def {func}" in (text or ""):                      # unfenced reply
        start = text.index("import") if "import" in text else text.index(f"def {func}")
        return text[start:].split("\n```")[0].strip() + "\n"
    return None


def compose(problem, features, title=""):
    """The policy written out as an ordinary standalone program: `priority(<args>)`."""
    args = problem.signature[problem.signature.index("(") + 1:problem.signature.index(")")]
    parts = [f"# Helix v3 policy{': ' + title if title else ''}",
             "# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).",
             "import numpy as np", "import math", ""]
    terms = []
    for f in features:
        body = re.sub(r"^\s*import (numpy as np|math)\s*$", "", f.code, flags=re.M).strip()
        body = body.replace("def feature(", f"def _{f.id}(", 1)
        parts += [f"# {f.id} {f.name} ({f.origin}): {f.measures[:110]}", body, ""]
        terms.append(f"(_{f.id}, np.array({[round(float(x), 6) for x in f.effective_weights()]}))")
    parts += [f"_TERMS = [{', '.join(terms)}]", "",
              f"def priority({args}):",
              "    k = None",
              "    total = None",
              "    for f, w in _TERMS:",
              f"        v = np.asarray(f({args}), dtype=float)",
              "        v = v[:, None] if v.ndim == 1 else v",
              "        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]",
              "    if total is None:",
              f"        return np.zeros(len({args.split(',')[problem.candidates_arg].strip()}))",
              "    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)", ""]
    return "\n".join(parts)
