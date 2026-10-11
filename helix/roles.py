"""What each agent sees, and how its reply is read back.

System prompts live in helix/prompts/*.md. Each agent's system prompt is its
role file followed by the shared problem statement (problem.md). This module
builds the user message for each call from the current state of the run.

The air gap: the Mutator's prompt is built only from `Scored` objects (code and
a score). It cannot receive a Program, a Hypothesis or the research log.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / "prompts"
LOG_SHOWN = 30          # how many recent hypotheses the Researcher sees


def system_prompt(role):
    """mutator | researcher | coder | zeroshot → role prompt + shared problem statement."""
    return (PROMPTS / f"{role}.md").read_text().strip() + "\n\n" + (PROMPTS / "problem.md").read_text().strip()


@dataclass(frozen=True)
class Scored:
    """Everything the Mutator is allowed to know about a program."""
    code: str
    score: float


# ---------------------------------------------------------------- user messages
def mutator_message(target, others):
    if not isinstance(target, Scored) or not all(isinstance(o, Scored) for o in others):
        raise TypeError("the Mutator only receives code and scores (air gap)")
    parts = [f"## Program to improve (score {target.score:.3f})\n\n```python\n{target.code.strip()}\n```"]
    if others:
        parts.append("## Other strong programs, for ideas")
        parts += [f"### Score {o.score:.3f}\n\n```python\n{o.code.strip()}\n```" for o in others]
    parts.append("Write one new program that scores higher than the program to improve.")
    return "\n\n".join(parts)


def researcher_message(champ, champ_info, ranked, log, plan, generation, gains):
    """champ_info: {"new": bool, "jump": float|None}; plan: {"cause": n, "improve": n}; gains: id -> gain over parent."""
    parts = [f"Generation {generation}. Score = −(mean excess %); higher is better."]

    head = f"## The champion: {champ.id}, score {champ.score:.3f} ({champ.branch} branch, generation {champ.generation})"
    if champ_info.get("new") and champ_info.get("jump") is not None:
        head += f"\n**New champion: it beat the previous best by {champ_info['jump']:+.3f}.** Find out why, then build on it."
    parts.append(f"{head}\nExcess % by family: {format_families(champ.families)}\n\n```python\n{champ.code.strip()}\n```")

    knockouts = [h for h in log if h.kind == "cause" and h.base_id == champ.id and h.verdict != "pending"]
    parts.append("## What we know about the champion's parts (knock-outs: score change when the part is removed)")
    if knockouts:
        def ko_line(h):
            if h.delta is None:
                return f"- {h.id}: {h.change} → {h.verdict}"
            hurt = sorted(h.family_shift.items(), key=lambda kv: kv[1], reverse=True)[:2]
            where = ", ".join(f"{f} {v:+.2f}" for f, v in hurt if v > 0)
            return f"- {h.id}: {h.change} → score {h.delta:+.3f} [{h.verdict}]" + (f"; excess rose most on {where}" if where else "")
        parts.append("\n".join(ko_line(h) for h in knockouts))
    else:
        parts.append("(no knock-outs on this champion yet)")
    acted_on = {h.builds_on for h in log if h.builds_on}
    open_findings = [h for h in log if h.kind == "cause" and h.verdict in ("matters", "removal-helps")
                     and h.base_id == champ.id and h.id not in acted_on]
    if open_findings:
        parts.append("Findings not acted on yet (aim improve tests at these): "
                     + ", ".join(f"{h.id} ({h.delta:+.3f})" for h in open_findings))

    parts.append("## Other candidate programs, best first")
    others = [p for p in ranked if p.id != champ.id]
    for p in others:
        origin = p.branch + (f", from {p.parent_id}" if p.parent_id else "")
        gain = f", {gains[p.id]:+.3f} over its parent" if gains.get(p.id) is not None else ""
        parts.append(f"### Program {p.id}: score {p.score:.3f} ({origin}{gain})\n"
                     f"Excess % by family: {format_families(p.families)}\n\n```python\n{p.code.strip()}\n```")
    if not others:
        parts.append("(none)")

    parts.append("## Research log (oldest first)")
    shown = [h for h in log if h.verdict != "pending"][-LOG_SHOWN:]
    parts.append("\n".join(format_hypothesis(h) for h in shown) if shown else "(nothing tested yet)")

    total = plan["cause"] + plan["improve"]
    ask = [f"## Plan for this generation\nPropose exactly {total} hypotheses:"]
    if plan["cause"]:
        ask.append(f"- {plan['cause']} **cause** tests: knock out one part of {champ.id} each, choosing parts not knocked out yet.")
    ask.append(f"- {plan['improve']} **improve** tests: moderate changes to the parts of {champ.id} that matter most"
               + (", following up the open findings above" if open_findings else "")
               + ", or a transplant between the champion and another strong program.")
    ask.append("Use program ids exactly as written above. Put the JSON block first.")
    parts.append("\n".join(ask))
    return "\n\n".join(parts)


def coder_message(base, h):
    kind = ("**cause** (knock-out): remove or neutralise exactly this part, nothing else"
            if h.kind == "cause" else "**improve**: make exactly this moderate change, nothing else")
    return (
        f"## Base program {base.id} (score {base.score:.3f})\n"
        f"Excess % by family: {format_families(base.families)}\n\n```python\n{base.code.strip()}\n```\n\n"
        f"## Hypothesis ({kind})\n\nClaim: {h.claim}\n\nChange to make: {h.change}\n\nPrediction: {h.prediction}\n\n"
        "Make exactly this change to the base program."
    )


def zeroshot_message():
    return "Write your program now."


def repair_message(code, error):
    return (
        f"Your program failed when it was scored:\n\n```\n{error.strip()}\n```\n\n"
        f"Here is the program:\n\n```python\n{code.strip()}\n```\n\n"
        "Fix the error and keep the idea the same. Reply in the same format as before: "
        "one sentence, then the complete program in a single ```python block."
    )


# ---------------------------------------------------------------- formatting
def format_families(families):
    return " | ".join(f"{f} {v:.2f}" for f, v in families.items()) if families else "n/a"


def format_hypothesis(h):
    line = f"- {h.id} {h.kind} on {h.base_id}" + (f" (builds on {h.builds_on})" if h.builds_on else "") + f": [{h.verdict}"
    if h.delta is not None:
        line += f", {h.delta:+.3f}"
    line += f"] claim: {h.claim} | change: {h.change}"
    if h.family_shift:
        moved = sorted(h.family_shift.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        line += " | excess moved: " + ", ".join(f"{f} {v:+.2f}" for f, v in moved)
    return line


# ---------------------------------------------------------------- reading replies
_FENCE = re.compile(r"```([a-zA-Z0-9_+-]*)\s*\n(.*?)```", re.S)


def extract_code(text):
    """The last fenced code block that defines priority(); None if there isn't one."""
    blocks = [body for _, body in _FENCE.findall(text) if "def priority" in body]
    if blocks:
        return blocks[-1].strip() + "\n"
    if "def priority" in text and "```" not in text:
        return text.strip() + "\n"
    return None


def extract_note(text):
    """The agent's own short description: the text before the first code block, trimmed."""
    head = text.split("```", 1)[0].strip()
    head = re.sub(r"^\s*(\d\.|-|\*)\s*", "", head)
    return " ".join(head.split())[:300]


def extract_hypotheses(text, valid_ids, fallback_id):
    """Parse the Researcher's JSON. Unknown base ids fall back to the best program."""
    candidates = [body for lang, body in _FENCE.findall(text) if lang.lower() in ("json", "")]
    candidates.append(text[text.find("{"): text.rfind("}") + 1] if "{" in text else "")
    for raw in candidates:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data.get("hypotheses", []) if isinstance(data, dict) else data
        out = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            claim, change = str(item.get("claim", "")).strip(), str(item.get("change", "")).strip()
            if not claim or not change:
                continue
            base = str(item.get("base", "")).strip()
            kind = str(item.get("kind", "improve")).strip().lower()
            out.append({
                "base": base if base in valid_ids else fallback_id,
                "claim": claim,
                "change": change,
                "prediction": str(item.get("prediction", "")).strip(),
                "kind": "cause" if kind.startswith("cause") or "knock" in kind else "improve",
                "builds_on": str(item.get("builds_on") or "").strip(),
            })
        if out:
            return out
    return []
