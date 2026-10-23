# Helix v4.7: v4 without the false ceiling

v4.7 keeps v4's architecture:
- the Researcher plans, Coders write, and the history-free Mutator explores;
- every program is run, scored and kept;
- the Atlas Distiller records findings.

What changes is what the deep loop works on and what it is shown. It removes the mechanisms that
`docs/V4_CEILING.md` found building a false ceiling in the 150-generation atlas-s1 run, and the cut-off found in the
VRP runs.

Code: `helix47/`, which reuses helix4 and changes nothing in it. Tests: `tests/test_helix47.py`. The job:
`scripts/run_v47_jobs.sh` and `docs/V47_JOB.md`. On the VRP: `run_vrp --version v47`, in the private package.

## The crux, and why the first draft of v4.7 didn't fix it

The false ceiling lives in the main deep loop. All three planned experiments go to the champion every generation.
Each is judged against the champion after 30 s. And the planner is shown only evidence about the champion.

When the champion stops improving, every slot keeps polishing it, and the planner (DeepSeek V4.1 Flash, the same
model behind Hermes, which calls every flat curve a ceiling) concludes it is saturated. It says so in 95% of its
analyses by generations 101–120. It then designs experiments that confirm it.

The first draft added a challenger loop beside the main loop. That left the main loop as it was, so it was a third
loop, not a fix. This version changes the main loop itself.

## Lines: the deep loop works on lineages, each judged against itself

A line is one lineage of constructions with its own best score.

- **One line at the start.** A run starts with one line, L1, from Code Zero. All 3 planned experiments go to it,
  and the Mutator's parents come from it. While L1 is climbing, a generation is v4's.
- **Each experiment is judged against its line's best.** The planner sees each line against its own previous
  generations ("g12 0.912345 (+0.0031); g13 no gain"), never against the overall record.
- **Code, not the planner, closes a line that has stopped gaining.** A line is stalled when its best rose by less than
  `stall_gain` (2e-4 relative; 2e-3 on the VRP) over its last `line_patience` (8) generations.
  - A stalled line closes, except the line that holds the record.
  - When the record's line stalls, a new line opens beside it. The record's line keeps a slot and closes only after
    twice the patience without a gain.
  - This is rule 2, from October 23 (see "What the first VRP run showed" below).
  - Its programs and findings stay, but it gets no more experiments.
  - The planner is never asked whether a construction is saturated. Its system prompt says closing lines is the
    system's job; its job is to make each line it is given climb.
- **New lines open when one closes,** up to `lines_after_stall` (2) active lines. Each takes the next starting point
  in turn:
  - the best kept alternative construction (below);
  - the best program of another branch: one that split from every line's best at a point at least 1% lower, so not
    a polish of it;
  - a fresh start from Code Zero.

  A kind the active lines already have goes last, and two fresh starts never run at once.
- **Slots follow progress.** Each active line gets one of the 3 slots, and the spare goes to the line that gained
  most over its last two generations. A new line counts as gaining.
- **The Mutator is a halo around the active lines.** Its parents are sampled from their programs.
- **The overall best is simply the best of all lines.** It is what the run reports, but the deep loop isn't
  chained to it.

This is what makes the planner's pessimism harmless. A stalled line is closed by code and the effort moves, so a
belief that the current construction is saturated leads nowhere. The model can stay pessimistic about a construction
and the search still moves on from it.

## The rest, always on

| Mechanism in v4 (`docs/V4_CEILING.md`) | The change in v4.7 | Where |
|---|---|---|
| **New ideas are erased.** Programs fall back to their start when their idea doesn't beat it within 30 s; 72% of late children handed back their start unchanged. | `construct` may return `{"best": ..., "alternative": ...}`. The alternative is scored. If it is different from the result and from the start, and scores at least 0.9 of the start, it is kept as its own program (role `alt`), and new lines can start from it. | `helix47/evaluate.py`, `Run.child`, `prompts.ALTERNATIVE_RULE` |
| **A wall of failures.** At generation 140 all 45 findings on the map were failures. | The findings shown are balanced: the 12 best and 8 newest "works"/"mechanism" findings and 6 open questions; failures only from the active lines (the newest 10). A closed line's failures are only counted ("Line L1 (closed): 389 failures, facts about that line's constructions"). Each finding names its line, and a failure names the construction it was tried on; its status reads "held: N didn't gain", not "supported". | `helix47/memory.py` |
| **Microscopic gains count.** 47 "new bests" in generations 81–150 added up to +1.4e-9. | A noise floor, `gain_floor` (1e-6 relative; 5e-4 on the VRP, where scores move by about 0.2% between evaluations). It applies to statuses, line bests, records and feedback. | `memory.outcome`, `Run.update_lines`, `Run.child` |
| **Collapsing targets** (+2% at generation 5, +5e-6 by generation 30; late experiments tested saturation). | Predictions are targets: "the score this aims for on its line". "When a line's recent experiments haven't gained, change something bigger rather than something smaller." | `helix47/prompts.py` |
| **Framing.** "Generation 140 of 150"; "improving a good start is the main way progress is made". | No countdown. The problem text becomes "building on it is one way to make progress; building a different construction is another". When the problem has a proven bound (ac2: R ≤ 1, already in its text), each line's block gives the honest room above that line's best. | `Atlas47.header`, `line_block`, `ProblemView` |
| **The real limits.** At most 200,000 steps. Base programs over 12,000 characters were cut off for the coder (67 of 420 late programs; the same bug stalled the VRP runs at 45,000). Replies were capped at 9,000 tokens. | Up to 1,000,000 steps (`max_n`; the problem module itself is unchanged). Base programs are shown up to 30,000 characters (the VRP: whole), and each line's best up to 12,000 for the planner. Replies can be 16,000 tokens (the VRP: 32,000). | `ProblemView`, `Run.program_block`, `Run.write_code` |

**Left out, on purpose:**
- **No outside information.** Nothing tells the model that better constructions are known to exist, and no record
  values appear in any prompt.
- **No problem-specific hints.** The prompts carry none, and a test audits them.
- **No extra budget.** Every program gets the same 30 s as in v4, so the comparison with v4 is like for like.

## Why this should be a strict improvement

- **Until L1 stalls, v4.7 runs v4's generation.** The allocation is the same (3 planned experiments on the one line,
  3 Mutator children from its programs), as is the budget. Only the measurement and the display differ.
- **After L1 stalls, v4 has nothing to lose.** By definition of the stall, v4's champion was gaining less than 2e-4
  (relative) per 4 generations. In the 150-generation run, generations 81–150 gained 1.4e-9 in total. v4.7 gives up
  that trickle and spends the effort on new lines.
- **The record is kept.** The final result is the best over all lines, so it can't end below the point where L1
  stalled.
- **The risk is honest.** A new line needs generations to climb, so within a short job it may not overtake. The job
  is 30 generations, and v4's lines stalled from about generation 10 (the 0.8825 trap) to about generation 40.

## Tests and checks

- `tests/test_helix47.py`, 11 tests:
  - a climbing run is v4-shaped;
  - a stalled line closes and new lines take its slots;
  - experiments follow the allocation, with bases from their own line;
  - the planner sees closed lines by name and not their scores;
  - resuming keeps the lines;
  - the findings are balanced and grouped by line;
  - the problem view;
  - the prompts are audited for problem words, and v4's prompts are unchanged.
- **The VRP:** `test_v47_runs_on_the_vrp_with_a_fake_model` (private package).
- **A real-model run** (6 generations, 10 s per program, lines forced to close quickly):
  - L1 climbed 0.818 → 0.895 and closed at generation 4;
  - two lines opened from other branches;
  - the planner's view showed only those lines, against their own previous generations;
  - its plan reasoned per line ("L2's N=480 attempts never tested the optimiser…");
  - L3 took the record at generation 6 (0.9051).

## How to read the job

`helix47/compare.py` writes `results/v47/COMPARISON.md` for each run:
- the best score by generation, and the last generation with a real gain;
- for v4.7: when L1 closed, the records set after that and how many by new lines, and the line holding the best.

**What "strict improvement" should look like:**
- v4.7 tracks v4 until L1 closes.
- After that, records keep coming, from new lines, where v4 flattens.

## What the first VRP run showed, and rule 2 (October 23, 04:15)

The VRP v4.7 job (2 runs from Code Zero) was behind v4 at generation 22–26: 1.577 and 1.503, against v4's 1.639 and
1.591. The logs showed two things.

1. **Rule 1 closed lines too early.**
   - Run 1's L1 closed at generation 6, when it gained 0.18% in 4 generations. On the VRP, v4 often gained that slowly
     and kept climbing for 30 generations.
   - Its replacement L2 climbed well (1.49 → 1.57) and was closed at generation 20 after a 4-generation flat spell.
     v4's runs had flat spells of 4–10 generations that ended in jumps.
   - The fresh line from Code Zero (L3) climbed from 1.40 to 1.577 and became the best. So fresh lines aren't the
     problem; closing lines too early is.

   **Rule 2:** patience 8. The record's line is never simply dropped: a new line opens beside it, it keeps a slot, and
   it closes only after 16 generations without a gain. That keeps the depth v4 had and still adds breadth when the
   record stalls.
2. **Both v4.7 runs were also slower in generations 1–5,** before any line had closed (1.466 and 1.469 at generation
   5, against v4's 1.522 and 1.532). With two runs each this may be chance. If it isn't, it comes from the
   always-on changes: the planner's view by line (without v4's tree of attempts), the line framing, or the targets.
   The from-scratch autocorrelation job will tell (3 seeds each). If v4.7 is slower there too in its first
   generations, the tree view comes back first.

Runs started under rule 1 keep it when they resume (`line_rule`: 1). Runs prepared by `helix47.warm` but not yet
started get rule 2.
