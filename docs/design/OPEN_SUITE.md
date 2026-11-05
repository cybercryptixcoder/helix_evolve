# The open suite: problems without a ceiling

The first suite (`suite/`, 9 problems) measures progress toward a known reference (an optimum or best-known
solution), and next to a hidden textbook rule. Several of those problems saturate (knapsack reaches 100%), and a
known optimum is itself a hint about what "best" looks like. The open suite asks a different question: **how far
does the search climb when nothing caps it and nothing tells it what good looks like?**

Inspired by score-based heuristic contests (AtCoder Heuristic Contest, as collected in
[ALE-Bench](https://arxiv.org/html/2506.09050v2)): there is no known optimum, only a score, and better ideas keep
raising it. Every problem here is **invented** (made-up rules, so no textbook answer or published solution exists),
and the objectives differ: task performance, speed and scaling, play against opponents, and one judgement-call
objective with no ground truth.

## The contract (what makes a problem "open")

Same interface as `helix3/problem.py` (a decision-by-decision priority problem), plus:

- `open_ceiling = True`. **No reference, no floor, no textbook rule**: `baseline = []`, `reference_metrics()`
  returns `{}`, `floor()` is 0.
- **Score = cost relative to Code Zero.** Each instance has a cost (>= 0, lower is better) and
  `gap = 100 * cost / cost_of_code_zero(instance)`. Code Zero scores exactly 100 on every instance; progress is
  `100 - gap`, "how much of Code Zero's cost is gone". 100% would mean zero cost, which no instance allows, so the
  ceiling is open and nothing hints at where the real best lies.
- **No hints**: the description states the rules and the score, never strategies. Candidate order is neutral
  (shuffled per decision with the instance's seed), so Code Zero is effectively a random policy.
- **Held-out family** in `test`, deterministic seeds, fast (Code Zero on the train split in about a second).
- **Diagnostics** describe the policy's own behaviour only (never a reference).

## The problems

| Name | Kind | One decision | Cost |
|---|---|---|---|
| `forage` | task performance, dynamic | a drone picks its next target among visible items (or the charger) | value lost: value that spawned but decayed or was never collected, plus a penalty for running out of battery |
| `thermal` | systems performance | place an arriving job on a server in a data hall whose racks heat up and slow down | total extra completion time caused by heat and queueing (flow time above each job's ideal) |
| `backtrack` | speed and scaling | a fixed backtracking solver asks which unassigned variable to branch on next | search nodes until the first solution (capped), over instances from small to large; the growth rate with size is a diagnostic |
| `duel` | play against opponents | choose a move in an invented two-player game | the share of points won by a fixed pool of scripted opponents over many seeded games |
| `fairshare` | judgement call, no ground truth | give the next open shift to one of the volunteers | a blend of uncovered shifts, unmet preferences and unfairness (spread of dissatisfaction); the components are reported separately because the blend itself is a judgement |

## How the runs are set up (`scripts/run_open_jobs.sh`)

- **No reference statistics** reach the agents (`diagnostics.show_reference: false`; there are none anyway).
- Each problem runs once with the default strategy (15 generations).
- **Thinking-mode ablation** on two problems: Researcher and Navigator without hidden thinking, at low (the
  default), always at high, and low with a high breakthrough every 5th generation.
- Results land in `results/open/<job>/`, with the full trace.

## Round 2: games, debugging, mathematical construction

Four more open problems, each a different kind of thing to evolve: a strategy for a puzzle game, a controller for a
fast arcade game, a debugger, and a construction rule for an open mathematical question.

| Name | Kind | One decision | Score |
|---|---|---|---|
| `stacker` | puzzle game (invented falling-piece rules) | where to drop the next piece (rotation and column) | points over a fixed number of pieces, game over ends it early |
| `runner` | arcade game, run as a speedrun | the action for the next tick (left, right, jump, dash, wait) | ticks to reach the goal across seeded levels, plus penalties for deaths and for not finishing |
| `repair` | debugging | which candidate patch to try next on a buggy program | patches tried before every test passes, plus a penalty per test still failing at the budget |
| `progression` | mathematical construction | which number to add next to a set that must avoid an invented equation | the final set's size (bigger is better; no known maximum) |

Scoring for problems where bigger is better (`stacker`, `progression`): `gap = 100 * score_of_code_zero / score`,
so Code Zero is 100 and the ceiling stays open (a score twice Code Zero's is gap 50, ten times is 10). For cost
problems (`runner`, `repair`): `gap = 100 * cost / cost_of_code_zero` as before.

**repair** in more detail: a handful of invented calculation programs (a made-up tariff calculator, a geometry
routine, a small simulator...) each have a hidden correct version and a test suite of 20-40 cases generated from it.
An instance injects 2-4 seeded bugs (operator swaps, off-by-one, wrong variable, changed constant, negated
condition, swapped arguments). The candidates are single-edit patches over the program (each mutation operator at
each applicable place). The engine applies the chosen patch and keeps it only if no passing test breaks and either fewer tests fail
or the total numeric error at least halves; otherwise it reverts. Bug sets that Code Zero repairs by luck are redrawn. The features see what a debugger sees: for each candidate
patch its kind and line, how many failing and passing tests execute that line, the errors the failing tests raise
(exception kinds, how far off the numbers are), and what has been tried. Never the correct program.
