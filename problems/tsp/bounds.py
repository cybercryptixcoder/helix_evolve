"""Family floors for the Researcher's 'room' hints (loop-side interface: HELIX_BOUNDS_MODULE).

This problem does not model a floor/room decomposition, so family_floor returns None and the
loop's message simply omits that section. (The evaluator still reports a per-instance lower bound
in its result JSON, so every score's headroom is queried where it exists: per instance.)
"""


def family_floor(split="train"):
    return None
