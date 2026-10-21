# Helix v4.5 and v5

October 21, 2026. Built from `docs/BRIEF_2026-10-21.md` (requests verbatim), the design discussion in
`docs/IDEAS.md` ("The next build: Helix as a researcher") and the analysis of the finished v4 job
(`docs/V4_ANALYSIS.md`).
- Code: `helix5/`.
- Tests: `tests/test_helix5.py`.
- Job: `scripts/run_v5_jobs.sh`, `docs/V5_JOB.md`.

Two systems run side by side on the same engine, budgets and problem as v4, so v4's nine runs are the baselines:

- **v4.5** (`--condition v45`): the conservative bet. v4's Atlas, with what the v4 traces showed it needed.
- **v5** (`--condition v5`): the ambitious bet. One continuing researcher with a theory, an agenda and a notebook.

## 1. What the v4 job showed

Full analysis: `docs/V4_ANALYSIS.md`. The best run (atlas-s1) certifies C2 ≥ 0.9390161; four of nine runs passed
AlphaEvolve's May 2025 result (0.8963); four ended at 0.8825.

1. **The planner hill-climbed one base.** All 3 planned experiments were on one base in 8-19 of 20 generations.
   Even so, the best run was narrow in *where* it built and wide in *what* it tried.
2. **The textbook answer is a trap.** The four stuck runs sat at 4 ln 2 / π ≈ 0.88254, the classical
   f = x^(-1/2). Three of them reached for it from memory in generations 1-2, then polished it for 15-19
   generations.
3. **Stuck planners spiral.** They used 15,000-20,000 reasoning tokens per plan (the climbers 5,500-7,500), with 6-9
   length cut-offs each. Their plans derived integrals in their heads, often wrongly.
4. **Escapes came from three moves.** A new *kind* of change on the best line (turning the max into a constraint:
   found independently three times), a fresh start, and applying the current method to another line.
5. **Waste:**
   - a third to a half of planned children had no effect;
   - siblings sharing code got the same score, and each was credited for it;
   - inherited stages ate the budget before new ones ran;
   - late, at high resolution, programs were killed at the CPU limit and scored nothing (8 in atlas-s1, including
     a whole generation of the main line).
6. **What worked:**
   - elimination: grouping what failed and trying the complement;
   - diagnosis from programs' printouts;
   - warm starts carrying a resolution ladder across generations;
   - the wide loop, which set 52 records and drove two of the escapes.

## 2. The behavioural problems, and the structure that answers each

An early v5 test showed four problems: a belief that froze the search, narrowing, thinking spirals, and plans with
no shape. The v4 traces show the same four. Each comes from a structural cause, so each fix is structural: a change
in what the system decides by code and what it asks the model for, not an extra instruction.

| Problem | Why it happens | Structural answer |
|---|---|---|
| **A belief freezes the search** (an early v5 test: "the true max is 4 ln 2 / π"; v4: runs anchored on x^(-1/2)) | A memory that stores and re-shows beliefs turns a confident belief into a premise of every later plan. Nothing ever tests it, and every polishing result seems to fit it. | **Beliefs are hypotheses with a refutation test.** Observations (works / fails) must cite measured experiments, and their status is computed from the measurements, not from the model's say-so. Explanations (mechanisms) and claims beyond the data (conjectures) must say what would refute them (`refuted_if`). Limits, optima and closed forms are filed as conjectures by code, whatever the model calls them, and held at low confidence until they survive two challenges. Every 3 rounds a **challenge slot** tests one. Shared gains don't count as evidence. |
| **Narrowing** (v4: one base in 8-19 of 20 generations) | Each round the planner picks the experiments with the best expected gain, and locally that is always the best program. An instruction to diversify loses to that every round. | **Code decides the allocation; the model fills the slots.** Every generation has roles: deepen (on the best line), branch (another line, or a fork point of the best line), explore (from scratch). Depth adapts to progress: two deepen slots while the best line keeps paying, and they must test different mechanisms. Branch candidates favour young lines, so a new line gets to mature: a fresh start rarely beats the record at once. The roles are enforced on the bases. |
| **Thinking spirals** (v4: 15,000-20,000 tokens per plan in stuck runs) | An open-ended "plan" with thinking turned on invites the model to settle uncertainty by derivation, which has no stopping point. | **A bounded decision.** v5's round is a fixed four-step work order (what came back → theory → agenda → slots), each step a short structured output. "Measure, don't derive": a suspicion becomes an experiment. The planning call is capped: on a cut-off it answers without thinking rather than retrying at double length. |
| **Plans with no shape** | "Plans" were open-ended wishes: never closed, never counted. | **Threads with stop rules.** Each agenda thread has a question, a next step with an if/then, and a stop rule. Code counts each thread's experiments and real gains. After 3 experiments without a real gain the thread is due: it must be closed, revised with a new approach, or parked. A due thread that is ignored is parked by code. Open threads are kept few, with at least one on the best line and one off it. |
| **Plateaus held by more of the same kind** (v4: atlas-s1 g5-g8; the stuck runs) | Each generation's experiments are variations within one kind of change; the planner doesn't step back to see that. | **Elimination, built in.** After 2 generations without a rise, the progress check lists every planned experiment since the last rise with its result. It asks the planner to group them by the kind of change, and at least one experiment must make a kind of change none of them made. (This is what atlas-s1 did by itself to break its plateau.) |

## 3. The shared engine (both systems; `helix5/run.py`, `helix5/evaluate.py`, `helix5/sandbox.py`, `helix5/prompts.py`)

- **The portfolio** (above).
  - Default roles are deepen, branch, explore.
  - The first generation is deepen, explore, explore.
  - While the line pays (the record rose ≥ 0.001 last generation, or ≥ 0.0001 in each of the last two): deepen,
    deepen, then branch or explore alternately.
  - v5 swaps the explore slot for a challenge slot every 3 rounds when a mechanism or conjecture is unchallenged.
- **Fresh starts**: an explore experiment runs with no start construction, using its base only as a template.
- **Real gains**: gains are labelled by size ("big gain" ≥ 0.001, "gain" ≥ 0.00001, "no real change", "loss").
  Statuses and statistics count only real gains, and "new best" means the record actually rose.
- **Anytime results**: programs call `keep_best(h)` whenever their best improves. At the CPU limit
  (1.25 × budget + 10 s) the runner stops the program and scores the construction it kept, instead of nothing.
- **Stage lines**: programs print one line per stage ("stage name: before -> after, s"). These lines are collected
  apart from the rest of the output and always come back, so planners see where the budget goes and which stage
  pays.
- **Shared gains**: siblings on one base that land on exactly the same score are marked ("the gain came from code
  they share"), and memories don't count them as evidence.
- **More of the program's voice**: the stage lines plus the last printed lines come back; unused budget is stated.
- **Coder rules**: use the whole budget, return the best construction found anywhere in the run (never worse than
  the start), keep the best, print stage lines.

## 4. v4.5: Atlas+ (`helix5/v45.py`)

Everything Atlas had (the immutable log, the tree of attempts, the Distiller's findings graph with code-checked
evidence, the map with the last generation in full, two-step navigation), plus:
- **Its own recent reasoning**: the last 3 generations' analyses, every bet, the if/then it committed to, and what
  came of each (with gain labels). This combines Atlas's map with the Journal's continuity.
- **If/then follow-up**: every experiment states what to do next if it gains and if it doesn't.
- **The portfolio and the progress check**, including the elimination list when stalled.

## 5. v5: the researcher (`helix5/v5.py`)

One researcher works across rounds and keeps three things, all stored as append-only event logs:

| | What it is | How it changes |
|---|---|---|
| Theory (`beliefs.jsonl`) | beliefs of four kinds: works / fails (cite evidence), mechanism / conjecture (state `refuted_if`); conjectures stay "low" until they have survived two challenges; a theory summary is rewritten at each review | `add`, `revise`, `drop`, each with a reason, plus challenge outcomes; code shows the measured outcome of every cited program and computes the status |
| Agenda (`agenda.jsonl`) | threads: a question, a next step with an if/then, a stop rule; code counts experiments, gains, and when a thread is due | `add`, `revise`, `done` (with outcome), `park`, `drop`, `reopen`, `branch`; due threads ignored are parked by code |
| Notebook (`notebook.jsonl`) | one step per round or review: what came back (did each prediction hold?), reasoning, a one-line gist, operations, experiments, the steps it follows | appended; never edited |

- **Versioned, never rewritten.** The current state is the replay of the events. Every earlier version of every
  belief and thread, and every branch, stays reachable through lookups. An untouched belief stays word for word (a
  test checks this).
- **Every experiment belongs to a thread and a notebook step**, with its slot role, prediction and if/then.
- **Constructed continuity.** When results come back, the round opens at the steps linked to them:
  - the step that scheduled them (with its results, in full);
  - the latest step that touched each of their threads;
  - the steps those followed;
  - the steps that created the threads.

  Links are recorded when a step is written, mostly by code, so continuity never depends on a search succeeding.
  Near steps are shown in full, far ones as gists.
- **Explicit lookups** before deciding (up to 5): a step, a thread or belief with its full version history, a program
  (plan, diff, code, result, children), or a word search over everything.
- **Step back** every 5 rounds: a review that challenges beliefs, acts on due threads, checks the balance between
  lines, and writes a new theory summary.
- **Interrupts**: when the memoryless mutation loop sets a record, the round says so first.
- **Thinking**: the round's decision and the review think at "low" (capped); lookups don't think.

## 6. How they will be compared

Same problem, budgets and round structure as v4: 3 planned and 3 mutated programs per generation, 30 s of CPU each,
20 generations. The report (`python -m helix5.report results/v4 runs/v5 --out results/v5`) puts v4's 9 runs, v4.5
and v5 on one page, with AlphaEvolve's May 2025 result and the other published values as reference lines; it shows
v5's agenda and theory.

Measures:
- best per seed, and the median;
- how many runs pass 0.8963, and how many end in the 0.8825 attractor;
- real-gain rates by slot role;
- how often runs escape a stall;
- for v5, threads closed vs parked and beliefs challenged.

`python tools/analyse_runs.py results/v5` gives the same failure-point table as for v4.

Three seeds per system: differences smaller than the spread between seeds are not evidence.

**One difference from v4:** v4.5 and v5 also get the anytime results, stage lines and shared-gain marks, which v4
did not have. A comparison with v4 is therefore a comparison of systems (memory, planning and engine together), not
of memory alone. v4.5 against v5 isolates memory and planning, since they share the engine.

## 7. Tests

`tests/test_helix5.py` (21 tests):
- the AlphaEvolve construction reproduced three ways, and the exact check on large constructions;
- gain labels;
- both systems end to end with a fake model (6 generations, including a review), and resume;
- portfolio roles and their enforcement, the steady-climb rule, lines and branch candidates, fresh children;
- v5 operations, versioning and no drift; falsifiable beliefs and conjectures; due threads parked; continuity
  following links; lookups;
- the capped planning call; step kinds;
- shared gains marked and not counted; the elimination list when stalled; stage lines and the CPU limit keeping the
  best;
- the combined report.

## 8. What is still uncertain

- **The portfolio costs depth.** atlas-s1 was the narrowest run and the best. The steady-climb rule gives a paying
  line two deepen slots, but in a flat generation only one slot deepens. Whether that slows a run like atlas-s1 is
  exactly what the job will show.
- **v5 makes more model calls and reads longer prompts than v4.5.** A round is a lookup call, a decision, and a
  review every 5 rounds.
- **The tests show that the mechanisms fire** (roles, challenges, stop rules, marks, the CPU stop), not that they
  raise scores.
- **The short real tests are inconclusive.** At 7 generations, v4.5 reached 0.8824 and v5 0.8710, inside v4's spread
  at generation 7 (0.868-0.887).
