# Lean Helix against v4: every difference, and why each is safe (November 8, 2026)

**What lean is:** v4 with its Atlas memory, the condition v4's runs showed best and that every later VRP run used,
cleaned. The Atlas starts empty in every run: nothing from earlier runs is carried over. v4's Control condition (no
memory) remains a setting, `memory="none"`. The test, set by Shreyas on
Nov 8, is that lean must be at least as good as v4, shown by reading the code, not by runs (runs are too noisy to
show it). So every difference below is one of two kinds:
- **the same behaviour, written differently**;
- **a fix:** a known bug or a limit in v4, removed, where the fixed version can only do at least as well.

**Why v4, not a later version** (`docs/VERSIONS.md`):
- v4 with the Atlas is the version the record calls "the baseline that works": 0.939 on AC2 in 20 generations, and
  +20.8% over the current method on the VRP's held-out worlds.
- v4.5 was within chance of v4.
- v4.6 was worse.
- v4.7 was behind v4 on the VRP from scratch (1.642 against 1.696 held out).
- v7 and v8 were only ever run as continuations of earlier runs, never against v4 from the same start.

So none of the later versions' changes is something we are sure of. The fixes below are limited to faults in v4's
code, or its limits, whose fix can only help.

Nothing whose effect is uncertain is included. The parts tested in experiments 1-7 (one-line notes, the best
program's longer path, restarts, mutations from the best program only, mutations without inspiration) were taken out
of the code. They remain in git history at commit `bc7475a5` (the version experiments 1-7 ran on).

Compared: `helix4/` (run.py, memory.py's Atlas and Control, prompts.py, archive.py, evaluate.py, sandbox.py, llm.py
and helix3/llm.py, problems/ac2.py) against `lean/` (loop.py, atlas.py, prompts.py, archive.py, sandbox.py, llm.py,
problems/ac2.py).

**Checked by tests against helix4's own code:**
- `tests/test_lean_v4.py` renders the same programs and findings through helix4's Atlas and lean's, and requires the
  same text, numbers aside: the map (tree of attempts, findings index, last generation), every opened program and
  finding, every finding's status, the statistics. It also requires:
  - the planner's view (header, best program, map, opened items, plan format);
  - the Navigator's and the Distiller's requests;
  - the same AC2 feedback as helix4's evaluator, line for line, for an improving, an unchanged and an invalid
    program.
- `tests/test_lean.py` checks the Control view, the coder's and mutator's requests and the plan retry against
  helix4's strings.
- For the VRP, the plug-in's own `tests/test_lean_adapter.py` (private) checks every request against what
  `run_vrp.install` made helix4 say.

## Identical

- **The generation.** Mutations are submitted first; the planner plans meanwhile; then the coders.
  - Same counts: 3 + 3 (v4's wide and deep).
  - Same temperatures: planner 0.7, coder 0.5, mutator 0.8, the code retry 0.4.
  - Same thinking effort: the planner "low", the others none.
- **Parents.** Sampled from every valid program of earlier generations, with weight 1/(1+rank)/sqrt(1+children),
  by the same seeded generator. Each mutation sees one other program, chosen at random from the 5 strongest.
- **The planner's view** (v4's Atlas):
  - the problem;
  - "# Generation g of G" and the budget line;
  - the best program: its id and score, its lineage line (its last 6 steps of ancestry, each with what it changed and
    gained), its result and its code;
  - the map: the tree of attempts (the lineages of the 12 strongest programs and of the last generation, the rest
    folded), the findings (up to 45: the newest and the best supported) and the last generation in full;
  - from generation 2, up to 6 items the planner chose to open (the Navigator's call);
  - the plan format.

  With `memory="none"` (v4's Control): the 6 strongest programs instead of the map, and no Navigator.
- **The Atlas's Distiller.** After every generation it reads the findings so far, the planner's analysis and every
  new program (plan, summary, base, result, diff), and writes at most 6 new findings and attaches evidence.
  - Code keeps only evidence that names real programs, and links that name existing findings.
  - A finding's status (supported, mixed, refuted, open) is computed from its evidence's measured gains, never taken
    from the model.
  - On resume, the findings of an unfinished generation are dropped.
- **The prompts.** Every system prompt and format is v4's text, word for word: the planner's (v4's Researcher's),
  the coder's, the mutator's, the plan format, the code format, and both retry notes.
- **The plan.**
  - An unreadable plan is asked for once more, JSON only.
  - An experiment on an unknown or failed base goes to the best program.
  - Missing experiments become "improve the best program".
- **Writing code.** One retry when the reply has no program. A reply that is bare code, with no code fence, is
  accepted.
- **Evaluation.**
  - Every program runs from its base's result, in its own process, with the same CPU, memory and wall limits, one
    thread and low priority.
  - At most HELIX_EVAL_SLOTS programs run at once on the machine, and only while at least HELIX_EVAL_MIN_MB of memory
    is free.
  - Code is checked and scored; no model judges anything.
- **Bookkeeping.**
  - Every program is kept.
  - A program identical to one already built on the same base is not run again.
  - A stopped run resumes from its last finished generation.
- **The model client.**
  - A reply cut off by the token limit is retried once with double the room.
  - A thinking call over 600 s is retried without thinking.
  - Failed calls are retried; a run never stops on one.

## Fixes (each can only help)

| v4 | Lean | Why it can only help |
|---|---|---|
| Base programs were shown clipped at 12,000 characters, the best program at 9,000 and inspiration at 5,000 | 30,000, 12,000 and 8,000 by default; a problem may raise them (the VRP shows programs whole) | A coder must return the complete program. Shown a clipped one, it rewrote the missing part blind, and children broke. The VRP lesson: "code-length clipping is a hidden ceiling" (`docs/research/VRP_CONTEXT.md`) |
| Scores shown to 6 digits, lineage gains to 5 | 9 digits | A gain smaller than 1e-6 was shown as +0.000000. More digits only add information |
| The planner read the archive while mutations were writing to it | It reads under a lock | v4 could crash ("dictionary changed size during iteration"). What the planner sees is otherwise the same: the programs finished at that moment |
| Thinking room 12,000 tokens on top of the planner's 12,000 | 24,000 on top | More room; the reply is the same or less often cut off |
| A coder's reply had room for 9,000 tokens | 12,000 by default; a problem may raise it (the VRP: 32,000) | A long program no longer gets cut off |
| A rate limit (HTTP 429) ended a call after 5 tries | It is waited out | A rate limit is a wait, not a failure: fewer lost programs |
| The facts any result has (its score against its start's, "the result is the start unchanged", CPU and wall time) were written inside the one problem file | The core writes the first and last lines for every problem; the problem describes the rest (`describe`, which may see the start) | AC2's feedback is v4's, line for line (tested). Other problems now get the same first and last lines |
| An invalid result's feedback was the error alone | The error, then the program's last printed lines, as for a crashed program | More information, not less: a program's own printout often says why its result was wrong |

## Removed

- **v4's Journal memory.** v4's job compared three conditions; the Atlas was carried forward into every later
  version and the VRP runs, so lean keeps the Atlas, and Control as a setting.
- **v4's own report pages** (`helix4/report.py`). Lean writes the same records, read by `lean/bench.py`.

## Added

- **An adapter interface** (`lean/problems/__init__.py`). The core never changes per problem: a problem file
  supplies the statement, Code Zero and the evaluator, and may override the wording of the system prompts and the
  budget lines. Without overrides the text is v4's, word for word.
  - This is how v4's VRP plug-in already worked, by patching helix4 at run time.
  - Lean makes it explicit: a problem may bring its own evaluator. Programs that don't start from a construction
    have each change measured against their base's score, with "its base … scored …" added to the first feedback
    line, as v4's VRP plug-in did.
- **More than one starting program** (November 8, 2026; Shreyas approved). A problem may list `extra_seeds`
  (`[(idea, code), ...]`): each is evaluated and joins generation 0 beside Code Zero, so parents and inspirations
  can come from any of them. With none listed, generation 0 is exactly as before (tested). Used by the VRP's
  "combined" variant: a fast program and a cheap one, side by side.
- **A knowledge bank** (November 9, 2026; Shreyas asked): a problem may supply `knowledge` (Markdown entries
  `## K<n>: title`, `lean/knowledge.py`). The planner and the mutators see the whole bank; a coder gets the entries its
  experiment cites (`knowledge` field, kept in plans.jsonl). With `inspiration: "knowledge"` a mutation is shown the
  bank instead of another strong program. No bank and the default setting: prompts exactly as before (tested).

## Problems

- **AC2 (`lean/problems/ac2.py`):** v4's statement and feedback, word for word.
  - The step limit is a parameter. It is 200,000 in v4; experiments 3 and 7c used 50,000, the published systems'
    constraint.
- **The other problems (circles, AC1, AC3, Erdős):** new. They use v4's wording for how a program should treat its
  start and its budget.
