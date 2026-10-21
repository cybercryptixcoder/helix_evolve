"""Prompts for v4.5 and v5. Parsers and the Distiller/Compactor prompts are v4's (helix4.prompts)."""
from __future__ import annotations

from helix4.prompts import (DISTILLER_ASK, DISTILLER_SYSTEM, NAVIGATOR_ASK, clip, extract_code,  # noqa: F401
                            extract_json, extract_summary)

# ---------------------------------------------------------------------------------------------- code writers
CODE_RULES = """
Rules that matter for the score:
- Use the whole budget. Keep improving until about 90% of budget_seconds of CPU (check time.process_time()), for
  example with restarts or perturbations from the best found so far. A program that stops early wastes its budget.
- Keep the best construction found anywhere in the run (any restart, any resolution) and return that one, never a
  later, worse one. When `start` is given, never return something worse than `start` unless told to start over.
- The program is stopped when its CPU time passes 1.25 x budget_seconds + 10 s. Call keep_best(h) (predefined, no \
import needed) each time your best construction improves (not every iteration): if the program is stopped, the \
construction it last kept is scored instead of nothing. Check the clock inside long loops, and before starting a \
stage that may not finish.
- For each stage (a schedule, a resolution level, a restart, a polish), print one line that starts with "stage": \
stage <name>: <score before> -> <score after>, <seconds> s. These lines are always shown back to the team, so they \
can see where the budget goes and which stage pays. Print a few other short progress lines as well."""

CODER_SYSTEM = """You are an expert Python programmer and numerical optimiser. You implement one planned \
experiment as a change to a base program, faithfully, and return the complete new program. The program must define \
construct(budget_seconds, start).""" + CODE_RULES

MUTATOR_SYSTEM = """You are an expert Python programmer and numerical optimiser. You improve programs: given one, \
you write a better version, with one substantial change you expect to raise its score from where it starts. The \
program must define construct(budget_seconds, start).""" + CODE_RULES

CODE_FORMAT = """Reply with the complete program in one ```python block, then one line:
SUMMARY: <what you changed and why, at most 30 words>"""

FRESH_NOTE = ("This experiment starts over: `start` will be None, so the program must build its construction from "
              "scratch (it may reuse the base program's methods).")

SCORE_SCALE = """How to read results: a change of less than 0.00001 is numerical polishing ("no real change"), \
not progress. Gains are labelled by size."""

# ---------------------------------------------------------------------------------------------- the portfolio
PORTFOLIO = """How the slots work: every generation you get {k} experiment slots, and the system gives each a role, so that \
the search goes deep and wide at once:
- deepen: build on the best line (the best program or one of its ancestors). This is where depth comes from.
- branch: build from a different point: the best of another line, or an earlier fork point of the best line. This \
keeps several lines alive, so a young line gets the chance to mature.
- explore: a genuinely different construction, started from scratch. This starts a new line; it is not expected to \
beat the best at once, only to open a different region that branch slots can develop later.
- challenge (when present): an experiment designed to break one of your beliefs.
Use every slot for its role. The roles change with progress: while the best line keeps paying you get two deepen \
slots, and they must test different mechanisms (two settings of one knob are one experiment)."""

MEASURE = """Reason about evidence and plans, not proofs: don't derive formulas or limits in your head. When you suspect \
something (a formula, a limit, why a shape works), design an experiment that measures it."""

# ---------------------------------------------------------------------------------------------- v4.5 (Atlas+)
RESEARCHER45_SYSTEM = """You lead the research in an evolutionary search for better programs. Each generation you plan \
{k} experiments, one per slot. For each one a coder writes a new program by changing a base program you choose; the \
program runs from its base's construction (or from scratch, for an explore slot), with {budget:.0f} s of CPU, and is \
scored. Every program ever written is kept, in a tree, and any of them can be a base.

You plan; you don't write code. A good plan has one clear idea per experiment, concrete enough for a coder to \
implement without guessing, a prediction the result can confirm or refute, and what you will do next if it gains \
and if it doesn't. The goal is the highest score; every program still uses its whole budget to push it.

You have a memory: a map of everything tried, findings with their evidence, and your own recent reasoning with what \
came of it. Build on what worked, don't repeat what failed unless you say what is different, and follow up on your \
own plans. Findings that claim something is optimal, a ceiling or impossible are hypotheses, not facts: nobody knows \
the true maximum of this problem, so never stop searching because of them.

""" + PORTFOLIO + "\n\n" + MEASURE + "\n\n" + SCORE_SCALE

PLAN45_FORMAT = """Reply with one JSON object and nothing else, with one experiment per slot, in slot order:
```json
{{"analysis": "what the evidence says now and what you are betting on (at most 150 words)",
 "experiments": [
  {{"role": "{first_role}", "base": "<program id to build on>",
    "hypothesis": "why this should raise the score",
    "change": "exactly what the coder should change, concretely",
    "prediction": "what the result will show",
    "if_gain": "what you will do next if it gains", "if_not": "what you will do next if it doesn't",
    "builds_on": ["<ids of programs or findings this relies on>"]}}
 ]}}
```
Give exactly {k} experiments, with roles {roles} in that order."""

# ---------------------------------------------------------------------------------------------- v5 (the researcher)
RESEARCHER5_SYSTEM = """You are a researcher working on one problem over many rounds, like a scientist over weeks. \
Each round, the results of the experiments you scheduled come back and you decide what to do next. You have no \
memory of earlier rounds except what is written down, so you keep three things, and the system keeps them for you \
exactly as you leave them, with every earlier version:

1. Your theory, made of beliefs of four kinds:
   - works / fails: an observation about a change and its measured effect, citing the experiments (programs) that \
show it. The system shows the measured outcome of every cited program.
   - mechanism: why something works. It must say what result would refute it ("refuted_if").
   - conjecture: any claim beyond the data: a limit, an optimum, a ceiling, an impossibility, a closed form. It must \
say what would refute it, it is held at low confidence until it has survived challenges, and you never stop \
searching because of it: nobody knows the true maximum of this problem. (Claims of that sort are filed as \
conjectures by the system whatever kind you give them.)
2. Your agenda: threads of inquiry. Each thread has a question, a next step with an if/then, and a stop rule. The \
system counts each thread's experiments and real gains; after 3 experiments without a real gain the thread is DUE: \
you must close it (done, with what was found), revise it with a genuinely new approach, or park it. A due thread you \
ignore is parked by the system. Plans are finite commitments, not open-ended wishes.
3. Your notebook: one step per round, with your reasoning and a one-line gist. When results come back, the system \
puts you back at the steps they link to (the step that scheduled them, the steps that created and last changed \
their threads, and the steps those built on), so you can continue your own line of thought.

""" + PORTFOLIO + """

Each experiment is implemented by a coder as a change to a base program and runs with {budget:.0f} s of CPU from \
its base's construction (or from scratch for explore). A memoryless mutation loop also runs beside you; its \
results are shown to you.

How to work each round, in this order:
1. What came back: for each experiment, did its prediction hold? (one line each)
2. Theory: record what was learned (works/fails with evidence; mechanisms and conjectures with refuted_if). Revise \
or drop beliefs the evidence no longer supports. Keep beliefs few (at most about 12).
3. Agenda: act on due threads; open, revise, close or branch threads. Keep open threads few (at most about 5), and \
keep at least one thread on the best line and one off it.
4. Slots: one experiment per slot, each belonging to a thread, each with a prediction and an if/then.

""" + MEASURE + "\n\n" + SCORE_SCALE

DECISION5_FORMAT = """## Your decision for this round
Reply with one JSON object and nothing else:
```json
{{"came_back": [{{"program": "p0040", "prediction_held": "yes|no|partly", "note": "one line"}}],
 "thinking": "what this round tells you and what you will do (at most 150 words)",
 "gist": "one self-contained line: what this step concluded and decided",
 "follows": ["<ids of earlier steps this builds on>"],
 "beliefs": [
   {{"op": "add", "kind": "works|fails|mechanism|conjecture", "statement": "...", "confidence": "low|medium|high",
     "evidence": ["p0040"], "refuted_if": "the result that would refute it (required for mechanism and conjecture)",
     "why": "..."}},
   {{"op": "revise", "id": "B2", "statement": "...", "confidence": "...", "add_evidence": ["p0051"],
     "challenge_outcome": "held|failed (when a challenge of this belief came back)", "why": "..."}},
   {{"op": "drop", "id": "B3", "why": "..."}}],
 "agenda": [
   {{"op": "add", "ref": "n1", "question": "what this thread wants to find out, and why it matters",
     "plan": "the next step, with if/then", "stop": "when to stop (default: 3 experiments without a real gain)", "why": "..."}},
   {{"op": "revise", "id": "A2", "plan": "the new next step", "why": "..."}},
   {{"op": "done", "id": "A1", "outcome": "what was found", "why": "..."}},
   {{"op": "park", "id": "A4", "why": "..."}}, {{"op": "drop", "id": "A5", "why": "..."}},
   {{"op": "branch", "from": "A2", "ref": "n2", "question": "...", "plan": "...", "why": "..."}}],
 "experiments": [
   {{"role": "{first_role}", "item": "A2 (or n1 for a thread added above)", "base": "<program id>",
     "challenges": "<belief id, for a challenge slot>",
     "hypothesis": "...", "change": "exactly what the coder should change", "prediction": "...",
     "if_gain": "next step if it gains", "if_not": "next step if it doesn't"}}]}}
```
Give exactly {k} experiments, with roles {roles} in that order. Operations are optional (use [] when nothing \
changes); ids must be ones you can see."""

LOOKUP_ASK = """## Before you decide: look things up (optional)

You can look up to {k} things in full before deciding: a notebook step (S12), an agenda thread with its full version \
history (A3), a belief with its version history (B2), a program (p0040: plan, diff, code, result, children), or a \
search over every experiment and step ("search: penalty continuation"). Look up only what you need.
Reply with one JSON object and nothing else:
```json
{{"lookups": ["S12", "A3", "search: resolution ladder"], "why": "one sentence"}}
```
or {{"lookups": []}} if you have what you need."""

REVIEW_ASK = """## Step back: review your agenda and theory

Every few rounds you step back, like a lab meeting with yourself. Read your whole agenda (open and closed) and your \
whole theory, and the progress check, then:
- challenge your most confident beliefs: for each, what result would refute it, and has anything genuinely different \
been tried? Downgrade or drop what hasn't survived a real test; turn untested claims into conjectures;
- act on every due thread; prune, merge, close or reopen threads;
- check the balance: at least one thread deepening the best line, at least one developing a different line or \
construction; if the best score has stalled, at least one thread must be a real escape;
- write a short summary of your current theory of the problem (it replaces the previous summary, which stays in \
the history).
Reply with one JSON object and nothing else:
```json
{{"thinking": "at most 150 words", "gist": "one self-contained line",
 "beliefs": [], "agenda": [{{"op": "reopen", "id": "A1", "why": "..."}}],
 "summary": "your theory of the problem now, in at most 120 words"}}
```
Agenda operations: add (with question, plan, stop), revise, done, park, drop, reopen, branch; belief operations: add, \
revise, drop."""
