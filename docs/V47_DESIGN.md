# Helix v4.7: v4 without the false ceiling

v4.7 is a variant of v4, not a new architecture. Its loop, roles and Atlas memory are v4's. It removes the
mechanisms that `docs/V4_CEILING.md` found building a false ceiling in the 150-generation atlas-s1 run, together with
the cut-off found in the VRP runs. Code: `helix47/` (it reuses helix4 and changes nothing in it). Tests:
`tests/test_helix47.py`. The job: `scripts/run_v47_jobs.sh` and `docs/V47_JOB.md`.

## The design principle: leave a climbing run alone

v4.5 turned on breadth (branch and explore slots) every generation, and it started slower than v4 (`docs/V5_RESULTS.md`).
v4.7 avoids that by splitting its changes in two:
- **Always on:** fixes to how results are measured, shown and kept. They don't take any experiment away from the
  search.
- **On only while the search is stalled:** a step-change slot and a challenger line. They take one deep slot each
  from the main line, but only while the main line has stopped producing gains.

A run is stalled when its best score rose by less than `stall_gain` (2e-4, relative) over the last `stall_gens` (3)
generations. In the v4 run:
- generations 1–40: rarely stalled;
- generations 41–150: stalled throughout;
- the early 0.8825 trap of four v4 runs: stalled within 3 generations of reaching it.

## The changes, one per mechanism

| Mechanism in v4 (`docs/V4_CEILING.md`) | The change in v4.7 | Where |
|---|---|---|
| **New ideas are erased.** Programs fall back to their start when their idea doesn't beat it in 30 s; 72% of late children handed back the start unchanged. | `construct` may return `{"best": ..., "alternative": ...}`. The alternative is scored. If it is different from the result and from the start, and scores at least 0.9 of the start, it is kept as its own program (role `alt`, with its own construction), so later experiments can continue it. Coders and Mutators are told about it. | `helix47/evaluate.py`, `Run.child`, `prompts.ALTERNATIVE_RULE` |
| **Everything is judged against the champion, at once.** A new region is compared with 0.9408 on its first try. | **The challenger line.** When stalled, one deep slot goes to a lineage started fresh (Code Zero), from an alternative, or from the best of another branch. It is planned by its own planner. That planner sees its line's programs and best, and the shared findings, but not the overall record. The line is judged against its own previous best, with twice the budget. It ends when it takes the record (merged into the main line), after `line_patience` (4) generations without a gain, or after `line_max_gens` (12). If the search is still stalled, a new line starts. | `Run.start_line`, `challenger_experiment`, `update_line`, `Atlas47.challenger_view` |
| **The memory becomes a wall of failures.** At generation 140 all 45 findings on the map were failures, many "confirmed saturated". | Failures are scoped: each "fails" finding is shown with the construction it was tried on, and its status reads "held: N didn't gain" rather than "supported". The map has quotas: the 12 newest failures; the 12 best and 8 newest "works"/"mechanism" findings; 6 open questions. Older failures are grouped by construction into one line each: "31 more failures tried on the construction scoring 0.9408 … facts about that construction, not about the problem". The Distiller is asked to name the construction a failure was tried on and not generalise. An opened finding shows its 12 newest pieces of evidence (v4's opened items reached 262,000 of a 311,000-character prompt). | `helix47/memory.py` |
| **Microscopic gains count as wins.** 47 "new bests" in generations 81–150 added up to +1.4e-9. | A noise floor, `gain_floor` = 1e-6 relative. A change counts as a gain only above it: in finding statuses, in the history's gain counts and `new_best`, in the lineage shown to the planner, and in the feedback ("below the noise floor: counts as no gain"). | `memory.outcome`, `Run.generation`, `Run.child` |
| **The planner's targets collapse** (+2% at generation 5, +5e-6 by generation 30; later experiments were tests of saturation). | Predictions are targets: "the score this aims for". The system prompt says a failure is about the construction it was tried on, and that an experiment designed only to confirm the best can't be improved wastes a slot. When stalled, exactly one experiment per plan is a **step-change**: aimed at +1e-3 relative or more, with twice the budget. Its coder returns the new construction as the alternative, so it is kept either way. The step slot is enforced by code: if the plan marks none, the last experiment becomes it. | `helix47/prompts.py`, `Atlas47.plan`, `Run.experiments` |
| **Framing.** "Generation 140 of 150"; a lineage line of "+0.00000" rows; "improving a good start is the main way progress is made". | No countdown ("Generation 140"). The lineage shows only the steps that gained, and counts the rest. The problem's own sentence becomes "building on it is one way to make progress; building a different construction is another". When the problem has a proven bound (ac2: R ≤ 1, already stated in its text), the header gives the honest room: "the best score so far is 0.940795, so up to 5.9% of the range is still open". | `Atlas47.header`, `lineage_gains`, `ProblemView` |
| **The real limits.** At most 200,000 steps. Base programs over 12,000 characters were cut off for the coder (67 of 420 late programs in v4; the same bug stalled the VRP runs at 45,000), and replies were capped at 9,000 tokens. | Up to 1,000,000 steps (`max_n`; the problem module itself is unchanged). Base programs are shown up to 30,000 characters (the best program, for the planner, up to 14,000). Replies can be 16,000 tokens. Step-change and challenger experiments get twice the budget. | `ProblemView`, `Run.program_block`, `Run.write_code` |

**Not in v4.7, on purpose:**
- **No outside information.** Nothing tells the model that better constructions are known to exist, and no record
  values appear in any prompt.
- **No problem-specific hint.** The prompts were audited, and a test checks them for problem words.

## Why the model needs this: it is also the model that says "it's hit a wall"

The model in the loop, DeepSeek V4.1 Flash, is also the model behind Shreyas's Hermes agent. Hermes calls a
flattening curve a ceiling every time it sees one, and the planner did the same: "saturated" appears in 15% of its
analyses in generations 1–20 and 95% in generations 101–120.

That looks like a stable disposition of the model: read a plateau as a limit. So v4.7 doesn't rely on persuading it.
- The noise floor, the scoping and the balanced map change what it is shown.
- The challenger's planner never sees the plateau at all.
- The step slot and the challenger slot are assigned by code, not by its judgement.

Its belief can stay pessimistic, and the search still tries the things a pessimist wouldn't.

## What v4.7 costs

- **While climbing:** the same as v4. The same 6 programs and the same calls; replies may be longer.
- **While stalled:** one extra planning call (the challenger), and two of the six programs at twice the budget. That
  is about 1.33 times the evaluation time of a v4 generation.

## How to read the job

`helix47/compare.py` writes `results/v47/COMPARISON.md` for each run:
- the best score by generation;
- the last generation with a real gain (more than 1e-5 relative);
- for v4.7: the lines started, how many took the record, the alternatives kept, and the generations stalled.

**What "strict improvement" should look like:**
- While climbing (generations 1 to about 20), v4.7 tracks v4.
- From the first stall on, v4.7 keeps having real gains where v4 flattens.
- Lines take the record now and then.

Three seeds per version is little, given how much runs vary (`docs/V4_CEILING.md`, "Seeds"). So the per-run
mechanisms matter as much as the medians: alternatives kept and continued, lines that gained, records taken by
lines or step-changes.
