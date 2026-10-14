# The problem: greedy construction of a travelling-salesman tour

Cities sit at points in a square. One traveller visits every city exactly once, always starting at city 0. At each step the traveller stands on the current city and must choose the next one right away, seeing only the city positions and which cities are already visited; when only one city is left it must be the next stop; after the last city, the tour closes back to city 0. The goal is the shortest total tour length.

You don't write the tour loop. You write one function that scores the unvisited cities for the current stop, and the simulator moves to the highest-scoring city.

```python
import numpy as np

def pick(city, cities, visited, dist):
    """
    city:    int                              index of the city the traveller is on
    cities:  np.ndarray, shape (n, 2), float  coordinates of every city, in [0, 100]
    visited: np.ndarray, shape (n,), bool     True for cities already in the tour
    dist:    np.ndarray, shape (n, n), float  euclidean distance between every pair of cities
    returns: np.ndarray, shape (n,), float    one FINITE score per city. The highest score among
                                              the UNVISITED cities is visited next; ties go to the
                                              lowest index. Scores of visited cities are ignored
                                              (the simulator overwrites them), but every score
                                              must still be finite.
    """
```

## Rules

- Import only `numpy` and `math`. Anything else, including `typing` and `from __future__ import annotations`, makes the program invalid, so don't add type-hint imports. No file access, no randomness, no state kept between calls.
- Return exactly one finite number per city: no NaN, no infinity.
- `pick` is called once per step — about 119 times per instance — so keep it vectorised with numpy and avoid Python loops over cities.
- The start city is 0 and `visited[0]` is already True; don't assume the starting index anywhere it matters — read `visited`.
- Distances come from `dist`; coordinates are provided in case a rule wants directions, angles or spread instead of raw distance. Everything is deterministic.

## How programs are scored

- Each program tours five families of instances, three instances per family, 120 cities each:
  - `uniform`: coordinates uniform in the square
  - `clustered`: a handful of gaussian clusters
  - `grid`: a jittered lattice
  - `circle`: points on a noisy circle
  - `skewed`: coordinates from a cubed power law, dense near one corner
- For each instance, excess = tour length ÷ lower bound − 1. The lower bound is half the sum, over all cities, of each city's two nearest-neighbour distances: every tour enters and leaves each city once, so no tour can be shorter than this bound.
- **score = −(mean excess across families, in %).** Higher is better; 0 would be perfect.
