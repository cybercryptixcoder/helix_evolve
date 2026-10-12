"""Features: the unit the feature engine evolves.

A feature is one small function an agent writes:

    def feature(item, bins, capacity):
        '''What it measures, in one line.'''
        ...
        return values            # one number per row of `bins` (the last row is the new bin)

A policy is a weighted sum of features, and the weights are fitted by an optimiser (helix/fit.py), never
by an agent. `compose()` turns a library of features plus weights into an ordinary `priority()` program
that the unchanged evaluator scores: an empty library (or all-zero weights) gives every bin the same
score, which is Code Zero (first fit).

Every feature is normalised by a `scale` (1 / its typical spread, measured once) so that weights are
comparable and the optimiser can start every new feature at weight 0.
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import asdict, dataclass, field

ALLOWED_MODULES = {"numpy", "math"}


@dataclass
class Feature:
    id: str                         # f0001
    name: str                       # short_snake_case name
    code: str                       # source defining `feature(item, bins, capacity)`
    description: str = ""
    branch: str = "deep"            # deep | wide
    generation: int = 0
    hypothesis_id: str | None = None
    parent_ids: list = field(default_factory=list)   # features it varies or combines (wide)
    status: str = "candidate"       # candidate | active | rejected | redundant | retired | invalid
    columns: list = field(default_factory=lambda: ["value"])   # names of the values it returns per bin
    scales: list = field(default_factory=lambda: [1.0])        # 1 / typical spread of each column
    weights: list = field(default_factory=lambda: [0.0])       # current weights (on the scaled columns)
    error: str | None = None
    delta_train: float | None = None    # score gain when it was tried (train), after refitting the weights
    delta_valid: float | None = None    # the same on the validation instances: what decides acceptance
    importance: list | None = None      # per column: validation score lost when its weight is set to 0
    note: str = ""

    @property
    def width(self):
        return len(self.columns)

    def record(self):
        return asdict(self)


class FeatureError(ValueError):
    pass


# ---------------------------------------------------------------- reading an agent's feature code
def prepare(code, fid):
    """Check a feature's source and rename it for inclusion in a composed program.
    Returns (imports, body): import lines to hoist, and the renamed definitions. The main function becomes
    `_<fid>`; helpers and constants get a `_<fid>_` prefix so features never collide."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise FeatureError(f"syntax error: {exc}") from None
    imports, defs = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                if n.split(".")[0] not in ALLOWED_MODULES:
                    raise FeatureError(f"imports {n!r}; only numpy and math are allowed")
            imports.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.Assign, ast.AnnAssign)):
            defs.append(node)
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            continue                                   # a module docstring
        else:
            raise FeatureError(f"only imports, constants and functions are allowed at the top level "
                               f"(found {type(node).__name__} on line {node.lineno})")
    funcs = [d for d in defs if isinstance(d, ast.FunctionDef)]
    if not funcs:
        raise FeatureError("no function defined; write `def feature(item, bins, capacity):`")
    main = next((f for f in funcs if f.name == "feature"), funcs[-1])
    if len(main.args.args) != 3:
        raise FeatureError(f"`{main.name}` must take exactly (item, bins, capacity)")
    rename = {}
    for d in defs:
        targets = [d.name] if isinstance(d, ast.FunctionDef) else \
            [t.id for t in (d.targets if isinstance(d, ast.Assign) else [d.target]) if isinstance(t, ast.Name)]
        for name in targets:
            rename[name] = f"_{fid}" if d is main else f"_{fid}_{name}"

    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in rename:
                node.id = rename[node.id]
            return node

        def visit_FunctionDef(self, node):
            if node.name in rename:
                node.name = rename[node.name]
            self.generic_visit(node)
            return node

    new = ast.Module(body=[Renamer().visit(d) for d in defs], type_ignores=[])
    ast.fix_missing_locations(new)
    return [ast.unparse(i) for i in imports], ast.unparse(new)


def docstring(code):
    """The first line of the feature function's docstring (what it measures, in the author's words), or ""."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return ""
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    main = next((f for f in funcs if f.name == "feature"), funcs[-1] if funcs else None)
    doc = ast.get_docstring(main) if main else None
    return " ".join(doc.strip().splitlines()[0].split())[:300] if doc else ""


def code_hash(text):
    return hashlib.sha1(text.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- building a priority() program
HEADER = """# Helix feature policy{title}
# priority() = sum over features of (weight x scale) . feature(item, bins, capacity); the weights were fitted
# by an optimiser. With every weight at 0 all bins tie and the simulator picks the oldest bin that fits
# (first fit), so the empty policy is Code Zero.
import numpy as np
import math
"""

_PRIORITY = """

def priority(item, bins, capacity):
    for a in (item, bins, capacity):
        a.setflags(write=False)                    # features may read the inputs, never change them
    k = len(bins)
    total = np.zeros(k)
    for f, w in {terms}:
        if not w.any():
            continue
        v = np.asarray(f(item, bins, capacity), dtype=float)
        if v.ndim == 1:
            v = v[:, None]
        if v.shape[0] != k:
            v = np.broadcast_to(v.reshape(1, -1)[:, :len(w)], (k, len(w)))
        total += v @ w
    if not np.isfinite(total).all():
        total = np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3)
    # Bins that differ only by floating-point noise count as tied, so the oldest wins whatever the scale.
    return np.round(total, 9)
"""


def _pieces(features):
    imports, bodies = [], []
    for f in features:
        imp, body = prepare(f.code, f.id)
        imports += [i for i in imp if i not in imports and i not in ("import numpy as np", "import math")]
        doc = f"# {f.id} {f.name} ({f.branch}, {f.width} value{'s' if f.width > 1 else ''}): " \
              f"{' '.join((f.description or '').split())[:140]}"
        bodies.append(f"{doc}\n{body}")
    return imports, bodies


def effective_weights(f, weights=None):
    """weight x scale for each column of a feature."""
    w = f.weights if weights is None else weights
    return [float(a) * float(b) for a, b in zip(w, f.scales)]


def compose(features, weights=None, title=""):
    """A complete priority() program from features and their weights (default: each feature's .weights,
    or `weights` = one list per feature). Features whose weights are all 0 are left out."""
    weights = [f.weights for f in features] if weights is None else weights
    keep = [(f, w) for f, w in zip(features, weights) if any(float(x) != 0.0 for x in w)]
    imports, bodies = _pieces([f for f, _ in keep])
    terms = ", ".join(f"(_{f.id}, np.array({effective_weights(f, w)!r}))" for f, w in keep)
    return (HEADER.format(title=f" | {title}" if title else "") + "\n".join(imports) + "\n\n\n"
            + "\n\n\n".join(bodies) + f"\n\n_TERMS = [{terms}]\n" + _PRIORITY.format(terms="_TERMS"))


def module_source(features):
    """Source for fitting: every feature defined, weights read from `_W` (one array per feature) at call
    time, so one compiled module serves every weight vector the optimiser tries."""
    imports, bodies = _pieces(features)
    names = ", ".join(f"_{f.id}" for f in features)
    return ("import numpy as np\nimport math\n" + "\n".join(imports) + "\n\n" + "\n\n".join(bodies)
            + f"\n\n_FUNCS = [{names}]\n_W = []                 # set by the fitter before every run\n"
            + _PRIORITY.format(terms="zip(_FUNCS, _W)"))


def flat(features):
    """[(feature index, column index)] in the order of the optimiser's weight vector."""
    return [(i, j) for i, f in enumerate(features) for j in range(f.width)]


def split_vector(features, x):
    """Optimiser vector -> one list of weights per feature."""
    out, k = [], 0
    for f in features:
        out.append([float(v) for v in x[k:k + f.width]])
        k += f.width
    return out


def join_vector(features):
    return [w for f in features for w in f.weights]
