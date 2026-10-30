"""The dry run (docs/BRIEF_2026-10-29.md): circle packing as a search over dials, by hand, no language model.

n equal coins in the unit square, as large as possible. Equivalent: n points in the unit square with the smallest
pairwise distance d as large as possible; the coins' radius is r = d / (2 (1 + d)).

One program skeleton. The literature's approaches (square grid, hexagonal rows, push apart, shake and re-settle,
greedy placement) are taken apart into ingredients, each a dial with a trade-off:

    rows    number of rows of the starting pattern               (integer)
    shift   offset of every other row: 0 square, 0.5 hexagonal    [0, 0.5]
    greedy  share of coins placed greedily (emptiest spot)        [0, 1]
    push    step size of the push-apart settle (log10)            [-3.5, -1]
    sharp   how much the push focuses on the closest pairs (p)    [2, 40]
    shake   size of the jiggle before each re-settle              [0, 0.15]

Resources, fixed for every point: settle steps, shake rounds, the random seed (common to all points, so two nearby
settings differ only by their dials).
"""
from __future__ import annotations

import math

import numpy as np

DIALS = {             # name: (low, high, integer?)
    "rows": (1, None, True),
    "shift": (0.0, 0.5, False),
    "greedy": (0.0, 1.0, False),
    "push": (-3.5, -1.0, False),
    "sharp": (2.0, 40.0, False),
    "shake": (0.0, 0.15, False),
}
SETTLE_STEPS = 300
SHAKE_ROUNDS = 12
RESETTLE_STEPS = 120


def bounds(n):
    b = dict(DIALS)
    b["rows"] = (1, max(2, int(round(2 * math.sqrt(n)))), True)
    return b


def min_dist(P):
    D = np.sqrt(((P[:, None, :] - P[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(D, np.inf)
    return D.min()


def radius(P):
    d = min_dist(P)
    return d / (2 * (1 + d))


def pattern(n, rows, shift):
    """n points in `rows` rows; every other row offset by `shift` of a column; spans the square."""
    rows = max(1, min(int(rows), n))
    per = [n // rows + (1 if i < n % rows else 0) for i in range(rows)]
    pts = []
    for i, c in enumerate(per):
        y = 0.5 if rows == 1 else i / (rows - 1)
        off = shift if i % 2 else 0.0
        span = (c - 1) + shift if c > 1 else 1.0
        for j in range(c):
            x = 0.5 if c == 1 and shift == 0 else (j + off) / span
            pts.append((x, y))
    return np.clip(np.array(pts, float), 0, 1)


def greedy_fill(P, m, rng, cand=600):
    """Adds m points one at a time, each at the candidate farthest from every point so far (and from nothing else)."""
    pts = list(P)
    for _ in range(m):
        C = rng.random((cand, 2))
        if pts:
            A = np.array(pts)
            dmin = np.sqrt(((C[:, None, :] - A[None, :, :]) ** 2).sum(-1)).min(1)
        else:
            dmin = np.zeros(cand)
        pts.append(C[int(np.argmax(dmin))])
    return np.array(pts)


def settle(P, steps, eta, p):
    """Push apart: gradient steps on sum_{i<j} (d0/d_ij)^p, kept in the square. eta is the largest move per step."""
    P = P.copy()
    n = len(P)
    for _ in range(steps):
        diff = P[:, None, :] - P[None, :, :]
        d = np.sqrt((diff ** 2).sum(-1)) + np.eye(n)
        d0 = d[~np.eye(n, dtype=bool)].min()
        w = (d0 / d) ** p / d ** 2
        np.fill_diagonal(w, 0.0)
        g = (w[:, :, None] * diff).sum(1)
        norm = np.abs(g).max()
        if norm == 0 or not np.isfinite(norm):
            break
        P = np.clip(P + eta * g / norm, 0.0, 1.0)
    return P


def build(n, dials, seed=0):
    """The program at a point: the starting pattern, greedy placement, push-apart settle, then shake and re-settle
    (a shake is kept only if it improves). Returns (points, radius)."""
    rng = np.random.default_rng(seed)
    m = int(round(dials["greedy"] * n))
    P = pattern(n - m, dials["rows"], dials["shift"]) if n - m > 0 else np.zeros((0, 2))
    P = greedy_fill(P, m, rng)
    P = P + rng.normal(0, 1e-6, P.shape)                      # break exact ties
    eta, p = 10 ** dials["push"], dials["sharp"]
    P = settle(P, SETTLE_STEPS, eta, p)
    best, rb = P, radius(P)
    for _ in range(SHAKE_ROUNDS):
        if dials["shake"] <= 0:
            break
        Q = np.clip(best + rng.normal(0, dials["shake"], best.shape), 0, 1)
        Q = settle(Q, RESETTLE_STEPS, eta, p)
        rq = radius(Q)
        if rq > rb:
            best, rb = Q, rq
    return best, rb


def score(n, dials, seeds=(0, 1)):
    """The height of a point: the mean radius over a few fixed seeds (the same seeds for every point)."""
    return float(np.mean([build(n, dials, s)[1] for s in seeds]))
