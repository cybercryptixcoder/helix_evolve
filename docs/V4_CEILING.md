# Is v4 building a false ceiling for itself? (atlas-s1, generations 1–150)

Shreyas's question (2026-10-22): does anything in the setup make the system try less hard the better it gets ("84 out
of 100, that's pretty good")? Could continuity itself cause it, because the model sees the whole climb? Data:
`results/v4cont/atlas-s1` (150 generations, 901 programs, 892 findings) and `results/v4/` (the first 20 generations
of all nine runs). Only v4 is analysed here.

## The short answer

Yes, there is a false ceiling, and it is built mostly by the machinery rather than by the model's mood.

- The planner's ambition did collapse.
  - At generation 5 it predicted gains of +2% ("R exceeds 0.895, vs 0.878").
  - By generation 30 it predicted +5e-6.
  - From generation 60 on, most experiments were framed as tests of whether the point was saturated ("if it stays
    exactly 0.940794, the basin is saturated").
  - "Saturated" appears in 15% of its analyses in generations 1–20, and in 95% in generations 101–120.
- But the history-free mutator stalled at the same time as the planner. Its prompt has no history, no findings and
  no lineage, so the planner's psychology can't be the main cause.
  - In generations 81–150 the wide loop (the mutator) beat its start by more than 1e-6 in 7 of 208 children.
  - The planned deep loop did so in 2 of 194.
- Four mechanisms build the ceiling. Each one feeds the next.

## The four mechanisms

### 1. New ideas are erased before anyone sees them

Every program starts from its base's construction. Every program written so far keeps the start whenever its own
search doesn't beat it within 30 s.

| Generations | Children that handed back their start unchanged |
|---|---|
| 1–40 | 31% |
| 41–80 | 50% |
| 81–150 | 72% |

So when an experiment found a new region scoring, say, 0.935 that could have climbed, the system recorded
"+0.000000, the result is the start unchanged". A promising new basin and a total failure look identical. The
memory then files it as a failure.

### 2. Every idea is judged against the champion, after 30 seconds

A child's gain is its score minus its base's score. Its base is nearly always the record line: late parents were
p0509, p0579, p0843 and their kin. A genuinely different construction needs many generations of its own climbing
before it can beat 0.9408, but it is judged on generation one. So fresh starts are punished:
- only 16 of the 210 planned experiments in generations 81–150 even tried one;
- the 2 late children below 0.93 were both recorded as failures.

Every idea in this setup has to pay off at once against the champion.

### 3. The memory turns into a wall of confirmed failures

The Distiller's findings:

| Generations | Works | Fails |
|---|---|---|
| 1–40 | 76 | 151 |
| 41–80 | 54 | 174 |
| 81–150 | 6 | 389 |

- **What the map shows.** The map shows the 45 newest findings and keeps "supported" ones. A failure that is
  confirmed is "supported". At generation 140, **all 45 findings on the planner's map were "fails"**.
- **How they read.** Many of them read "the 0.940794 point is now confirmed saturated against three more
  structurally different levers" (F495, F661, F880). Many are linked as "contradicts F495", that is, as attempts
  against the saturation claim that failed.
- **What it adds up to.** These are true statements about one basin. But nothing marks them as being about that
  basin, so together they read as "everything has been tried".
- **The size of the prompt.** The planner's prompt reached 311,000 characters, and 262,000 of those were items it had
  opened, mostly failures.

This is the "84 out of 100" effect, but it comes from the failures, not from the climb. The planner is shown only
evidence that nothing works, and it reasons correctly from what it is shown.

### 4. Microscopic gains count as wins

- **The rule.** A change counts as a gain if it beats its base by 1e-9.
- **What that produced.** Generations 81–150 logged 47 "new bests" totalling +0.0000000014. The best score moved in
  the 8th to 10th decimal place almost every generation, and polishing findings stayed "supported".
- **The consequence.** The cheapest way to get a supported finding was another polish. "Polish" appears in 333
  intents after generation 40.

### Things that make it worse

- **The problem text pushes warm starts.** It says: "improving a good start is the main way progress is made".
- **The plan format invites confirmation tests.** It asks for "a prediction the result can confirm or refute".
  Without a target, a prediction like "it stays at 0.940794" is easy to confirm.
- **The header shows a countdown.** "Generation 140 of 150" tells the planner the run is nearly over. There's no
  direct measurement of this effect, but it can only push toward safe bets.
- **The lineage line shows zeros.** It is shown every generation, and it is a row of
  "0.94079 (+0.00000: …) -> 0.94079 (+0.00000: …)".
- **The real ceiling is there too.** 30 s of CPU and at most 200,000 steps cannot reach the 400,000–1,600,000-step
  record constructions (see the record research of 2026-10-22).

### What is not the cause

Seeing the climb from 0.667 is not the problem. The planner rarely refers to the starting score. Its anchor is the
current record, which is printed to six decimals everywhere, and its predictions are almost always "the record plus
something tiny".

## The same thing at the start: the 0.8825 basin

In the first 20 generations, 4 of the 9 runs (atlas-s3, journal-s3, control-s1, control-s3) reached about 0.882 by
generation 1–10 and ended at 0.8824–0.8825. The same mechanisms trapped them early: a basin that everyone warm-starts
from, and children judged against it. The runs that escaped (atlas-s1 to 0.939, journal-s1 to 0.934) did so through a
lucky early jump. That luck is what makes the seeds look important (see below).

## Structural fixes (not just wording)

Each fix addresses one mechanism. With these, "there is room" becomes true for every new idea by construction,
rather than something we tell the model.

| # | Fix | Mechanism it removes |
|---|---|---|
| 1 | **Keep what an experiment found, not only what it returned.** A program may also hand back its best alternative construction (`construct` returns the best, plus an optional `alternative`). The evaluator scores both. An alternative from a different region becomes its own program in the archive, so it can be continued. | 1 |
| 2 | **Challenger lines.** One experiment per generation goes to a challenger line: a lineage started fresh or from an alternative. Its planner sees that line's own best and history, and the shared findings, but not the global record. It is judged against its own previous generation (Shreyas's idea), for several generations, before it is compared with the champion. | 2 |
| 3 | **Findings are scoped and balanced.** A failure found on a basin is tagged with that basin and shown as "tried on the 0.9408 basin", not as a general truth. The map has quotas: at most 15 failures, grouped ("31 levers tried on the 0.9408 basin, none moved it"); always the best "works" and "mechanism" findings; always the open questions. A finding about one basin can't be "supported" as a statement about the problem. | 3 |
| 4 | **A noise floor for gains.** A change counts as a gain, and a record as a record, only above 1e-6 (relative). Smaller changes are "no gain", and the run's best stays put. | 4 |
| 5 | **An ambition slot.** Each plan has one step-change experiment, aimed at +1e-3 or more, with a larger budget (or continued over several generations). It is judged on its own line, not against the champion at 30 s. | 2, 4 |
| 6 | **Wording.** Replace "improving a good start is the main way progress is made" with "building on `start` is one option; a new construction is another; both are judged". Drop "of N" from the header. Ask for predictions as targets ("aims for at least …"), not as confirm-or-refute tests. Show the true, honest room every generation: "proven upper bound 1.0; current best 0.9408; gap 5.9%". | 3, framing |
| 7 | **Raise the real ceiling.** Allow up to 2,000,000 steps, and give challenger and ambition experiments a longer budget (minutes, not 30 s). | the real limit |

Fixes 1–4 are the core. Fix 6 alone would change wording and little else, because the evidence the planner sees would
still be a wall of failures. On whether to tell the model "better constructions are known to exist": it is true (0.96
has been published) and it is not a solution. But it is outside information that AlphaEvolve's comparable runs didn't
get, so it is Shreyas's call, and it is left out of the fixes above.

## Seeds

- **What it is.** A seed is one integer per run (`--seed 1`, stored in `state.json` as `config.seed`). It is a run
  label and the key for one random generator: `random.Random(seed * 7919 + gen)` in `helix4/run.py`.
- **What it controls.** It decides which programs the wide loop picks as parents and as "inspiration" each
  generation. That is all.
- **What it is not.**
  - It is not a file.
  - It is not a system prompt.
  - It is not a weighting of prompts.
  - It is not a starting solution: every run starts from the same Code Zero (0.667).
- **The models ignore it.** The model calls are not seeded at all: they sample at temperature 0.5–0.8, and the API
  doesn't take a seed. So re-running "seed 1" gives a different run, and there is no space of good seeds to search.
- **Where the run-to-run spread comes from.** The spread (0.882 to 0.939 after 20 generations) comes from the models'
  own randomness, mostly in the first generations: which basin a run falls into first. The other runs called "s1"
  (journal-s1, control-s1) are not related to atlas-s1; control-s1 is the worst run.
- **The consequence.** Results need several runs per condition, and an outlier run says little about a setting.
  Fixing the trap mechanisms (2 and 3 above) should also shrink this spread, because a run stuck in a basin could
  still leave it.

## How much the system prompt matters

Two kinds of input should be kept apart:
- **The system prompts:** the fixed instructions (`helix4/prompts.py`).
- **The context:** what is shown each generation (the best program, the map, the findings, the results).

The evidence says the context and the structure matter far more than the wording of the system prompt:
- **Control, journal and Atlas use identical system prompts.** They differ only in context. The context decided which
  memory method won.
- **The mutator stalled at the same generation as the planner.** It has a short system prompt and no history. What
  stopped it was the warm start, the 30 s budget and the champion comparison, not its instructions.
- **Wording does matter in two ways:**
  - It can break things outright. One sentence in the v4.6 prompt caused 32,000-token thinking spirals, fixed by
    restoring the earlier guard wording.
  - It shapes how plans are framed. "A prediction the result can confirm or refute" is where the saturation-test
    style of the late plans comes from.

So a better system prompt can remove a failure mode or improve the style of the plans. It won't move a stalled run
by itself while the structure keeps erasing new ideas and judging them against the champion. A cheap check, if
wanted: 2 runs × 20 generations with the fix-6 wording only, against 2 with fixes 1–4. Under this analysis, the
wording-only runs should stall the same way.
