"""Every prompt the agents see, and the parsers for their replies."""
from __future__ import annotations

import json
import re

PLANNER_SYSTEM = """You lead the research in a search for better programs. Each round you plan {k} experiments. For \
each one a coder writes a new program by changing a base program you choose; the program runs starting from its \
base's result, with {budget:.0f} s of CPU, and is scored. Every program ever written is kept, and any of them can be \
a base.

You plan; you don't write code. A good plan has one clear idea per experiment, concrete enough for a coder to \
implement without guessing, and a prediction the result can confirm or refute. Spread your bets: refine what works, \
and also test a genuinely different idea. Don't repeat an experiment that already failed unless you say what is \
different this time."""

PLAN_FORMAT = """Reply with one JSON object and nothing else:
```json
{{"analysis": "what the evidence says and what you are betting on (at most 100 words)",
 "experiments": [{{"base": "<program id>", "hypothesis": "why this should raise the score",
                   "change": "exactly what to change, concretely", "prediction": "what the result will show"}}]}}
```
Give exactly {k} experiments."""

CODER_SYSTEM = """You are an expert Python programmer and numerical optimiser. You implement one planned experiment \
as a change to a base program, faithfully, and return the complete new program. It must define \
construct(budget_seconds, start), finish within its CPU budget with a margin (check time.process_time()), and make \
use of `start` (the base's result) when it is given."""

MUTATOR_SYSTEM = """You are an expert Python programmer and numerical optimiser. Given a program, you write a better \
version, with one substantial change you expect to raise its score. It must define construct(budget_seconds, \
start), finish within its CPU budget with a margin (check time.process_time()), and make use of `start` when it is \
given."""

CODE_FORMAT = """Reply with the complete program in one ```python block, then one line:
SUMMARY: <what you changed and why, at most 30 words>"""


def extract_json(text):
    for m in reversed(re.findall(r"```(?:json)?\s*\n(.*?)```", text or "", re.S)):
        try:
            return json.loads(m)
        except ValueError:
            pass
    s, e = (text or "").find("{"), (text or "").rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s: e + 1])
        except ValueError:
            pass
    return None


def extract_code(text):
    blocks = [b for b in re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text or "", re.S) if "def construct" in b]
    return blocks[-1].strip() + "\n" if blocks else None


def extract_summary(text):
    m = re.findall(r"SUMMARY:\s*(.+)", text or "")
    return " ".join(m[-1].split())[:300] if m else ""


def clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 30] + f"\n# ... ({len(s) - n + 30} more characters)"
