# Helix v4.5 and v5

October 21, 2026. Built from `docs/BRIEF_2026-10-21.md` (requests verbatim) and the design discussion in
`docs/IDEAS.md` ("The next build: Helix as a researcher"). Code: `helix5/`. Tests: `tests/test_helix5.py`. Job:
`scripts/run_v5_jobs.sh`, `docs/V5_JOB.md`.

Two systems, run side by side on the same engine, budgets and problem as v4, so v4's nine runs are the baselines:

- **v4.5** (`--condition v45`): the conservative bet. v4's Atlas, fixed where the v4 overnight run showed it was weak.
- **v5** (`--condition v5`): the ambitious bet. One continuing researcher with a theory, an agenda and a notebook.

## 1. What the v4 run showed (the evidence behind both)

From `results/v4/` (plans, findings, journals, histories), mid-run on October 21:

1. **The planner hill-climbed one champion.** In most generations all 3 planned experiments built on the current best
   program (atlas-s1: 12 of 12 generations; most runs at least 75%). The population existed; the planner didn't use it.
2. **Stalled runs stayed stalled.** Four runs reached the classical 1/√x shape (≈ 0.8825) early and spent 5-10
   generations polishing it by 0.00001 at a time; "gained" counted +0.000000001 as success.
3. **Breakouts needed a genuinely different method**: random multi-start (journal-s2: 0.882 → 0.914), a penalty
   continuation that turns the max into a constraint (atlas-s1: 0.879 → 0.908 → 0.936), a resolution ladder.
   Each came after the planner noticed, from its memory, that the recent attempts had all failed.
4. **Programs wasted budget**: many stopped after 7-13 s of 30, and one returned a worse construction than it had
   found ("the pipeline throws away its own best answer").
5. **Program logs matter**: the journal-s2 breakthrough came from reading a program's printed lines.
6. **Atlas recorded honestly** (atlas-s2: 23 "works", 27 "fails", 4 questions, 94 links) and its planner opened and
   cited findings; but it never saw its own previous reasoning, which the Journal did.

## 2. Shared engine fixes (both systems; `helix5/run.py`, `helix5/evaluate.py`, `helix5/prompts.py`)

- **Fresh starts**: an experiment can start from scratch (no start construction), using its base only as a template.
- **The escape rule**: the engine computes how many generations the best has gone without rising by 1e-4. After 3,
  at least one of the 3 experiments must be an escape: fresh, or built on a program outside the best one's line. If
  the planner doesn't provide one, the engine converts the last experiment into a fresh start and says so.
- **Real gains**: gains are labelled by size ("big gain" ≥ 0.001, "gain" ≥ 0.00001, "no real change", "loss");
  statistics and finding statuses count only real gains; "new best" means the record actually rose.
- **More of the program's voice**: the last 8 printed lines come back (v4: 4); unused budget is stated.
- **Coder rules**: use the whole budget (restarts, perturbations from the best found), return the best construction
  found anywhere in the run, never worse than the start, print progress lines. (In tests, programs now use 27-28 s
  of their 30.)

## 3. v4.5: Atlas+ (`helix5/v45.py`)

Everything Atlas had (the immutable log, the tree of attempts, the Distiller's findings graph with code-checked
evidence, the map with the last generation in full, two-step navigation), plus:
- **Its own recent reasoning**: the last 3 generations' analyses, every bet, the if/then it committed to, and what
  came of each (with gain labels). Atlas's map plus the Journal's continuity.
- **If/then follow-up**: every experiment states what to do next if it gains and if it doesn't.
- **A computed progress check** at the top, and the escape rule spelled out when it applies.

## 4. v5: the researcher (`helix5/v5.py`)

One researcher working across rounds, which keeps three things, all stored as append-only event logs:

| | What it is | How it changes |
|---|---|---|
| Theory (`beliefs.jsonl`) | beliefs (works / fails / mechanism), each citing programs as evidence; plus a theory summary rewritten at each review | `add`, `revise`, `drop`, each with a reason; code shows the measured outcome of every cited program and computes the status |
| Agenda (`agenda.jsonl`) | the purposes being pursued, each with a plan that says what happens depending on results | `add`, `revise`, `done` (with outcome), `park`, `drop`, `reopen`, `branch` |
| Notebook (`notebook.jsonl`) | one step per round or review: reasoning, a self-contained gist, operations applied, experiments scheduled, the steps it builds on | appended; never edited |

- **Versioned, never rewritten.** The current state is the replay of the events. Every earlier version of every belief
  and agenda item, and every branch, stays reachable through lookups. An untouched belief stays word for word (a
  test checks this).
- **Every experiment belongs to an agenda item and a notebook step**, with its prediction and if/then.
- **Constructed continuity** (`continuity()`): when results come back, the round opens at the steps linked to them:
  the step that scheduled them (with its results, in full), the latest step that touched each agenda item they
  belong to, the steps those declared they build on, and the step that created the item (as gists). Links are
  recorded when a step is written, mostly by code (which step scheduled what, which step touched which item), so
  continuity never depends on a search succeeding. Near steps in full, far ones as gists; at most 4 full and 12 gists.
- **Explicit lookups** before deciding (up to 5): a step, an agenda item or belief with its full version history, a
  program (plan, diff, code, result, children), or a word search over everything.
- **Step back** every 5 rounds: a review of the whole agenda and theory (prune, merge, close, reopen, correct) with a
  new theory summary.
- **Interrupts**: when the memoryless mutation loop sets a record (by 1e-4 or more), the round says so first.
- Thinking: the round's decision and the review think at "low"; lookups don't think.

What v5 deliberately does not do yet: run event-driven (it keeps v4's rounds of 3 experiments so compute stays
comparable), or let the model rewrite the theory freely (only the summary is rewritten, with history).

## 5. How they will be compared

Same problem, budgets and round structure as v4 (3 planned + 3 mutated programs per generation, 30 s of CPU each, 20
generations). The report (`python -m helix5.report results/v4 runs/v5 --out results/v5`) puts v4's 9 runs, v4.5 and
v5 on one page, with AlphaEvolve's May 2025 result and the other published values as reference lines; v5's agenda and
theory are shown. Measures: best per seed and median; how many runs pass 0.8963; real-gain rates of planned vs
mutated children; how often runs escape a stall; for v5, items resolved vs abandoned and how often plans were
revised. Three seeds per system: differences smaller than the spread between seeds are not evidence.

## 6. Tests

`tests/test_helix5.py` (12): the AlphaEvolve construction reproduced three ways; the exact check on a large
construction; gain labels; both systems end to end with a fake model (6 generations, including a review); resume
dropping an unfinished generation; the escape rule (forced only when needed); fresh children run without a start;
v5 operations, versioning and no drift; continuity following links rather than a window; lookups and search; the
combined report.
