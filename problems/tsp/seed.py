"""The starting program for this problem: nearest neighbour.

Walk to the nearest unvisited city every step. This is the tour-problem analogue of Code Zero:
simple, always valid, and the thing any evolved program must beat.
"""
import numpy as np


def pick(city, cities, visited, dist):
    """Score = -distance from the current city, so the nearest unvisited city wins."""
    return -dist[city]
