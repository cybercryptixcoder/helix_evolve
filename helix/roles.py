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


def researcher_message(ranked, log, n_hypotheses, generation):
    parts = [f"Generation {generation}. Score = −(mean excess %); higher is better.", "## Programs, best first"]
    for p in ranked:
        origin = p.branch + (f", from {p.parent_id}" if p.parent_id else "")
        parts.append(
            f"### Program {p.id} — score {p.score:.3f} ({origin})\n"
            f"Excess % by family: {format_families(p.families)}\n\n```python\n{p.code.strip()}\n```"
        )
    parts.append("## Research log (oldest first)")
    shown = [h for h in log if h.verdict != "pending"][-LOG_SHOWN:]
    parts.append("\n".join(format_hypothesis(h) for h in shown) if shown else "(nothing tested yet)")
    parts.append(f"Propose exactly {n_hypotheses} hypotheses. Use program ids exactly as written above.")
    return "\n\n".join(parts)


def coder_message(base, h):
    return (
        f"## Base program {base.id} (score {base.score:.3f})\n"
        f"Excess % by family: {format_families(base.families)}\n\n```python\n{base.code.strip()}\n```\n\n"
        f"## Hypothesis\n\nClaim: {h.claim}\n\nChange to make: {h.change}\n\nPrediction: {h.prediction}\n\n"
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
    line = f"- {h.id} on {h.base_id}: [{h.verdict}"
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
            out.append({
                "base": base if base in valid_ids else fallback_id,
                "claim": claim,
                "change": change,
                "prediction": str(item.get("prediction", "")).strip(),
            })
        if out:
            return out
    return []
