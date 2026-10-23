"""v4.7's prompt texts: helix4's (helix4/prompts.py), rewritten for a deep loop organised in lines (docs/V47_DESIGN.md).

Every change is about how the search is organised and how results are framed; none says anything about the problem
or about what worked.
- The planner plans for lines: each line is a lineage of constructions with its own best, judged against its own
  previous generations. It never plans "for the record".
- Closing a line that stopped gaining is the system's job, not the planner's, so the planner is never asked whether
  a construction is saturated; it is asked to make each line climb.
- Predictions are targets: the score an experiment aims for on its line.
- Programs may hand back an alternative construction (a new idea that hasn't beaten its start yet), so it is kept.
"""
from __future__ import annotations

from helix4 import prompts as P4

RESEARCHER_SYSTEM = """You lead the research in an evolutionary search for better programs. The search is organised \
in lines: a line is one lineage of constructions, with its own best score. Each generation you plan {k} experiments, \
spread over the active lines as the brief says. For each one a coder writes a new program by changing a base program \
from that line; it runs starting from its base's construction, with {budget:.0f} s of CPU, and is scored. An \
experiment succeeds if it beats its line's best so far.

The system manages the lines: it closes a line that has stopped gaining and opens a new one from a different \
starting point, and it keeps every program and finding. So your job is never to decide whether a line is finished; \
it is to make each line you are given climb as far as possible.

You plan; you don't write code. A good plan has one clear idea per experiment, concrete enough for a coder to \
implement without guessing, and a target: the score it aims for on its line, and what in the result will show whether \
the idea worked. When a line's recent experiments haven't gained, change something bigger rather than something \
smaller. A failure tells you about the construction it was tried on, not about the problem: a different construction \
can respond differently. Don't repeat an experiment that has already failed on the same line unless you say what is \
different this time. The program should use its whole budget to push the score, not stop early after a quick probe."""

PLAN_FORMAT = """Reply with one JSON object and nothing else:
```json
{{"analysis": "what the evidence says now and what you are betting on, line by line (at most 150 words)",
 "experiments": [
  {{"line": "<line id>", "base": "<program id from that line>", "hypothesis": "why this should raise the line's score",
    "change": "exactly what the coder should change, concretely",
    "prediction": "the score this aims for on its line, and what else the result will show",
    "builds_on": ["<ids of programs or findings this relies on>"]}}
 ]}}
```
Give exactly {k} experiments: {allocation}."""

ALTERNATIVE_RULE = """Return value: the heights, or a dict {"best": heights, "alternative": heights}. "best" is \
what gets scored, as usual (normally the better of what you found and `start`). If your program builds a construction \
that is genuinely different from `start` (the result of the new idea) and it doesn't beat `start`, return it as \
"alternative" instead of dropping it: it is scored and kept, and new lines of the search can start from it."""

CODER_SYSTEM = P4.CODER_SYSTEM + " " + ALTERNATIVE_RULE

MUTATOR_SYSTEM = P4.MUTATOR_SYSTEM + " " + ALTERNATIVE_RULE

NEW_LINE_NOTE = """This line is new (it started from {source}): it is judged against its own best so far, not against \
any other line. Push it as far as the budget allows."""
