# Plan: a domain knowledge bank for lean Helix, and a run with it (November 9, 2026)

## What Shreyas asked

- **A knowledge bank** in lean Helix: the field's knowledge of the problem (the state of the art, what works best,
  the strongest heuristics and exact methods), so the agents can use more than what the model remembers.
  Knowledge, not programs: inspiration programs would bias the search towards copying.
- It sits **beside the Atlas** (which holds what this run learns); the agents are told to use it to improve the
  programs.
- **Lean and clean:** a small addition to the core; v4's prompts unchanged except one added block.
- **A run** on the fake VRP data: generation 0 is all our good programs together; the score is cost only; programs
  never see the clock and must stop by themselves, under a maximum duration; started without waiting for approval.

## Design

### The bank (core, `lean/knowledge.py`)

- A problem may supply `knowledge`: a Markdown text of entries, each `## K<n>: <title>` followed by its text. No
  `knowledge`: nothing changes (tested).
- **The planner** sees the whole bank in its prompt (before its instructions), introduced by one sentence: "The
  field's knowledge of this problem: use it to design experiments. Cite the entries an experiment draws on in its
  `knowledge` field." An experiment's `knowledge` field (e.g. `["K3", "K7"]`) is kept in `plans.jsonl`.
- **A coder** gets the full text of the entries its experiment cites (so the method is implemented as described).
- **A mutator** (no planner) sees the whole bank too. With `inspiration: "knowledge"` (a run setting; the default
  stays v4's), a mutator is no longer shown "another strong program, for ideas": the bank is its only inspiration, so
  the starting programs are the population, never a model shown again and again (Shreyas, 12:04).
- **The Atlas is unchanged.** What the run learns about using an entry ("K5 tried: the truckload model did not
  help") goes into the Atlas through the Distiller, as any finding does.

### The VRP bank (`helix_vrp/knowledge/vrp.md`)

Filled by hand from online research (Shreyas: the person setting a run up fills the bank; it holds the field's
knowledge and the problem's facts, never our programs). 19 entries, each a few paragraphs, with sources: the problem's family (heterogeneous fleet,
site-dependent, split delivery VRP); the state of the art (hybrid genetic search, SISR ruin-and-recreate, ALNS,
set-partitioning matheuristics, branch-price-and-cut, column generation); the split-delivery results (full truckloads,
when splitting pays, known heuristics); fleet sizing and mix; lower bounds; and the facts of this problem (most of the
cost is trucks; most trips are full loads). Plus the three directions no program has tried so far (column generation,
a truckload model, combining whole solutions), as knowledge, not as orders.

### The run (`helix_vrp/lean_knowledge.py`)

- **Rules: the uncapped variant's.** Cost only (Q); the clock is blocked (static check and at run time); the
  safety limit is raised to 30x each instance's usual time (120, 210, 360 CPU seconds) so that no program fails for
  taking somewhat longer (cost first, time second); a program that hits it fails.
- **Generation 0: the population.** p1010, p0200, p0280, p0174, p0095 and p0498 (uncapped family), p0092 and
  p0324 (combined), p0204 (scaling), p0403 (fast), p0152 and p0175 (as is). Programs that already stop by themselves
  enter as they are; the others are first converted by the coder to stop by themselves (as p1010 was for the
  uncapped run; each conversion is kept, so a restart does not redo it). A program that cannot be converted in six
  attempts is left out, and the run's log says so.
- **Memory:** the Atlas, started empty. **Settings:** lean's (3 planned + 3 mutations per generation), with
  `inspiration: "knowledge"`.
- **Where:** Colab (8 cores), for about 12 hours, its records relayed to `helix_vrp_private` at each 9-minute
  check-in as before.
- **Readable scores** (total cost, CPU, scaling) and the chart cover it like every run.

## Checks

- The core tests still pass (a problem without a bank gives the same prompts as before).
- A new test: the planner and mutators see the bank, a coder gets exactly the cited entries, the field is kept.
- Live: the run's generation 0 and first generations on Colab, with the bank in the planner's prompt and cited entries
  in plans.
