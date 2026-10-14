"""Baseline: visit cities in input order (the tour-problem analogue of first-fit)."""
import numpy as np


def pick(city, cities, visited, dist):
    return -np.arange(len(cities), dtype=float)
