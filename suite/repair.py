"""Repair (open suite): evolve a debugger. Which single-edit patch should be tried next on a buggy program?

Seven small invented calculation programs: a tariff and a parcel-fee calculator (`billing`), a fence quote over a
polygon and a level-crossing routine over a polyline (`geometry`), a cart and an inventory simulator (`simulation`),
and a checksum routine with three schemes, kept for the held-out family (`encoding`). Each correct program generates
its own test suite (32 seeded inputs and their expected outputs). An instance is one program with 2-4 seeded bugs
(operator swap, off-by-one, wrong variable, changed constant, negated condition, swapped arguments), each failing
10-60% of the tests on its own, chosen so that undoing them one at a time in some order is kept at every step.

One decision: the candidates are all single-edit patches of the program's current state (every mutation operator at
every applicable syntax node) not yet tried in that state. The engine applies the chosen patch and keeps it only if
no passing test breaks and either fewer tests fail or the total numeric error at least halves; otherwise it reverts.
After a kept patch the program has changed, so every patch of the new state is a candidate again.

Cost: patches tried until every test passes, or B + 20 x failing tests + total numeric error (< 1 per failing test)
when the budget of B tries (or the candidates) runs out. Open ceiling (docs/OPEN_SUITE.md): gap = 100 x cost / Code
Zero's cost on the same instance. Bug sets on which Code Zero repairs everything within the budget are redrawn (so its
cost is always a budget-exhausted cost, a stable denominator). The instances and Code Zero's costs are cached in
suite/data/repair_cz.json (rebuild: `python -m suite.repair --cz`, ~5 s); a missing or stale entry is regenerated
on the spot (same result).

Programs run with a step guard: every loop iteration counts, and a run stops (status "halted") after 2000 iterations
or when the values carried through a loop leave +-1e12, so a buggy loop can neither hang nor blow up (no signals,
so it also works in threads). Test results are memoised per (program state, patch) in each process, so repeated
evaluations of an instance are cheap; a lock serialises the in-place patching of the cached syntax trees.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import random
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
CZ_FILE = ROOT / "suite" / "data" / "repair_cz.json"
VERSION = 6                     # bump when programs, tests, operators or the budget change (invalidates the cache)
SPLIT_SEED = {"train": 7411, "valid": 7522, "test": 7633}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
TRAIN_FAMILIES = ["billing", "geometry", "simulation"]
HELD_OUT = ["encoding"]
CODES = {"billing": 1, "geometry": 2, "simulation": 3, "encoding": 4}
BUDGET = 250                    # patch tries per instance
FAIL_PENALTY = 20.0             # cost per test still failing when the budget runs out
N_TESTS = 32
KEEP_ERR = 0.5                  # an error-only improvement must cut the total error to at most this share
VAR_WINDOW = 3                  # a variable swap uses a variable read or written within this many lines
STEP_CAP = 2000                 # loop iterations per test run
VALUE_CAP = 1e12                # values carried through a loop must stay inside +-VALUE_CAP
TOL = 1e-9                      # a test passes when its relative error is at most this

# ---------------------------------------------------------------------------------------------- programs
TARIFF = """
def tariff(usage, plan, months, solar):
    total = 0.0
    peak = 0.0
    for h in range(len(usage)):
        total = total + usage[h]
        if h >= 8 and h < 11:
            peak = peak + usage[h]
    net = total - solar
    credit = 0.0
    if net < 0:
        credit = -net * 0.04
        net = 0.0
    if plan == 0:
        charge = net * 0.21 + 4.0
    elif plan == 1:
        charge = 0.0
        block = 0
        remaining = net
        while remaining > 0:
            size = 10.0 + 5.0 * block
            used = min(remaining, size)
            charge = charge + used * (0.11 + 0.03 * block)
            remaining = remaining - used
            block = block + 1
    else:
        off = net - peak
        if off < 0:
            off = 0.0
        charge = off * 0.12 + min(peak, net) * 0.34
    if months >= 24:
        charge = charge * 0.92
    elif months >= 12:
        charge = charge * 0.96
    return max(charge - credit, 2.5)
"""

PARCEL = """
def parcel(weight, length, width, height, zone, service, count):
    vol = length * width * height / 5000.0
    billable = max(weight, vol)
    if billable <= 0.5:
        base = 3.2
    elif billable <= 2.0:
        base = 4.5 + (billable - 0.5) * 1.8
    else:
        base = 7.2 + (billable - 2.0) * 1.1
    if service == 0:
        fee = base * 0.8
        if zone > 3:
            fee = fee + 1.5
    elif service == 1:
        fee = base
        z = 1
        while z < zone:
            fee = fee + 0.6
            z = z + 1
    else:
        fee = base * (1.5 + 0.1 * zone)
        if length > 60:
            fee = fee + (length - 60) * 0.05
    total = 0.0
    for i in range(count):
        if i < 3:
            total = total + fee
        else:
            total = total + fee * 0.85
    if total > 100:
        total = 100 + (total - 100) / 2
    return total
"""

FENCE = """
def fence(xs, ys, gap):
    n = len(xs)
    area2 = 0.0
    cost = 0.0
    gates = 0
    for i in range(n):
        j = (i + 1) % n
        area2 = area2 + xs[i] * ys[j] - xs[j] * ys[i]
        dx = abs(xs[j] - xs[i])
        dy = abs(ys[j] - ys[i])
        d = sqrt(dx * dx + dy * dy)
        if dy > 2 * dx:
            rate = 19.0
        elif dx > 2 * dy:
            rate = 11.5
        else:
            rate = 14.0
        cost = cost + d * rate + (int(d // gap) + 1) * 8.0
        if d > 12 and gates < 2:
            gates = gates + 1
            cost = cost + 45.0
    area = abs(area2) / 2
    if area > 300:
        cost = cost - (area - 300) * 0.1
    return cost
"""

LEVELS = """
def levels(xs, ys, h):
    crossings = 0
    touches = 0
    first = -1.0
    width = 0.0
    for i in range(len(xs) - 1):
        a = ys[i] - h
        b = ys[i + 1] - h
        if a == 0 or b == 0:
            touches = touches + 1
        elif a * b < 0:
            x = xs[i] + (xs[i + 1] - xs[i]) * a / (a - b)
            if crossings == 0:
                first = x
            else:
                width = x - first
            crossings = crossings + 1
    if crossings == 0:
        return (touches, -1.0, 0.0)
    return (crossings + touches, first, width)
"""

CART = """
def cart(kinds, lengths, speed, mass):
    energy = 0.5 * mass * speed * speed
    dist = 0.0
    done = 0
    boosts = 0
    for i in range(len(kinds)):
        k = kinds[i]
        seg = lengths[i]
        if k == 0:
            loss = 0.3 * mass * seg
        elif k == 1:
            loss = 1.8 * mass * seg
        elif k == 2:
            loss = -0.9 * mass * seg
        else:
            loss = 0.05 * mass * seg
            if energy > 120:
                loss = loss + 0.01 * energy
        if loss >= energy:
            dist = dist + seg * energy / loss
            energy = 0.0
            break
        energy = energy - loss
        dist = dist + seg
        done = done + 1
        if energy < 40 and boosts < 1:
            energy = energy + 60
            boosts = boosts + 1
    return (dist, done)
"""

INVENTORY = """
def inventory(demand, start, level, qty, lead, policy):
    stock = start
    due = -1
    lost = 0
    holding = 0.0
    orders = 0
    for day in range(len(demand)):
        if day == due:
            stock = stock + qty
            due = -1
        want = demand[day]
        if want > stock:
            lost = lost + (want - stock)
            stock = 0
        else:
            stock = stock - want
        if stock > 50:
            holding = holding + 10.0 + (stock - 50) * 0.35
        else:
            holding = holding + stock * 0.2
        if due < 0:
            if policy == 0 and stock <= level:
                due = day + lead
                orders = orders + 1
            elif policy == 1 and day % 7 == 6:
                due = day + lead
                orders = orders + 1
    return lost * 4.0 + holding + orders * 12.0
"""

CHECKSUM = """
def checksum(digits, scheme):
    total = 0
    if scheme == 0:
        w = 3
        for d in digits:
            total = total + d * w
            w = w - 1
            if w < 1:
                w = 4
        r = total % 13
        if r < 5:
            return r
        return 13 - r
    if scheme == 1:
        for i in range(len(digits)):
            v = digits[i]
            if i % 3 == 2:
                v = v * 2
                if v > 9:
                    v = v - 7
            total = total + v
        return (10 - total % 10) % 10
    runs = 0
    prev = -1
    for d in digits:
        if d != prev:
            runs = runs + 1
            prev = d
        total = (total * 3 + d + runs) % 101
    return total + runs
"""


def _gen_tariff(r):
    scale = r.choice([0.5, 1.0, 2.0])
    usage = [round(r.uniform(0.0, 6.0) * scale, 2) for _ in range(12)]
    solar = round(r.uniform(0.0, 30.0), 1) if r.random() < 0.6 else round(r.uniform(30.0, 80.0), 1)
    return (usage, r.randint(0, 2), r.choice([r.randint(0, 11), r.randint(12, 23), r.randint(24, 48)]), solar)


def _gen_parcel(r):
    size = r.randint(0, 2)
    if size == 0:
        w, dims = round(r.uniform(0.1, 0.7), 2), [r.randint(5, 15) for _ in range(3)]
    elif size == 1:
        w, dims = round(r.uniform(0.3, 3.0), 2), [r.randint(10, 30), r.randint(10, 25), r.randint(5, 15)]
    else:
        w, dims = round(r.uniform(2.0, 25.0), 2), [r.randint(20, 90), r.randint(10, 50), r.randint(5, 40)]
    return (w, *dims, r.randint(1, 6), r.randint(0, 2), r.choice([1, 2, 3, 4, 6, 8]))


def _gen_fence(r):
    shape = r.randint(0, 2)
    if shape == 0:                                              # an axis-aligned rectangle
        x0, y0 = r.randint(-10, 0), r.randint(-10, 0)
        w, h = r.randint(2, 25), r.randint(2, 25)
        xs, ys = [x0, x0 + w, x0 + w, x0], [y0, y0, y0 + h, y0 + h]
    else:                                                       # a star-shaped polygon
        n = r.randint(3, 5) if shape == 1 else r.randint(6, 9)
        rad = r.uniform(3.0, 16.0)
        ang = sorted(r.uniform(0.0, 2 * math.pi) for _ in range(n))
        xs = [round(rad * r.uniform(0.6, 1.3) * math.cos(a), 1) for a in ang]
        ys = [round(rad * r.uniform(0.6, 1.3) * math.sin(a), 1) for a in ang]
    return (xs, ys, round(r.uniform(1.5, 4.0), 1))


def _gen_levels(r):
    n = r.randint(3, 10)
    xs = [0]
    for _ in range(n - 1):
        xs.append(xs[-1] + r.randint(1, 3))
    lo, hi = sorted((r.randint(0, 8), r.randint(0, 8)))
    ys = [r.randint(lo, hi + 1) for _ in range(n)]
    return (xs, ys, r.randint(lo, hi + 1) if r.random() < 0.85 else r.randint(0, 9))


def _gen_cart(r):
    n = r.randint(4, 11)
    mix = r.choice([(0, 2, 3), (0, 1, 2), (0, 1, 2, 3), (1, 3), (0, 1, 1, 3), (1, 1, 2)])
    return ([r.choice(mix) for _ in range(n)], [r.randint(1, 10) for _ in range(n)], r.randint(3, 12), r.randint(1, 5))


def _gen_inventory(r):
    days = r.randint(8, 18)
    hi = r.choice([6, 12, 20])
    return ([r.randint(0, hi) for _ in range(days)], r.randint(10, 70), r.randint(5, 30), r.randint(15, 60),
            r.randint(1, 5), r.randint(0, 1))


def _gen_checksum(r):
    return ([r.randint(0, 9) for _ in range(r.randint(5, 14))], r.randint(0, 2))


PROGRAMS = {
    "tariff": {"family": "billing", "src": TARIFF, "lists": ("usage",), "gen": _gen_tariff, "seed": 101},
    "parcel": {"family": "billing", "src": PARCEL, "lists": (), "gen": _gen_parcel, "seed": 102},
    "fence": {"family": "geometry", "src": FENCE, "lists": ("xs", "ys"), "gen": _gen_fence, "seed": 201},
    "levels": {"family": "geometry", "src": LEVELS, "lists": ("xs", "ys"), "gen": _gen_levels, "seed": 202},
    "cart": {"family": "simulation", "src": CART, "lists": ("kinds", "lengths"), "gen": _gen_cart, "seed": 301},
    "inventory": {"family": "simulation", "src": INVENTORY, "lists": ("demand",), "gen": _gen_inventory, "seed": 302},
    "checksum": {"family": "encoding", "src": CHECKSUM, "lists": ("digits",), "gen": _gen_checksum, "seed": 401},
}
FAMILY_PROGRAMS = {f: [p for p, s in PROGRAMS.items() if s["family"] == f] for f in CODES}


class _Halt(Exception):
    """The step guard stopped a run (too many loop iterations, or a carried value ran away)."""


BASE_GLOBALS = {"__builtins__": {}, "len": len, "range": range, "min": min, "max": max, "abs": abs, "int": int,
                "float": float, "round": round, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "_Halt": _Halt}

# ---------------------------------------------------------------------------------------------- mutation operators
K_OP, K_CMP, K_ONE, K_TWO, K_TEN, K_VAR, K_NEG, K_SWAP, K_SHIFT = range(9)
KIND_NAMES = ["operator", "comparison", "constant+-1", "constant*/2", "constant*/10", "variable", "negate", "swap",
              "shift"]
ARITH = {ast.Add: (ast.Sub,), ast.Sub: (ast.Add,), ast.Mult: (ast.Div,), ast.Div: (ast.Mult, ast.FloorDiv),
         ast.FloorDiv: (ast.Div, ast.Mod), ast.Mod: (ast.FloorDiv,)}
CMP = {ast.Lt: (ast.LtE, ast.Gt), ast.LtE: (ast.Lt, ast.GtE), ast.Gt: (ast.Lt, ast.GtE), ast.GtE: (ast.LtE, ast.Gt),
       ast.Eq: (ast.NotEq,), ast.NotEq: (ast.Eq,)}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}
NONCOMM = (ast.Sub, ast.Div, ast.FloorDiv, ast.Mod)
COMMUTATIVE_CALLS = ("min", "max")
STATUS = ["pass", "wrong value", "ZeroDivisionError", "IndexError", "TypeError", "other exception", "halted"]


def _num(v):
    return float(f"{v:.12g}") if isinstance(v, float) else v


def _const_moves(v):
    """(kind, description, new value) for a numeric constant: integers +-1, x2 and /2 (when even); floats x2, /2,
    x10 and /10. Every move has its inverse among the moves of the result."""
    if isinstance(v, int):
        out = [(K_ONE, "+1", v + 1), (K_ONE, "-1", v - 1), (K_TWO, "*2", v * 2)]
        if v % 2 == 0:
            out.append((K_TWO, "/2", v // 2))
    else:
        out = [(K_TWO, "*2", v * 2), (K_TWO, "/2", v / 2), (K_TEN, "*10", v * 10), (K_TEN, "/10", v / 10)]
    return [(k, d, _num(n)) for k, d, n in out if _num(n) != v]


def _loc(new, old):
    ast.copy_location(new, old)
    ast.fix_missing_locations(new)
    return new


def _plus(e, op):
    return _loc(ast.BinOp(left=e, op=op(), right=ast.Constant(value=1)), e)


def patches(fn, lists):
    """Every single-edit patch of a function's AST, in a deterministic order.

    A patch is (kind, line, col, depth, description, edits, target node, invertible); edits = [(object, attribute or
    list index, new value)]; invertible: its inverse edit is a candidate of the patched program (may hold a bug). Patches are applied in place and reverted, so they hold references into this very tree."""
    params = [a.arg for a in fn.args.args]
    stores = []                                     # (line, name) of every assignment
    loops = []                                      # (first line, last line) of every loop
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores.append((node.lineno, node.id))
        if isinstance(node, (ast.For, ast.While)):
            loops.append((node.lineno, node.end_lineno))
    lists = set(lists)
    out = []

    def place_vars(node):
        """The variables a read at `node` may be swapped with: same type, assigned inside a loop enclosing the read
        or on an earlier line within VAR_WINDOW lines (parameters are never swapped). Assignments are never edited,
        so the set depends only on the place: a swap's inverse is always a candidate when the name it replaced is in
        the set (only such reads can hold a variable bug)."""
        line = node.lineno
        spans = [(a, b) for a, b in loops if a <= line <= b]
        out = set()
        for ln, nm in stores:
            if any(a <= ln <= b for a, b in spans) or line - VAR_WINDOW <= ln < line:
                out.add(nm)
        return {v for v in out if (v in lists) == (node.id in lists)}

    def add(kind, node, depth, desc, edits, invertible=True):
        out.append((kind, node.lineno, node.col_offset, depth, desc, edits, node, invertible))

    def visit(node, depth, parent):
        t = type(node)
        if t is ast.BinOp:
            for new in ARITH.get(type(node.op), ()):
                add(K_OP, node, depth, new.__name__, [(node, "op", new())])
            if isinstance(node.op, NONCOMM):
                add(K_SWAP, node, depth, "swap", [(node, "left", node.right), (node, "right", node.left)])
        elif t is ast.Compare and len(node.ops) == 1:
            for new in CMP.get(type(node.ops[0]), ()):
                add(K_CMP, node, depth, new.__name__, [(node.ops, 0, new())])
        elif t is ast.BoolOp:
            new = BOOL[type(node.op)]
            add(K_CMP, node, depth, new.__name__, [(node, "op", new())])
        elif t is ast.Constant and type(node.value) in (int, float):
            for kind, desc, v in _const_moves(node.value):
                add(kind, node, depth, desc, [(node, "value", v)])
        elif t is ast.Name and isinstance(node.ctx, ast.Load) and not (type(parent) is ast.Call and parent.func is node):
            pv = place_vars(node) - set(params)
            if node.id not in params:
                for v in sorted(pv - {node.id}):
                    add(K_VAR, node, depth, v, [(node, "id", v)], node.id in pv)
        if t in (ast.If, ast.While, ast.IfExp):
            test = node.test
            if type(test) is ast.UnaryOp and type(test.op) is ast.Not:
                add(K_NEG, test, depth + 1, "unnot", [(node, "test", test.operand)])
            else:
                add(K_NEG, test, depth + 1, "not", [(node, "test", _loc(ast.UnaryOp(op=ast.Not(), operand=test), test))])
        if t is ast.Call and isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname not in COMMUTATIVE_CALLS:
                for i in range(len(node.args) - 1):
                    a, b = node.args[i], node.args[i + 1]
                    add(K_SWAP, node, depth, f"swap{i}", [(node.args, i, b), (node.args, i + 1, a)])
            if fname == "range":
                for i, a in enumerate(node.args):
                    _shift(a, depth + 1, (node.args, i))
        if t is ast.Subscript:
            _shift(node.slice, depth + 1, (node, "slice"))
        for field in node._fields:
            if t is ast.FunctionDef and field in ("args", "returns", "decorator_list"):
                continue
            v = getattr(node, field, None)
            if isinstance(v, list):
                for c in v:
                    if isinstance(c, ast.AST):
                        visit(c, depth + 1, node)
            elif isinstance(v, ast.AST):
                visit(v, depth + 1, node)

    def _shift(e, depth, slot):
        obj, key = slot
        if type(e) is ast.BinOp and type(e.op) in (ast.Add, ast.Sub) and type(e.right) is ast.Constant \
                and e.right.value == 1 and type(e.right.value) is int:
            add(K_SHIFT, e, depth, "unshift", [(obj, key, e.left)])
        add(K_SHIFT, e, depth, "+1", [(obj, key, _plus(e, ast.Add))])
        add(K_SHIFT, e, depth, "-1", [(obj, key, _plus(e, ast.Sub))])

    visit(fn, 0, None)
    return out


def apply_edits(edits, olds=None):
    """Apply edits in place; returns the old values (appended to `olds` as they are replaced, so an interrupted
    apply can still be reverted)."""
    olds = [] if olds is None else olds
    for obj, key, new in edits:
        if type(key) is int:
            olds.append(obj[key])
            obj[key] = new
        else:
            olds.append(getattr(obj, key))
            setattr(obj, key, new)
    return olds


def revert_edits(edits, olds):
    for (obj, key, _), old in zip(reversed(edits), reversed(olds)):
        if type(key) is int:
            obj[key] = old
        else:
            setattr(obj, key, old)


# ---------------------------------------------------------------------------------------------- guard and coverage
def _stmt(text, line):
    s = ast.parse(text).body[0]
    for n in ast.walk(s):
        if hasattr(n, "lineno"):
            n.lineno = n.end_lineno = line
            n.col_offset = n.end_col_offset = 0
    s._guard = True
    return s


def _marker(line):
    """`_h[line] = 1`, built directly (parsing it for every statement would be slow)."""
    loc = {"lineno": line, "end_lineno": line, "col_offset": 0, "end_col_offset": 0}
    s = ast.Assign(targets=[ast.Subscript(value=ast.Name(id="_h", ctx=ast.Load(), **loc),
                                          slice=ast.Constant(value=line, **loc), ctx=ast.Store(), **loc)],
                   value=ast.Constant(value=1, **loc), **loc)
    s._guard = True
    return s


def instrument(fn, coverage=False):
    """Insert the step guard (and line markers `_h[line] = 1` with coverage=True) into a function AST, in place."""
    top_assigned = []                               # (top-level statement index, names it assigns)
    for i, s in enumerate(fn.body):
        top_assigned.append((i, {n.id for n in ast.walk(s) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                             if isinstance(s, (ast.Assign, ast.AugAssign)) else set()))
    loops = []
    for i, s in enumerate(fn.body):
        for n in ast.walk(s):
            if isinstance(n, (ast.For, ast.While)):
                loops.append((i, n))
    for i, loop in loops:
        before = set().union(*[a for j, a in top_assigned if j < i])
        inside = {n.id for b in loop.body for n in ast.walk(b) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        watch = sorted(before & inside)
        cond = f"(_n := _n + 1) > {STEP_CAP}"
        if watch:                                   # a runaway value (or a NaN) makes the sum leave the range
            cond += f" or not -{VALUE_CAP:g} < {' + '.join(watch)} < {VALUE_CAP:g}"
        loop.body.insert(0, _stmt(f"if {cond}:\n    raise _Halt", loop.lineno))
    if coverage:
        def mark(body):
            out = []
            for s in body:
                if not getattr(s, "_guard", False):
                    out.append(_marker(s.lineno))
                    for f in ("body", "orelse"):
                        sub = getattr(s, f, None)
                        if isinstance(sub, list) and sub:
                            setattr(s, f, mark(sub))
                out.append(s)
            return out
        fn.body = mark(fn.body)
    fn.body.insert(0, _stmt("_n = 0", fn.lineno))
    return fn


def plain_text(text):
    """Drop the guard lines from an unparsed instrumented program."""
    keep = []
    skip_raise = False
    for ln in text.split("\n"):
        s = ln.strip()
        if s == "_n = 0" or s.startswith("if (_n := "):
            skip_raise = s.startswith("if (_n := ")
            continue
        if skip_raise and s == "raise _Halt":
            skip_raise = False
            continue
        keep.append(ln)
    return "\n".join(keep)


# ---------------------------------------------------------------------------------------------- running tests
def run_tests(code, fname, tests, expected, hits=None, order=None, must_pass=0):
    """(failing tests, total error, statuses, relative errors). Total error = sum over failing tests of
    rel / (1 + rel) for a wrong value, 1 for an exception or a halted run. With hits=list, collects line coverage.
    With must_pass=m, the first m tests of `order` must pass: at the first of them that fails the run stops and
    returns failing = -1."""
    g = dict(BASE_GLOBALS)
    exec(code, g)
    f = g[fname]
    n_fail, total = 0, 0.0
    status, rels = [], []
    for ti in (order if order is not None else range(len(tests))):
        args, exp = tests[ti], expected[ti]
        if hits is not None:
            g["_h"] = h = bytearray(hits[0])
        st, rel = 0, 0.0
        try:
            out = f(*args)
        except TimeoutError:
            raise
        except _Halt:
            st = 6
        except ZeroDivisionError:
            st = 2
        except IndexError:
            st = 3
        except TypeError:
            st = 4
        except Exception:  # noqa: BLE001 - any runtime error of a buggy program is a test outcome
            st = 5
        else:
            if type(out) is not tuple:
                out = (out,)
            if len(out) != len(exp):
                st, rel = 1, 1e6
            else:
                try:
                    for a, b in zip(out, exp):
                        rel += abs(a - b) / (1.0 + abs(b))
                except Exception:  # noqa: BLE001 - a wrong type or an overflow in the comparison
                    rel = 1e6
                if not rel <= TOL:
                    st = 1
                    rel = rel if rel < 1e6 else 1e6
                else:
                    rel = 0.0
        if st:
            if len(status) < must_pass:
                return -1, 0.0, status, rels
            n_fail += 1
            total += rel / (1.0 + rel) if st == 1 else 1.0
        status.append(st)
        rels.append(rel)
        if hits is not None:
            hits.append(h)
    return n_fail, total, status, rels


def _compile(tree):
    return compile(tree, "<program>", "exec")


def improves(cur_fail, cur_err, nf, err):
    """The keep rule, for a run in which every previously passing test still passed (nf >= 0): fewer failing tests,
    or as many and the total error down by at least (1 - KEEP_ERR)."""
    return nf >= 0 and (nf < cur_fail or (nf == cur_fail and err < KEEP_ERR * cur_err))


# ---------------------------------------------------------------------------------------------- program states
class Program:
    """One correct program and its test suite."""

    def __init__(self, name):
        spec = PROGRAMS[name]
        self.name, self.family, self.lists = name, spec["family"], spec["lists"]
        self.text = ast.unparse(ast.parse(spec["src"]))
        self.n_lines = len(self.text.split("\n"))
        r = random.Random(spec["seed"])
        self.tests = [spec["gen"](r) for _ in range(N_TESTS)]
        tree = ast.parse(self.text)
        instrument(tree.body[0])
        g = dict(BASE_GLOBALS)
        exec(_compile(tree), g)
        f = g[name]
        self.expected = []
        for a in self.tests:
            out = f(*a)
            self.expected.append(out if type(out) is tuple else (out,))
        h = hashlib.sha1(self.text.encode())
        h.update(repr((self.tests, self.expected)).encode())
        self.digest = h.hexdigest()[:12]


_PROGRAMS = {}


def program(name):
    p = _PROGRAMS.get(name)
    if p is None:
        p = _PROGRAMS[name] = Program(name)
    return p


class State:
    """A program state: the instrumented AST, its candidate patches (with per-candidate feature arrays) and its tests."""

    def __init__(self, prog, text):
        self.prog, self.text = prog, text
        tree = ast.parse(text)
        fn = tree.body[0]
        ps = patches(fn, prog.lists)
        self.edits = [p[5] for p in ps]
        self.keys = [(p[1], p[2], p[0], p[4]) for p in ps]
        self.kind = np.array([p[0] for p in ps], dtype=np.int64)
        self.line = np.array([p[1] for p in ps], dtype=np.int64)
        self.depth = np.array([p[3] for p in ps], dtype=np.int64)
        instrument(fn)
        self.tree = tree
        ctree = ast.parse(text)
        instrument(ctree.body[0], coverage=True)
        L = prog.n_lines + 2
        hits = [L]
        nf, tot, status, rels = run_tests(_compile(ctree), prog.name, prog.tests, prog.expected, hits)
        self.n_fail, self.err = nf, tot
        self.status = np.array(status, dtype=np.int64)
        self.rel = np.array(rels, dtype=float)
        cov = np.array([np.frombuffer(h, dtype=np.uint8) for h in hits[1:]], dtype=bool)     # (T, L)
        failing = self.status > 0
        line_cov = cov.T                                                                    # (L, T)
        self.cov = line_cov[self.line]                                                      # (P, T)
        self.fcov = self.cov[:, failing].sum(1).astype(np.int64)
        self.pcov = self.cov[:, ~failing].sum(1).astype(np.int64)
        self.outcomes = np.bincount(self.status, minlength=len(STATUS)).astype(np.int64)
        self.order = [int(t) for t in np.flatnonzero(~failing)] + [int(t) for t in np.flatnonzero(failing)]

    def better(self, nf, err):
        return improves(self.n_fail, self.err, nf, err)

    def try_patch(self, c):
        """(failing, error, new program text or None): the result of patch c; the text only when it improves."""
        if not self.cov[c].any():               # no test executes the edited line: no test result can change
            return self.n_fail, self.err, None
        edits = self.edits[c]
        olds = []
        try:
            apply_edits(edits, olds)
            try:
                code = _compile(self.tree)
            except (SyntaxError, ValueError, TypeError):
                return len(self.prog.tests), float(len(self.prog.tests)), None
            nf, err, _, _ = run_tests(code, self.prog.name, self.prog.tests, self.prog.expected, order=self.order,
                                      must_pass=len(self.order) - self.n_fail)
            new = plain_text(ast.unparse(self.tree)) if self.better(nf, err) else None
            return nf, err, new
        finally:
            revert_edits(edits[:len(olds)], olds)


class Memo:
    """Per-process caches: program states (LRU) and patch results per (state, patch)."""

    def __init__(self, max_states=160, max_results=250_000):
        self.states = OrderedDict()
        self.results = {}
        self.max_states, self.max_results = max_states, max_results
        self.lock = threading.Lock()            # a state's AST is patched in place: one try at a time per process

    def state(self, prog, text):
        key = (prog.name, text)
        with self.lock:
            st = self.states.get(key)
            if st is None:
                st = self.states[key] = State(prog, text)
                if len(self.states) > self.max_states:
                    self.states.popitem(last=False)
            else:
                self.states.move_to_end(key)
            return st

    def result(self, st, c):
        key = (st.prog.name, st.text, c)
        r = self.results.get(key)
        if r is None:
            with self.lock:
                r = st.try_patch(c)
                if len(self.results) >= self.max_results:
                    self.results.clear()
                self.results[key] = r
        return r


MEMO = Memo()


def _after_fork():
    """A fork can happen while another thread holds the lock or has a tree patched: start the child clean."""
    MEMO.states, MEMO.results, MEMO.lock = OrderedDict(), {}, threading.Lock()


os.register_at_fork(after_in_child=_after_fork)


# ---------------------------------------------------------------------------------------------- instances
BUG_CATEGORIES = ["operator", "off-by-one", "variable", "constant", "negate", "swap"]
MIN_SINGLE, MAX_SINGLE = 0.1, 0.6   # a bug on its own fails between these shares of the tests
MIN_ALL, MAX_ALL = 0.25, 0.8        # all bugs together fail between these shares


def bug_category(p):
    kind, node = p[0], p[6]
    if kind == K_CMP and type(node) is ast.Compare:
        pair = {type(node.ops[0]).__name__, p[4]}
        return "off-by-one" if pair in ({"Lt", "LtE"}, {"Gt", "GtE"}) else "operator"
    return {K_OP: "operator", K_CMP: "operator", K_ONE: "off-by-one", K_SHIFT: "off-by-one", K_VAR: "variable",
            K_TWO: "constant", K_TEN: "constant", K_NEG: "negate", K_SWAP: "swap"}[kind]


def _score(prog, tree, ps, sub):
    """(failing tests, total error, set of failing tests) of the correct program with the patches `sub` applied."""
    olds = [apply_edits(ps[c][5]) for c in sub]
    try:
        nf, err, status, _ = run_tests(_compile(tree), prog.name, prog.tests, prog.expected)
        fails = frozenset(i for i, st in enumerate(status) if st)
    except (SyntaxError, ValueError, TypeError):
        nf, err, fails = len(prog.tests), float(len(prog.tests)), frozenset(range(len(prog.tests)))
    finally:
        for c, o in zip(reversed(sub), reversed(olds)):
            revert_edits(ps[c][5], o)
    return nf, err, fails


def _step_ok(a, b):
    """Would the engine keep the edit that turns a program scored `a` into one scored `b`?"""
    return b[2] <= a[2] and improves(a[0], a[1], b[0], b[1])


def _solvable(prog, tree, ps, chosen, single):
    """All bugs together leave enough tests passing, and some order of single fixes improves the tests at every
    step (scores of every subset of the bugs)."""
    k = len(chosen)
    score = {0: (0, 0.0, frozenset())}
    for i in range(k):
        score[1 << i] = single[chosen[i]]
    for mask in range(1, 1 << k):
        if mask not in score:
            score[mask] = _score(prog, tree, ps, [chosen[i] for i in range(k) if mask >> i & 1])
    full = (1 << k) - 1
    if not MIN_ALL * len(prog.tests) <= score[full][0] <= MAX_ALL * len(prog.tests):
        return False
    good = {0: True}
    for mask in range(1, 1 << k):
        good[mask] = any(good[mask & ~(1 << i)] and _step_ok(score[mask], score[mask & ~(1 << i)])
                         for i in range(k) if mask >> i & 1)
    return good[full]


_SINGLE = {}                    # program -> {patch index: (failing, error)} of the correct program with one bug


def bug_sets(prog, rng):
    """Yields (buggy text, bug descriptions): 2-4 bugs on distinct, non-nested nodes, categories drawn uniformly,
    each bug failing between MIN_SINGLE and MAX_SINGLE of the tests on its own, and solvable (see _solvable)."""
    tree = ast.parse(prog.text)
    fn = tree.body[0]
    ps = patches(fn, prog.lists)
    instrument(fn)
    anc = {}
    for parent in ast.walk(fn):
        for child in ast.iter_child_nodes(parent):
            anc[id(child)] = parent
    by_cat = {}
    for i, p in enumerate(ps):
        if p[7]:
            by_cat.setdefault(bug_category(p), []).append(i)
    single = _SINGLE.setdefault(prog.name, {})
    lo, hi = MIN_SINGLE * len(prog.tests), MAX_SINGLE * len(prog.tests)

    def ok_alone(c):
        if c not in single:
            single[c] = _score(prog, tree, ps, [c])
        return lo <= single[c][0] <= hi

    def ancestors(node):
        out, n = set(), anc.get(id(node))
        while n is not None:
            out.add(id(n))
            n = anc.get(id(n))
        return out

    cats = [c for c in BUG_CATEGORIES if c in by_cat]
    k = int(rng.integers(2, 5))
    for _ in range(300):
        chosen, nodes = [], []
        for _ in range(200):
            if len(chosen) == k:
                break
            cat = cats[int(rng.integers(len(cats)))]
            c = by_cat[cat][int(rng.integers(len(by_cat[cat])))]
            node = ps[c][6]
            if any(node is n or id(n) in ancestors(node) or id(node) in ancestors(n) for n in nodes):
                continue
            if not ok_alone(c):
                continue
            chosen.append(c)
            nodes.append(node)
        if len(chosen) == k and _solvable(prog, tree, ps, chosen, single):
            olds = [apply_edits(ps[c][5]) for c in chosen]
            text = plain_text(ast.unparse(tree))
            for c, o in zip(reversed(chosen), reversed(olds)):
                revert_edits(ps[c][5], o)
            yield text, [f"line {ps[c][1]}: {bug_category(ps[c])} ({KIND_NAMES[ps[c][0]]} {ps[c][4]})" for c in chosen], chosen
    raise RuntimeError(f"repair: no valid bug set for {prog.name}")


def _gen_key(prog, seed):
    """Everything an instance's generation depends on (a cached instance is used only when this matches)."""
    parts = (VERSION, BUDGET, FAIL_PENALTY, KEEP_ERR, N_TESTS, STEP_CAP, VALUE_CAP, VAR_WINDOW, MIN_SINGLE, MAX_SINGLE,
             MIN_ALL, MAX_ALL, prog.digest, seed)
    return hashlib.sha1(repr(parts).encode()).hexdigest()[:12]


def _load_cache():
    try:
        return json.loads(CZ_FILE.read_text())["instances"]
    except (OSError, ValueError, KeyError):
        return {}


def make_instance(split, fam, i, cached=None):
    """One instance: the first bug set from the seeded draw on which Code Zero does not repair every test within the
    budget (so Code Zero's cost is always a budget-exhausted cost), with Code Zero's cost. A cached entry whose
    generation key matches is used as is (it is what this function would compute)."""
    prog = program(FAMILY_PROGRAMS[fam][i % len(FAMILY_PROGRAMS[fam])])
    seed = [SPLIT_SEED[split], CODES[fam], i]
    key = _gen_key(prog, seed)
    base = {"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "program": prog.name,
            "seed": seed + [7], "fingerprint": key}
    if cached and cached.get("fingerprint") == key:
        return dict(base, text=cached["text"], bugs=cached["bugs"], bug_idx=cached["bug_idx"], cz_cost=cached["cost"],
                    redraws=cached["redraws"])
    rng = np.random.default_rng(seed)
    for redraws, (text, bugs, idx) in enumerate(bug_sets(prog, rng)):
        inst = dict(base, text=text, bugs=bugs, bug_idx=[int(c) for c in idx], redraws=redraws)
        s = {}
        cost = repair(inst, None, s)
        if not s["solved"]:
            inst["cz_cost"] = cost
            return inst
        if redraws > 50:
            break
    raise RuntimeError(f"repair: Code Zero repairs every bug set of {base['id']}")


def raw_instances(split, use_cache=True):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    cache = _load_cache() if use_cache else {}
    out = []
    for fam in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        for i in range(PER_FAMILY):
            out.append(make_instance(split, fam, i, cache.get(f"{split}/{fam}-{SPLIT_BASE[split] + i:03d}")))
    return out


# ---------------------------------------------------------------------------------------------- the repair loop
def repair(inst, priority, stats=None):
    """Run the patch loop under `priority` (None = Code Zero). Returns the cost."""
    prog = program(inst["program"])
    st = MEMO.state(prog, inst["text"])
    rng = np.random.default_rng(inst["seed"])
    L = prog.n_lines + 2
    edited = np.zeros(L, dtype=bool)
    line_tries = np.zeros(L, dtype=np.int64)
    untried = np.ones(len(st.kind), dtype=bool)
    tries = kept = focus = 0
    while tries < BUDGET and st.n_fail > 0:
        idx = np.flatnonzero(untried)
        k = len(idx)
        if k == 0:
            break
        cand = idx[rng.permutation(k)]
        if priority is None or k == 1:
            c = int(cand[0])
        else:
            ln = st.line[cand]
            args = (st.kind[cand], ln, st.depth[cand], st.fcov[cand], st.pcov[cand], st.cov[cand], edited[ln],
                    line_tries[ln], st.status, st.rel, st.outcomes, tries, BUDGET)
            s = np.asarray(priority(*args), dtype=float)
            if s.shape != (k,):
                raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
            c = int(cand[int(np.argmax(np.round(s, 9)))])
        tries += 1
        line = int(st.line[c])
        line_tries[line] += 1
        focus += int(st.fcov[c] > 0)
        nf, err, new = MEMO.result(st, c)
        if new is not None:
            kept += 1
            edited[line] = True
            st = MEMO.state(prog, new)
            untried = np.ones(len(st.kind), dtype=bool)
        else:
            untried[c] = False
    cost = float(tries) if st.n_fail == 0 else BUDGET + FAIL_PENALTY * st.n_fail + st.err
    if stats is not None:
        stats.update(tries=tries, kept=kept, failing=st.n_fail, solved=int(st.n_fail == 0), focus=focus,
                     err=st.err, text=st.text)
    return cost


# ---------------------------------------------------------------------------------------------- the problem
class Repair(Problem):
    name = "repair"
    title = "Repair: choose the next patch to try on a buggy program"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = ("feature(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, "
                 "tries, budget)")
    candidates_arg = 0
    description = f"""Automatic program repair. A small calculation program (one Python function of 15-40 lines: loops, branches, arithmetic) has a few injected bugs. A fixed repair engine tries single-edit patches one at a time; the policy decides which patch is tried next.

**Programs and tests.** Each program is an invented calculation (a tariff or fee calculator, a geometry routine, a small simulator, ...). Its correct version is hidden; it produced a test suite of {N_TESTS} inputs with their expected outputs (one or a few numbers per test). A test **passes** when the output matches within a relative error of 1e-9; otherwise it **fails**, either with a wrong value (its relative error = sum over output numbers of |got - expected| / (1 + |expected|)) or with an exception. Every run has a step guard: a run stops as `halted` after {STEP_CAP} loop iterations or when a value carried through a loop leaves +-{VALUE_CAP:g}.

**Bugs.** An instance is one program with 2 to 4 bugs, each a single edit of the correct program of one of these kinds: an arithmetic operator swapped, a comparison or `and`/`or` swapped, a numeric constant changed, a variable read replaced by another variable, a condition negated (or a negation removed), two arguments or operands swapped, an index or `range` bound shifted by one. Every bug makes some tests fail on its own, and undoing the bugs one at a time in some order is kept by the engine at every step (see below). Bug sets on which Code Zero (below) repairs every test within the budget are redrawn, so Code Zero always exhausts its budget.

**Patches (the candidates).** A patch is one edit of the program's current state, with these **kinds** (ids): 0 `operator` (+ <-> -, * <-> /, / <-> //, // <-> %), 1 `comparison` (< <-> <=, < <-> >, <= <-> >=, > <-> >=, == <-> !=, and <-> or), 2 `constant+-1` (an integer literal +-1), 3 `constant*/2` (a numeric literal doubled or halved; integers halved only when even), 4 `constant*/10` (a float literal x10 or /10), 5 `variable` (a read of a local variable replaced by another local variable of the same type that is assigned inside a loop enclosing the read or on one of the {VAR_WINDOW} lines above it; parameters are never swapped), 6 `negate` (the condition of an if / while wrapped in `not`, or its `not` removed), 7 `swap` (the operands of -, /, //, % or two neighbouring arguments of a call other than min/max swapped), 8 `shift` (an index or `range` argument e changed to e + 1 or e - 1, or `e + 1` / `e - 1` back to e). Every patch at every place where it applies is a candidate, except patches already tried in the current state. A bug's inverse edit is always among the candidates, but other patches may also be kept.

**One decision** = choosing the next patch to try. The engine applies it and runs the tests. The patch is **kept** when no test that passed before now fails, and either fewer tests fail, or as many fail and the total error is at most {KEEP_ERR:g} x what it was (total error = sum over failing tests of rel / (1 + rel) for a wrong value with relative error rel, 1 for an exception or a halted run). Otherwise it is **reverted**. A kept patch changes the program, so the next decision has the candidates of the new program (all untried again). Candidates come in a random order (reshuffled at every decision), so the list order carries no information.

**Cost** of an instance: the number of patches tried until every test passes; or, if the budget of {BUDGET} tries runs out first (or no untried candidate is left), {BUDGET} + {FAIL_PENALTY:g} x (tests still failing) + their total error. The **gap** of an instance is 100 x cost / the cost of Code Zero (the policy that always takes the first candidate, i.e. a random patch) on the same instance: Code Zero scores 100, lower is better; nothing tells where the best possible lies.

Families are groups of programs: `billing`, `geometry`, `simulation` (two programs each; instances differ in program and bugs). The test split adds a family of programs that training never shows."""
    signature_doc = f"""Per-candidate arrays have the candidates on the first axis (k = number of candidate patches, in the decision's random order); T = {N_TESTS} tests.
- `kind`: shape (k,), int: the patch kind id 0-8 (0 operator, 1 comparison, 2 constant+-1, 3 constant*/2, 4 constant*/10, 5 variable, 6 negate, 7 swap, 8 shift).
- `line`: shape (k,), int: the program line the patch edits (1 = the `def` line; programs have 15-40 lines).
- `depth`: shape (k,), int: depth of the edited syntax node below the function definition (statements in the function body are at depth 1; deeper = further inside expressions and nested blocks).
- `fail_cov`: shape (k,), int: how many currently failing tests execute the patch's line (in the current program).
- `pass_cov`: shape (k,), int: how many currently passing tests execute the patch's line.
- `covered`: shape (k, T), bool: which tests execute the patch's line.
- `edited`: shape (k,), bool: whether a patch on the same line has been kept earlier in this instance.
- `line_tries`: shape (k,), int: how many patches on the same line have been tried so far in this instance (kept or not).
- `status`: shape (T,), int: each test's outcome on the current program: 0 pass, 1 wrong value, 2 ZeroDivisionError, 3 IndexError, 4 TypeError, 5 another exception, 6 halted by the step guard.
- `error`: shape (T,), float: each test's relative error for a wrong value (capped at 1e6); 0 for passing tests and for tests that raised or halted.
- `outcomes`: shape (7,), int: how many tests have each status (index = status code); the failing tests are outcomes[1:].sum().
- `tries`: int: patches tried so far in this instance.
- `budget`: int: the budget of tries ({BUDGET}).
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is tried next."""
    metric_notes = {
        "cost": f"patches tried until every test passed, or {BUDGET} + {FAIL_PENALTY:g} x failing tests + their error when the budget ran out",
        "tries": "patches tried",
        "solved": "1 if every test passed within the budget, else 0",
        "failing_left": f"tests still failing at the end (of {N_TESTS})",
        "kept": "patches kept (they improved the tests)",
        "focus_pct": "% of tries on a line executed by at least one failing test (at the time of the try)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):\n"
        "    \"\"\"Failing tests that execute the patch's line.\"\"\"\n"
        "    return fail_cov.astype(float)\n",
        "import numpy as np\n\ndef feature(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):\n"
        "    \"\"\"Two columns: passing tests on the line, and tries on the line so far.\"\"\"\n"
        "    return np.stack([pass_cov.astype(float), line_tries.astype(float)], axis=1)\n",
        "import numpy as np\n\ndef feature(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):\n"
        "    \"\"\"Failing tests with a wrong value (not an exception) that execute the line.\"\"\"\n"
        "    return (covered & (status == 1)[None, :]).sum(axis=1).astype(float)\n",
    ]

    def __init__(self):
        self._cache = {}

    def instances(self, split):
        if split not in self._cache:
            self._cache[split] = raw_instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    def cz_cost(self, inst):
        return inst["cz_cost"]

    def run(self, instance, priority):
        cost = repair(instance, priority)
        return {"gap": 100.0 * (cost / self.cz_cost(instance)), "cost": cost}

    def diagnose(self, instance, priority):
        s = {}
        cost = repair(instance, priority, s)
        return {
            "gap": round(100.0 * (cost / self.cz_cost(instance)), 3),
            "cost": round(cost, 3),
            "tries": s["tries"],
            "solved": s["solved"],
            "failing_left": s["failing"],
            "kept": s["kept"],
            "focus_pct": round(100.0 * s["focus"] / max(1, s["tries"]), 1),
        }


# ---------------------------------------------------------------------------------------------- cache and tools
def build_cz():
    """Regenerate every instance (ignoring the cache) and write the instances and Code Zero's costs."""
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in raw_instances(split, use_cache=False):
            s = {}
            cost = repair(inst, None, s)
            assert cost == inst["cz_cost"], inst["id"]
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "cost": cost, "program": inst["program"],
                                            "bugs": inst["bugs"], "bug_idx": inst["bug_idx"],
                                            "redraws": inst["redraws"], "text": inst["text"],
                                            "failing_left": s["failing"]}
            print(f"  {split:5s} {inst['id']:16s} {inst['program']:10s} bugs {len(inst['bugs'])} redraws "
                  f"{inst['redraws']:2d} Code Zero cost {cost:7.2f} (failing {s['failing']}, kept {s['kept']})")
    CZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CZ_FILE.write_text(json.dumps({"method": "repair instances (buggy programs) and Code Zero's cost per instance; "
                                             "rebuild with `python -m suite.repair --cz`",
                                   "version": VERSION, "budget": BUDGET, "instances": out}, indent=0))
    print(f"wrote {CZ_FILE} ({len(out)} instances, {time.time() - t0:.1f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cz", action="store_true", help="rebuild suite/data/repair_cz.json")
    ap.add_argument("--show", default=None, help="print an instance's buggy program (e.g. train/billing-000)")
    a = ap.parse_args(argv)
    if a.cz:
        build_cz()
    elif a.show:
        split, iid = a.show.split("/")
        inst = Repair().instance(split, iid)
        print(inst["text"])
        print("bugs:", inst["bugs"])
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
