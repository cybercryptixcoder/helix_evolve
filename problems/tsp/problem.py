"""Problem: greedy construction of a travelling-salesman tour.

A tour starts at city 0. At each step the traveller stands on the current city and the candidate
program scores every city; the highest score among the unvisited ones is visited next. After the
last city the tour closes back to city 0. The goal is the shortest total tour length.

The candidate never writes the loop: it only scores cities. Its view is deliberately local — the
current city, the coordinates, which cities are visited, and the distance matrix.
"""
import math

import numpy as np

N_CITIES = 120
TRAIN_SEEDS = (2101, 2102, 2103)
TEST_SEEDS = (3101, 3102, 3103)
QUICK_SEEDS = (9101,)

FAMILIES = ("uniform", "clustered", "grid", "circle", "skewed")
TEST_EXTRA_FAMILY = "spiral"  # held out: never in a train instance


def make_cities(family, seed, n=N_CITIES):
    rng = np.random.default_rng(seed)
    if family == "uniform":
        coords = rng.uniform(0.0, 100.0, size=(n, 2))
    elif family == "clustered":
        centers = rng.uniform(10.0, 90.0, size=(6, 2))
        pick = rng.integers(0, len(centers), size=n)
        coords = centers[pick] + rng.normal(0.0, 6.0, size=(n, 2))
    elif family == "grid":
        side = int(math.ceil(math.sqrt(n)))
        gx, gy = np.meshgrid(np.arange(side), np.arange(side))
        pts = np.stack([gx.ravel(), gy.ravel()], axis=1)[:n].astype(float)
        coords = pts * (100.0 / max(1, side - 1)) + rng.normal(0.0, 1.5, size=(n, 2))
    elif family == "circle":
        ang = np.sort(rng.uniform(0.0, 2 * math.pi, size=n))
        r = 40.0 + rng.normal(0.0, 1.5, size=n)
        coords = np.stack([50 + r * np.cos(ang), 50 + r * np.sin(ang)], axis=1)
    elif family == "skewed":
        coords = 100.0 * rng.power(3.0, size=(n, 2))
    elif family == "spiral":
        t = np.linspace(0.0, 1.0, n)
        ang = 6.0 * math.pi * t + rng.normal(0.0, 0.05, size=n)
        r = 5.0 + 45.0 * t
        coords = np.stack([50 + r * np.cos(ang), 50 + r * np.sin(ang)], axis=1)
    else:
        raise ValueError(f"unknown family {family!r}")
    return np.clip(coords, 0.0, 100.0)


def make_instance(family, seed, n=N_CITIES):
    coords = make_cities(family, seed, n)
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.sqrt((diff ** 2).sum(-1))
    return {"id": f"{family}-{seed}", "family": family, "seed": seed, "coords": coords, "dist": dist}


def split_seeds(split):
    """(families, seeds, per_family) for a split name."""
    if split == "train":
        return FAMILIES, TRAIN_SEEDS, len(TRAIN_SEEDS)
    if split == "test":
        return FAMILIES + (TEST_EXTRA_FAMILY,), TEST_SEEDS, len(TEST_SEEDS)
    if split == "quick":
        return FAMILIES, QUICK_SEEDS, 1
    raise ValueError(f"unknown split {split!r}, expected one of ['train', 'test', 'quick']")


def load_split(split):
    families, seeds, per_family = split_seeds(split)
    n = 40 if split == "quick" else N_CITIES
    instances = []
    for fam in families:
        for seed in seeds[:per_family]:
            instances.append(make_instance(fam, seed, n))
    return instances


def lower_bound(dist):
    """Half the sum, over cities, of each city's two nearest-neighbour distances.

    Every tour enters and leaves each city exactly once, so the trip through any city is at least
    its two shortest incident edges; summing half of those counts every edge of a tour once. No
    tour can be shorter than this bound.
    """
    d = dist.copy()
    np.fill_diagonal(d, np.inf)
    two = np.partition(d, 1, axis=1)[:, :2]
    return float(two.sum()) / 2.0


def run_instance(inst, pick):
    """Greedy tour scored by the candidate. One fresh `pick` per instance (see evaluate.py)."""
    coords, dist = inst["coords"], inst["dist"]
    n = len(coords)
    visited = np.zeros(n, dtype=bool)
    visited[0] = True
    current = 0
    total = 0.0
    for _ in range(n - 1):
        scores = np.asarray(pick(current, coords, visited, dist), dtype=float)
        if scores.shape != (n,):
            raise ValueError(f"pick returned shape {scores.shape}, expected ({n},)")
        if not np.all(np.isfinite(scores)):
            raise ValueError("pick returned a non-finite score for some city")
        scores = scores.copy()
        scores[visited] = -np.inf
        nxt = int(np.argmax(scores))
        total += float(dist[current, nxt])
        visited[nxt] = True
        current = nxt
    total += float(dist[current, 0])
    lb = lower_bound(dist)
    return {"instance": inst["id"], "family": inst["family"], "length": total,
            "lower_bound": lb, "excess": total / lb - 1.0}
