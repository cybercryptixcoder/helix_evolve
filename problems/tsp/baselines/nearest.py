"""Baseline: nearest neighbour (same policy as the seed)."""
import numpy as np


def pick(city, cities, visited, dist):
    return -dist[city]
