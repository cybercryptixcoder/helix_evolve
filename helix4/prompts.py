"""Every prompt the agents see, and the parsers for their replies.

Roles: the Researcher plans experiments (it is the only role that thinks, at `low`, and the only one whose view of
the past changes between conditions); Coders implement one experiment each; the Mutator improves a program with no
history (the wide loop); in Atlas, the Distiller records findings and the Researcher first picks what to open;
in Journal, the Compactor shortens old journal entries.
"""
from __future__ import annotations

import json
import re

RESEARCHER_SYSTEM = """You lead the research in an evolutionary search for better programs. Each generation you plan \
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
    "builds_on": ["<ids of programs{findings} this relies on>"]}}
 ]}}
```
Give exactly {k} experiments."""

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

NAVIGATOR_ASK = """## Before you plan: choose what to open

Above is the map of the search so far. You can open up to {k} items to see them in full before planning: a program \
(its plan, change, diff, code, result, its children, the findings citing it) or a finding (its evidence and its \
linked findings). Open what will most help you choose the next experiments.
Reply with one JSON object and nothing else:
```json
{{"open": ["p0012", "F3"], "why": "one sentence"}}
```"""

DISTILLER_SYSTEM = """You keep the findings of a research programme: short claims about what helps and what hurts, \
each backed by the experiments that show it. You are precise and evidence-bound: a finding says what was changed, \
what happened (in numbers, from the results), and the likely reason. You never invent results; every finding cites \
the program ids it is based on."""

DISTILLER_ASK = """## Your task

Record what generation {gen} taught. Write new findings, and attach this generation's programs as evidence to \
existing findings they bear on. Good findings are specific and reusable: "replacing the uniform start with a \
two-level step (p0031) raised the score from 0.8812 to 0.8855; the f*f top got flatter (1% share 3.1% -> 6.4%)", \
not "p0031 did better". Record failures and their cause too (errors, timeouts, no gain), and open questions worth \
testing. Link findings when one refines, contradicts, requires, or combines with another, or explains it.
Kinds: works (a change that raised the score), fails (a change that didn't, or broke), mechanism (why something \
works), question (worth testing, not yet tested).
Reply with one JSON object and nothing else:
```json
{{"new": [{{"kind": "works", "claim": "...", "evidence": ["p0031"],
           "links": [{{"to": "F3", "type": "refines"}}]}}],
 "evidence": [{{"finding": "F3", "programs": ["p0033"]}}]}}
```
At most 6 new findings. Link types: refines, contradicts, requires, combines-with, explains. Use ids exactly as \
shown."""

COMPACTOR_SYSTEM = """You compress a research journal without losing what matters for the next experiments."""

COMPACTOR_ASK = """Rewrite the older part of the journal below as one summary of at most {chars} characters. Keep: \
what was tried, what worked (with program ids and gains), what failed and why, what the best line is built from, \
and the open questions. Drop repetition and anything that no longer matters. Plain text, no preamble.

{text}"""


# ---------------------------------------------------------------------------------------------- parsing
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


def extract_code(text):
    if not text:
        return None
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    blocks = [b for b in blocks if "def construct" in b]
    if blocks:
        return blocks[-1].strip() + "\n"
    if "def construct" in text and "```" not in text:
        return text.strip() + "\n"
    return None


def extract_summary(text):
    m = re.findall(r"SUMMARY:\s*(.+)", text or "")
    return " ".join(m[-1].split())[:300] if m else ""


def clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 20] + f"\n... ({len(s) - n + 20} more characters)"
