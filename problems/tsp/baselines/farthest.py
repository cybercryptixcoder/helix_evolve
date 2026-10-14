"""Baseline: farthest next — deliberately bad, useful as a floor."""
import numpy as np


def pick(city, cities, visited, dist):
    return dist[city]
