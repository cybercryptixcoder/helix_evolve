# Plan: one lean Helix, problem first (November 5, 2026)

Status: **Phase 1 done; the core tested on 26 and 32 circles and AC1 (`docs/LEAN_RESULTS.md`); AC2 on the VM.** The request (Shreyas, Nov 5, 18:20 and 18:50) is in `REQUESTS.md`.

## The aim

Build one main Helix, small enough that anyone can read it and say which part caused which result. Every part must
solve a named problem and be shown by test to help. Then use it for a set of experiments on several problems, each
compared fairly with published systems. The old versions stay in the repo for reproducibility, but off centre stage.

## The rule: problem first

No component goes in because an architecture suggests it. Each one starts as a problem statement ("the search does X,
which costs Y; we see it in run Z"). Then comes the smallest change that addresses it, and then a test with and
without that change. A component stays only if the test shows it helps. If it doesn't help, it comes out, and the
test is recorded either way.

## The problems, as we know them

| # | Problem | Evidence so far |
|---|---|---|
| P1 | Each round starts from scratch: the model doesn't know what was tried or learned | v4's memory comparison (Atlas and journal beat no memory; 3 seeds, high variance) |
| P2 | Context is limited: not everything learned can be shown to the model | the memory designs from v4 to v4.7; never tested as its own question |
| P3 | The search settles in one region and polishes it | v10.2 seed 1: one track held the record for all 400 rounds; v9: the map ran, the record moved by 2.5e-13 |
| P4 | The model isn't creative: it rewrites its favourite ideas | v9: only 42% of requested changes landed; the model's "habits" (docs/research/RESEARCH_CASE.md) |
| P5 | Forcing genuinely untried territory with settings we control | the Oct 29 discussion (axes as dials, jumps; docs/history/CONVERSATION_2026-10-29.md); the circle-packing dry run |
| P6 | Nobody can attribute results to parts | 13,700 lines across six inherited packages behind v10.2 |

**The wide loop** is a question to test, not a conclusion. Shreyas's observation is that it mutates weak programs and
often scores at or below Code Zero. The records disagree on one measure: the share of total gain whose record was
set by a wide program was 68% in v10.2 seed 1, 76% in seed 2, 72% in v4 atlas-s1, and 20% in v8-s1. But "set the
record" may only mean "polished the deep loop's idea first". A test decides it.

## Phases

### Phase 0: the measuring stick (before any building)
- **Two problems.**
  - **A cheap development problem** for fast tests. Candidate: circle packing (26 circles, maximise the sum of
    radii), which scores in milliseconds and has published values.
  - **AC2 at a short budget**, so results can be compared with what Helix has already done there.
- **One fixed protocol:**
  - start from Code Zero;
  - N programs per run;
  - the same model and settings;
  - at least 3 seeds per arm.
- **The metrics:**
  - the best score after N programs;
  - the best score along the way (area under the curve);
  - the cost in tokens;
  - for each record, which part of the system produced it.
- **The floor:** the plainest loop. The model is shown the best program and asked for a better one. This is not a
  stand-in for the industry: it's the zero that every component is measured against.

### Phase 1: audit and clean v4 into the lean core
- **Read v4 in full** (1,842 lines) and list its bugs, conceptual issues and bloat.
- **Rebuild as one new package** (a name to agree on), with one file per concern:
  - problem;
  - sandbox and scorer;
  - archive;
  - model;
  - loop;
  - log.
- **Pull the size limits and fixes from later versions only where they're needed.** Examples: the exact step limit
  (`ExactView`); the safe evaluator from v4.7.
- **Tests:** crash tests with a fake model; then live tests with the real model, as always.
- **A problem is one file:** its statement, scorer, verifier and Code Zero.

### Phase 2: add components one at a time, each against its problem
In this order (each needs the earlier ones):
1. **P1 (continuity):** a plain memory of what was tried and what it showed, against no memory.
2. **P2 (context):** what to show the model when memory outgrows the context. Compare simple options
   (most recent, best, a summary), not a fixed architecture.
3. **Wide loop:** with it, without it, or folded into the deep loop.
4. **P3 and P4 (exploration):** separate lines judged on their own climb; new designs built from nothing. These
   are v7 and v10.2's ideas, re-tested on their own.
5. **P5 (controlled novelty):** the dial idea, with jumps to far points. This is new work; it needs its own design
   discussion first.
6. **The field's knowledge as input:** with and without, stated clearly in every result.

Each step gets:
- a short design note (the problem, the change, the test);
- the runs;
- a verdict: kept or dropped;
- a line in VERSIONS.md.

### Phase 3: freeze the main and run the showcase
- **Freeze one configuration.**
- **Run the problems in research/SHOWCASE_PLAN.md:**
  - AC1 and AC3;
  - Erdős's minimum overlap problem;
  - circle packing (26 and 32 circles);
  - AC2.

  Each under the published systems' constraints, with two or more seeds and every claim in RECORDS.md.

### Phase 4: the repo
- **The lean package at the centre** of the README.
- **The old versions in their own clearly labelled folder,** each still runnable for reproduction.
- **The README tells the story:** the problems, the components, the ablations, the results.

## Constraints
- **Compute.**
  - The VM (2 cores) is busy until about Nov 7.
  - This cloud session also has 2 cores.
  - Tests multiply runs (components × 3 seeds × 2 arms), so Phase 2 runs on the cheap problem at short budgets.
- **A current Luminal key** is needed for the live tests.

## Decisions for Shreyas
1. The development problem: circle packing (26, sum of radii), or another?
2. The run size for a component test (for example 300 programs × 3 seeds × 2 arms).
3. The new package's name and place (for example `lean/` or `helix/` with the old v1 moved).
4. Where the old versions go (for example `versions/`).

## Progress

- **Nov 5:** Phase 1. `lean/` built: v4's core, cleaned (`lean/README.md` lists what changed and why), about 1,000
  lines, crash-tested (`tests/test_lean.py`) and live-tested on circle packing. Decisions taken in Shreyas's
  absence ("do as much as you can"):
  - development problem: circle packing, n = 26, zero tolerance;
  - package `lean/`;
  - old versions untouched for now.
- **Experiment 1** (`experiments/lean/e1_core.json`): which parts of v4's core help? Five arms x 3 seeds, 240
  programs each, 10 s per program:
  - the plainest loop;
  - a population;
  - a planner;
  - a planner with notes;
  - a planner with no mutation loop.
