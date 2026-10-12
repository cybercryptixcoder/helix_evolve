"""What each agent sees, and how its reply is read back.

System prompts live in helix/prompts/*.md. Each agent's system prompt is its
role file followed by the shared problem statement (problem.md). This module
builds the user message for each call from the current state of the run.

The air gap: the Mutator's prompt is built only from `Scored` objects (code and
a score). It cannot receive a Program, a Hypothesis or the research log.
"""
import difflib
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
def mutator_message(target, others, fresh=False):
    """fresh=False: a variant of `target` (keep its core, one or two bold changes).
    fresh=True: a genuinely different program that beats `target`."""
    if not isinstance(target, Scored) or not all(isinstance(o, Scored) for o in others):
        raise TypeError("the Mutator only receives code and scores (air gap)")
    head = "Best program so far, the score to beat" if fresh else "Program to improve"
    parts = [f"## {head} (score {target.score:.3f})\n\n```python\n{target.code.strip()}\n```"]
    if others:
        parts.append("## Other strong programs" + ("" if fresh else ", for parts you can borrow"))
        parts += [f"### Score {o.score:.3f}\n\n```python\n{o.code.strip()}\n```" for o in others]
    if fresh:
        parts.append(f"This is a **fresh idea** request: write a genuinely different program that scores higher than "
                     f"{target.score:.3f}. Start your reply with the ```python block.")
    else:
        parts.append(f"This is a **variant** request: keep the core of the program to improve and make one or two bold "
                     f"changes so it scores higher than {target.score:.3f}. Start your reply with the ```python block.")
    return "\n\n".join(parts)


def code_only_message(user, cut_off):
    """Retry for a reply that ran out of room before finishing its program. Shows the agent what it had
    written, so the idea it was working towards isn't lost."""
    seen = cut_off.strip()
    if len(seen) > 3000:
        seen = seen[:1500] + "\n[...]\n" + seen[-1500:]
    return (f"{user}\n\n## Your previous reply was cut off\n\nIt ran out of room before the program was complete. "
            f"What you wrote:\n\n<<<\n{seen}\n>>>\n\n"
            "Reply with ONLY the complete program, in a single ```python block, implementing the idea you were "
            "working towards. No text before or after the block.")


def researcher_message(champ, champ_info, ranked, log, plan, generation, gains, lineage=(), parent=None, floor=None):
    """champ_info: {"new", "jump", "real_jump"}; plan: {"cause", "improve", "tuned"}; gains: id -> gain over parent;
    lineage: ids of the champion and its ancestors (knock-outs on an ancestor are inherited); parent: its parent;
    floor: {family: {"lower", "upper"}}, the excess % of the best packing that could exist (helix/bounds.py)."""
    parts = [f"Generation {generation}. Score = −(mean excess %); higher is better."]
    if floor:
        room = {f: champ.families[f] - floor[f]["lower"] for f in floor if f in champ.families}
        parts.append("## Where the room is\nExcess % is measured against a simple bound that no packing can reach. The "
                     "best packing that could possibly exist (even knowing every job in advance) has, by family: "
                     + ", ".join(f"{f} {floor[f]['lower']:.1f}" for f in floor)
                     + ". So the champion's real room to improve, in points of excess, is: "
                     + ", ".join(f"{f} {v:.1f}" for f, v in sorted(room.items(), key=lambda kv: -kv[1]))
                     + ". Aim at the families with the most room, not simply the highest excess.")

    head = f"## The champion: {champ.id}, score {champ.score:.3f} ({champ.branch} branch, generation {champ.generation})"
    if champ_info.get("new") and champ_info.get("jump") is not None:
        if champ_info.get("real_jump"):
            head += (f"\n**New champion: it beat the previous best by {champ_info['jump']:+.3f}.** Find out which new or "
                     "changed parts made the jump (see the diff from its parent), then build on it.")
        else:
            head += (f"\nNew champion by a small margin ({champ_info['jump']:+.3f}): its parts are its parent's, so "
                     "what we know about them still holds. Spend the tests on improving it.")
    parts.append(f"{head}\nExcess % by family: {format_families(champ.families)}\n\n```python\n{champ.code.strip()}\n```")
    if parent is not None and parent.code.strip() != champ.code.strip():
        diff = code_diff(parent.code, champ.code)
        if diff:
            parts.append(f"### What changed from its parent {parent.id} (score {parent.score:.3f})\n\n```diff\n{diff}\n```")

    lineage = list(lineage) or [champ.id]
    order = {pid: i for i, pid in enumerate(lineage)}
    knockouts = [h for h in log if h.kind == "cause" and h.base_id in order and h.verdict not in ("pending", "invalid")]
    knockouts.sort(key=lambda h: (order[h.base_id], h.id))
    parts.append("## What we know about the champion's parts (knock-outs: score change when the part is removed)")
    if knockouts:
        def ko_line(h):
            where_from = "" if h.base_id == champ.id else f" (inherited from ancestor {h.base_id})"
            if h.delta is None:
                return f"- {h.id}{where_from}: {h.change} → {h.verdict}"
            hurt = sorted(h.family_shift.items(), key=lambda kv: kv[1], reverse=True)[:2]
            where = ", ".join(f"{f} {v:+.2f}" for f, v in hurt if v > 0)
            return (f"- {h.id}{where_from}: {h.change} → score {h.delta:+.3f} [{h.verdict}]"
                    + (f"; excess rose most on {where}" if where else ""))
        parts.append("\n".join(ko_line(h) for h in knockouts[:12]))
    else:
        parts.append("(no knock-outs on this champion or its ancestors yet)")
    acted_on = {h.builds_on for h in log if h.builds_on}
    open_findings = [h for h in knockouts if h.verdict in ("matters", "removal-helps") and h.id not in acted_on]
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
        ask.append(f"- {plan['cause']} **cause** tests: knock out one part of {champ.id} each, choosing parts that are "
                   "new or changed since its parent and not knocked out yet (inherited knock-outs already cover the rest).")
    ask.append(f"- {plan['improve']} **improve** tests: change a mechanism of {champ.id}: add a property of the bins or a "
               "new term, change the functional form of a part that matters, change the rule for opening a new bin, "
               "or transplant a part from another strong program"
               + (". Follow up the open findings above, and aim at the families where the excess is highest" if open_findings
                  else ". Aim at the families where the excess is highest") + ".")
    if plan.get("tuned"):
        ask.append("Don't propose a test that only moves a number: the champion's constants are tuned automatically "
                   "every generation, and the numbers on any line you add or change are tuned before your test is "
                   "judged.")
    if plan.get("stuck"):
        ask.append(f"**The best score hasn't moved for {plan['stall']} generations.** Small edits to {champ.id} are "
                   "exhausted (see the log). Make at least half of the improve tests bold: a new mechanism the "
                   "champion lacks, a different rule for opening a new bin, rebuilding one part from scratch, or "
                   "developing another strong program (a different lineage) instead of the champion.")
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
        "Fix the error and keep the idea the same. Reply with the complete fixed program in a single "
        "```python block, then at most one sentence."
    )


# ---------------------------------------------------------------- formatting
def format_families(families):
    return " | ".join(f"{f} {v:.2f}" for f, v in families.items()) if families else "n/a"


def format_hypothesis(h):
    line = f"- {h.id} {h.kind} on {h.base_id}" + (f" (builds on {h.builds_on})" if h.builds_on else "") + f": [{h.verdict}"
    if h.delta is not None:
        line += f", {h.delta:+.3f}"
    line += "]"
    if getattr(h, "raw_delta", None) is not None and h.delta is not None and h.raw_delta != h.delta:
        line += f" (as written {h.raw_delta:+.3f}; after tuning its new numbers {h.delta:+.3f})"
    line += f" claim: {h.claim} | change: {h.change}"
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
    """The agent's own short description: the text before the first code block, or, for a reply that
    starts with its code, the text after the last one. Trimmed."""
    head = text.split("```", 1)[0].strip()
    if not head and text.count("```") >= 2:
        head = text.rsplit("```", 1)[1].strip()
    head = re.sub(r"^\s*(\d\.|-|\*)\s*", "", head)
    return " ".join(head.split())[:300]


def code_diff(old, new, limit=40):
    """The changed lines between two programs (- old, + new), at most `limit` lines."""
    lines = [line for line in difflib.unified_diff(old.strip().splitlines(), new.strip().splitlines(), lineterm="", n=0)
             if not line.startswith(("---", "+++", "@@"))]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit} more changed lines)"]
    return "\n".join(lines)


def extract_hypotheses(text, valid_ids, fallback_id):
    """Parse the Researcher's JSON. Unknown base ids fall back to the best program. A reply cut off
    part-way through the JSON still yields the hypotheses it finished."""
    candidates = [body for lang, body in _FENCE.findall(text) if lang.lower() in ("json", "")]
    candidates.append(text[text.find("{"): text.rfind("}") + 1] if "{" in text else "")
    parsed = []
    for raw in candidates:
        try:
            parsed.append(json.loads(raw))
        except (json.JSONDecodeError, ValueError):
            continue
    parsed.append({"hypotheses": _complete_objects(text)})
    for data in parsed:
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


def _complete_objects(text):
    """Every complete, parseable {...} object in `text` that looks like a hypothesis (has a claim)."""
    out, stack, in_str, esc = [], [], False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            begin = stack.pop()
            try:
                obj = json.loads(text[begin:i + 1])
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict) and "claim" in obj:
                out.append(obj)
    return out
