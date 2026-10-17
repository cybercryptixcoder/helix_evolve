"""Messages for the agents, and parsing their replies. System prompts come from the strategy folder; the
problem's description is appended to every system prompt so the long, unchanging part is cached."""
from __future__ import annotations

import json
import re

CONTRACT = """## A feature

```python
import numpy as np

def {signature}:
    \"\"\"One line: exactly what this measures.\"\"\"
    ...
    return values   # one number per candidate
```

{signature_doc}
- Import only `numpy` and `math`. No state between calls, no randomness, don't modify the inputs, no Python loops over candidates when a vectorised form exists (features run thousands of times per evaluation). Guard every division and log.
- Return finite numbers, roughly in [-1, 1] (normalise; the optimiser rescales anyway).

## How the policy works

priority(candidate) = w1 * feature1 + w2 * feature2 + ...; the highest priority wins; on a tie, the first candidate wins. With no features every candidate scores 0, so the first candidate always wins: that is **Code Zero**, the starting point (0% progress). An optimiser fits the weights, including their signs. A new feature is kept only if the policy does better with it than the same refit without it, on training instances *and* on separate validation instances, and the gain isn't already given by the kept features.

## How policies are scored

Per instance, the **gap** is how far the solution is above a reference (lower is better). The score is the mean gap over families. **Progress** is the share of the way from Code Zero (0%) to the best reachable (100%)."""


def system_prompt(strategy, role, problem, space="features"):
    """method (strategy/prompts/<role>.md) + domain addendum (strategy/prompts/<space>/<role>.md) + the problem."""
    contract = CONTRACT.format(signature=problem.signature, signature_doc=problem.signature_doc)
    addendum = strategy.addenda.get(space, {}).get(role, "").strip()
    return (f"{strategy.prompts[role].strip()}\n\n{addendum}\n\n# The problem: {problem.title}\n\n"
            f"{problem.description.strip()}\n\n{contract}")


def extract_json(text):
    """The first JSON object in a reply (fenced or bare); None if there isn't one."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cands = [m.group(1)] if m else []
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    cands.append(text[start:i + 1])
                    break
    for c in cands:
        try:
            return json.loads(c)
        except ValueError:
            try:
                return json.loads(re.sub(r",\s*([}\]])", r"\1", c))
            except ValueError:
                continue
    return None


def after_json(text, limit=900):
    """The prose after the JSON block (the agent's analysis)."""
    if not text:
        return ""
    parts = text.split("```")
    tail = parts[-1] if len(parts) >= 3 else ""
    return tail.strip()[:limit]


def before_json(text, limit=1200):
    """Prose before the JSON block (reasoning written out when thinking is off)."""
    if not text:
        return ""
    i = text.find("```")
    j = text.find("{")
    cut = min(x for x in (i, j, len(text)) if x >= 0)
    return text[:cut].replace("Reasoning:", "").strip()[:limit]


def extract_name(text, default):
    m = re.search(r"name:\s*`?([A-Za-z_][A-Za-z0-9_]*)", (text or "").split("```")[-1])
    return m.group(1)[:48] if m else default


def short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def gain(v, d=3):
    return "—" if v is None else f"{v:+.{d}f}"


def feature_line(f, with_code=False, max_code=900):
    """One ledger line about a feature: what its code measures and what happened to it."""
    bits = [f"**{f.id} {f.name}** ({f.origin}{', ' + f.kind if f.kind else ''}{', approach ' + f.node if f.node else ''}, gen {f.gen})"]
    bits.append(f"measures: {short(f.measures or f.idea.get('feature', ''), 180)}")
    if f.status == "duplicate":
        bits.append(f"DUPLICATE of {f.duplicate_of} (ranks candidates the same way); not evaluated")
    elif f.status in ("inert", "span"):
        bits.append(f"certified {f.status}: {f.certificate}")
    elif f.status == "invalid":
        bits.append(f"invalid: {short(f.error, 140)}")
    else:
        if f.probe:
            pr = ", ".join(f"w{w:+g}: {gain(d, 2)}" for w, d in f.probe)
            bits.append(f"probe alone on top of the champion [{pr}]")
        if f.d_valid is not None:
            bits.append(f"trial: train {gain(f.d_train)}, validation {gain(f.d_valid)}")
        if f.status in ("kept", "retired"):
            sign = "+" if (f.weights and f.weights[0] >= 0) else "−"
            bits.append(f"KEPT (fitted sign {sign})" + (f", retired gen {f.retired_gen}" if f.retired_gen else ""))
        else:
            bits.append(f"verdict: {f.verdict or f.status}")
    p = f.prediction
    if p.get("metric"):
        bits.append(f"prediction {p.get('family')}/{p.get('metric')} {p.get('direction')}: "
                    f"{p.get('before')} → {p.get('after')} = {'HELD' if p.get('held') else 'did not hold'}")
    out = "- " + "; ".join(bits)
    if with_code and f.code:
        out += "\n```python\n" + f.code.strip()[:max_code] + "\n```"
    return out


def scoreboard_line(f):
    """What the Mutator may see: code and scores, never hypotheses."""
    if f.status == "kept":
        tag = f"in the policy, validation gain {gain(f.d_valid)}"
    elif f.d_valid is not None:
        tag = f"validation gain {gain(f.d_valid)} ({f.verdict})"
    elif f.best_probe is not None:
        tag = f"rejected: best gain {gain(f.best_probe, 2)}"
    elif f.status == "duplicate":
        tag = "a duplicate"
    else:
        tag = f.status
    return f"- `{f.name}`: {short(f.measures, 140)} → {tag}"
