"""Hills: telling apart what programs produce (docs/V8_DESIGN.md).

A hill is a family of programs whose outputs are nearly the same: climbing moves a program along its hill, and a
new hill is an output far from every known one. The distance is measured by code, never by the model.

- The autocorrelation problem (and any problem whose output is one non-negative step function): the shape of the
  construction. Its support is trimmed and rescaled to [0, 1], its mass normalised, and it is resampled, preserving
  mass, to `bins` equal bins. The distance is the total-variation distance between two such shapes (the fraction of
  mass that would have to move), taking the closer of the two orientations, since the score doesn't change when the
  function is mirrored. It lies in [0, 1].
- A problem plug-in can give its own signature and distance (the VRP: the trips its solutions are made of).

Measured on the best constructions of 19 earlier runs (64 bins): the textbook 0.8825 constructions found by 6
different runs are within 0.04 of each other; 100 generations of polishing moved v4.7's record 0.06 (to v7's); the
bests of genuinely different runs are 0.09 to 0.6 apart. Hence the default radius of 0.075.
"""
from __future__ import annotations

import numpy as np


def shape_signature(h, bins=64):
    """The construction's shape: its mass in `bins` equal parts of its support (sums to 1), or None."""
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    if h.size == 0 or not np.isfinite(h).all() or h.max() <= 0:
        return None
    nz = np.nonzero(h > 1e-12 * h.max())[0]
    h = h[nz[0]: nz[-1] + 1]
    c = np.concatenate(([0.0], np.cumsum(h))) / h.sum()
    x = np.linspace(0.0, 1.0, len(h) + 1)
    return np.diff(np.interp(np.linspace(0.0, 1.0, bins + 1), x, c))


def shape_distance(a, b):
    """Total-variation distance between two shapes, the closer orientation (0: the same shape; 1: disjoint)."""
    if a is None or b is None or len(a) != len(b):
        return None
    a, b = np.asarray(a), np.asarray(b)
    return float(min(0.5 * np.abs(a - b).sum(), 0.5 * np.abs(a - b[::-1]).sum()))
