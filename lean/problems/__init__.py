"""Problems: the adapter between the core loop (which never changes) and one task.

Each problem is one file defining a class `Problem`. Required:

    name          a short name
    description   everything the agents are told about the problem and the program they write
    code_zero     the program every run starts from
    references    published values, for humans only (never shown to the agents)

and EITHER the three pieces of the standard evaluator (a program returns a NumPy array, run in lean/sandbox.py):

    check(array) -> (x or None, why)      is the result valid (x: the result as it is scored)
    score(x) -> float                     higher is better
    describe(x) -> list of lines          facts about the result, shown back to the agents

OR its own evaluator, for problems that don't fit (the private VRP plug-in, say):

    evaluate(code, start, budget, mem_mb) -> dict with valid, score, feedback (lines), error, cpu, and optionally
        start_score and construction (the result a child of this program starts from; None if programs don't use one)

Optional, with defaults (`setting` below) that reproduce v4's text exactly:

    entry           the function a program must define ("construct")
    title           one line naming the problem (the Atlas's Distiller sees it; default: the name)
    planner_system, coder_system, mutator_system, mutation_planner_system   the system prompts, with the same {k} / {budget} fields
    distiller_ask   the Atlas Distiller's task, with the same {gen} field
    generation_note the line under "# Generation g of G" in the planner's view (budget: the CPU seconds)
    task_note       the end of a coder's or mutator's request: what the program will be given
    clip            how many characters of code each view shows: base, best, inspiration, opened (by the Atlas)
    reply_tokens    room for a coder's or mutator's reply
"""
from __future__ import annotations

import importlib

from lean import prompts as P

DEFAULTS = {
    "entry": "construct",
    "planner_system": P.PLANNER_SYSTEM,
    "coder_system": P.CODER_SYSTEM,
    "mutator_system": P.MUTATOR_SYSTEM,
    "mutation_planner_system": P.MUTATION_PLANNER_SYSTEM,
    "distiller_ask": P.DISTILLER_ASK,
    "generation_note": "Each program gets {budget:.0f} s of CPU and starts from its base's construction.",
    "task_note": "budget_seconds will be {budget:.0f}; `start` will be {whose} construction.",
    # v4 showed 12,000 / 9,000 / 5,000 / 3,500 characters: long programs were rewritten blind (a known bug); never
    # clipped below these
    "clip": {"base": 30000, "best": 12000, "inspiration": 8000, "opened": 3500},
    "reply_tokens": 12000,
}


def setting(problem, key):
    return getattr(problem, key, DEFAULTS[key])


def load(name, **params):
    """A problem in this folder by name ("ac2"), or an adapter anywhere on the path by module ("helix_vrp.lean_adapter")."""
    return importlib.import_module(name if "." in name else f"lean.problems.{name}").Problem(**params)
