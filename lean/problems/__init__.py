"""Problems. Each is one file defining a class `Problem` with:

    name, description (what the agents are told), code_zero (the trivial starting program),
    check(array) -> (x or None, why), score(x) -> float (higher is better), describe(x) -> list of fact lines,
    references (published values, shown to humans only, never to the agents).
"""
from __future__ import annotations

import importlib


def load(name, **params):
    return importlib.import_module(f"lean.problems.{name}").Problem(**params)
