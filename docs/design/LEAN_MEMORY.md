# Design note: memory and context (P1, P2) — for discussion

Status: a proposal (Nov 6, 2026). Nothing here is built yet.

## The problem, as stated

- **P1 (continuity).** Each round, the model starts from scratch: it doesn't know what was tried or learned.
- **P2 (context).** Not everything can be shown, so something has to choose what the model sees.
- **The bar (Shreyas, Nov 5).** No fixed architecture (no graph, no Atlas): something that intuitively makes sense
  for the job.

## What memory is for, concretely

1. **Not repeating what failed:** "tried smoothing the max with a log-sum-exp; it gave nothing".
2. **Carrying a lesson forward:** "more steps helped up to about 2,000, then hurt within 20 s".
3. **Knowing which lines are still open:** "the comb-plus-spike shape was never polished".

The planner already sees the strongest programs' code. That code is the memory of what works. What it lacks is
1-3.

## What we know (`docs/LEAN_RESULTS.md`)

The only memory tested so far is **plain notes**: one line per program, written by code (what it tried, what it
gave), clipped to 20,000 characters. Against the same setup without notes:

| Problem | Effect of notes |
|---|---|
| 26 circles | no difference |
| 32 circles | worse: 2 of 3 seeds at the best known, against 3 of 3 |
| AC1 | worse: last place, median 1.5225 against 1.5137 |
| AC2 | better: median 0.9045 against 0.8825; the best run of all |

They also cost 14-29% more tokens. A likely reason they don't help: they are a long, unranked log, and the model
has to work out the lessons itself, every round.

## Options, simplest first

| | Memory | What the planner sees | Size | Who writes it |
|---|---|---|---|---|
| M0 | none | the strongest programs | - | - |
| M1 | notes (tested) | one line per program | grows; the oldest are cut | code |
| M2 | **a lab notebook** | at most 15 short findings, each citing the programs that show it ("smoothing past 1e5 hurt: p0041, p0057") | fixed | the model, once a round, rewriting the previous notebook with the round's results |
| M3 | **the best program's path** | the ideas along the best program's ancestry, each with what it gained | short: one line per ancestor | code |

- **M2 answers 1-3** in the way a person would keep a notebook. It solves P2 by construction, because its size is
  fixed. The risk: the model writes wrong conclusions, and nothing checks them. The citations make each finding
  traceable.
- **M3 is the cheapest real alternative.** It costs no extra model call. It answers "how did we get here", but not
  "what failed".

## The test

- **Setup:** plan (the base setup, if experiment 5 confirms it), with M0, M1, M2 and M3.
- **Problems:** 32 circles and AC1.
- **Seeds:** 5 each. Three seeds are too few here: experiments 1-4 showed seed spreads larger than the gaps
  between setups.
- **Measures:**
  - the best after N programs;
  - tokens;
  - a repeat rate: the share of planned experiments whose idea repeats one tried before, judged against the
    notebook's own citations.
- **Cost:** 40 runs, about 7 hours on the VM and here together.

## For Shreyas

1. Does the lab notebook (M2) match what you meant by "something that intuitively makes sense"?
2. Or should we first test the cheaper question: does any memory beat none (M0 against M3) before building M2?
