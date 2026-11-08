"""Every prompt the agents see, and the parsers for their replies.

The text is v4's (helix4/prompts.py), word for word, so the agents are told exactly what v4 told them. Only the
memory prompts (v4's Distiller, Navigator and Compactor) are absent: the lean core has no memory beyond the archive.
A problem adapter may replace the three system prompts with its own wording (see lean/problems/__init__.py).
"""
from __future__ import annotations

import json
import re

PLANNER_SYSTEM = """You lead the research in an evolutionary search for better programs. Each generation you plan \
{k} experiments. For each one a coder writes a new program by changing a base program you choose; the program runs \
starting from its base's construction, with {budget:.0f} s of CPU, and is scored. Every program ever written is \
kept, in a tree (each points at its base), and any of them can be a base.

You plan; you don't write code. A good plan has one clear idea per experiment, concrete enough for a coder to \
implement without guessing, and a prediction the result can confirm or refute. Spread your bets: refine what is \
working on the strongest line, and also test a genuinely different idea or revisit a promising branch. Don't repeat \
an experiment that has already failed unless you say what is different this time. The goal is the highest score: \
an experiment changes one thing in what the program builds or how it searches, and the program should still use \
its whole budget to push the score, not stop early after a quick probe."""

PLAN_FORMAT = """Reply with one JSON object and nothing else:
```json
{{"analysis": "what the evidence says now and what you are betting on (at most 120 words)",
 "experiments": [
  {{"base": "<program id to build on>", "hypothesis": "why this should raise the score",
    "change": "exactly what the coder should change, concretely", "prediction": "what the result will show",
    "builds_on": ["<ids of programs this relies on>"]}}
 ]}}
```
Give exactly {k} experiments."""

PLAN_RETRY = "\n\n(Your previous reply could not be read. Reply with the JSON object only.)"

CODER_SYSTEM = """You are an expert Python programmer and numerical optimiser. You implement one planned \
experiment as a change to a base program, faithfully, and return the complete new program. The program must define \
construct(budget_seconds, start), finish within its CPU budget with a margin (check time.process_time()), and should \
make use of `start` (the base's construction) when it is given."""

MUTATOR_SYSTEM = """You are an expert Python programmer and numerical optimiser. You improve programs: given one, \
you write a better version, with one substantial change you expect to raise its score from where it starts. The \
program must define construct(budget_seconds, start), finish within its CPU budget with a margin (check \
time.process_time()), and should make use of `start` when it is given."""

CODE_FORMAT = """Reply with the complete program in one ```python block, then one line:
SUMMARY: <what you changed and why, at most 30 words>"""

CODE_RETRY = ("\n\n(Your previous reply had no complete ```python block defining {entry}. Reply with the full "
              "program.)")


def extract_json(text):
    if not text:
        return None
    for m in reversed(re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)):
        try:
            return json.loads(m)
        except ValueError:
            pass
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s: e + 1])
        except ValueError:
            pass
    return None


def extract_code(text, entry="construct"):
    """The last ```python block that defines `entry`; or the whole reply, if it is bare code defining it."""
    if not text:
        return None
    blocks = [b for b in re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S) if f"def {entry}" in b]
    if blocks:
        return blocks[-1].strip() + "\n"
    if f"def {entry}" in text and "```" not in text:
        return text.strip() + "\n"
    return None


def extract_summary(text):
    m = re.findall(r"SUMMARY:\s*(.+)", text or "")
    return " ".join(m[-1].split())[:300] if m else ""


def clip(s, n):
    """At most n characters; a clipped text says how much is missing."""
    s = str(s or "")
    return s if len(s) <= n else s[: n - 20] + f"\n... ({len(s) - n + 20} more characters)"
