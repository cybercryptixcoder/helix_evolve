# The v7 runs (October 23–24, 2026): what happened

Two v7 runs ran side by side for 100 generations each (`docs/V7_JOB.md`):
- the autocorrelation run continued v47-s2 from generation 190 (results: `results/v7warm/`);
- the VRP run started from the best VRP program so far, on fake data. The VRP data stay off GitHub; the numbers here
  come from the run archive.

The question was whether v7 did what it was built to do, and where its gains came from. The reasoning about what to
do next is in `docs/SEARCH_SPACE.md`.

## The headline numbers

| | Start | After 100 generations | Gain |
|---|---|---|---|
| Autocorrelation R | 0.9412297 | **0.9412521** (p0941, verified three ways) | +2.2e-5 (+0.0024%) |
| VRP score, training worlds | 1.644336 | **1.650480** (p0601) | +0.37% |
| VRP score, held-out worlds | 1.6960 | **1.7060** | +0.59% |

- **Autocorrelation:** the human record (Jaech & Joseph, 0.94136) is still about 0.00011 above. The best known (about
  0.9626) is 2.3% above.
- **VRP:** the best current method (greedy plus simulated annealing) scores 1.3863 on the held-out worlds, so the new
  best is 21.6% better in quality.

## Did v7 do what it was built to do? Yes

- **Levels followed the stall.**
  - VRP: level 0 for generations 1–4, rising to 1 and then 2 as the record stalled. Back to 0 for generations 27–30,
    after a record, and for 80–100, while the new main track climbed.
  - Autocorrelation: the run's own rhythm (records every generation at 177–181) made its typical gap 1, so after
    generation 194 it was at level 2 in 93 of 100 generations.
- **The main track always kept a slot.** Nothing was closed: 74 side tracks opened on the autocorrelation run, 59 on
  the VRP run. Tracks paused and woke again.
- **Side tracks took the record:**
  - autocorrelation: T27 at generation 289;
  - VRP: T17 at generation 26, and T40 at generation 79.
- **Worse, then better, happened as intended on the VRP.**
  1. T40 opened at generation 57 with a bold change that scored 0.14% below its base.
  2. Its follow-up found a bug in it and gained a little, then T40 paused.
  3. At generation 79, the wide loop (which, at level 2, samples one parent from a side track) mutated T40's program
     and gained 0.23%. T40 took the record.
  4. The next generation gained another 0.21%, and T40 climbed for the rest of the run.

  Under v4.7's rule 1, T40 would have been closed at generation 58.

## Where the gains came from

### VRP

| Planned or not | Experiments | Any gain | Gain above 0.05% |
|---|---|---|---|
| mutation (wide loop) | 300 | 98 | 22 |
| main | 166 | 25 | 1 |
| track (continue a side track) | 75 | 38 | 12 |
| revive | 20 | 3 | 0 |
| backtrack | 20 | 10 | 0 |
| bold | 19 | 1 | 0 |

- **The run's one change of hill came from a bold experiment that varied something every program shared.** Its
  hypothesis began: "Every program in the tree seeds from a myopic greedy ... and then repairs with local search, so
  all of them converge to the same ... plateau." It replaced the shared starting construction. The program was worse
  at first; the hill showed only after a later mutation fixed the new start's scoring.
- **The planner reasoned this way in 9 bold or main experiments**, each naming a component that every program
  shared:
  - the starting construction;
  - the passive route pool;
  - the frozen trip structure;
  - the fixed truck counts;
  - a neighbourhood never optimised exactly;
  - and others.

  Most started slightly worse, got one follow-up, and paused. Only T40 was woken.
- **Revive barely helped** (3 tiny gains in 20). **Backtrack** went to recent states and gave only small gains.
- **Programs grew** from 55,860 to 132,360 characters, about 900 a generation, past the 90,000 the coders are asked to
  stay under. A long VRP run will soon reach what one reply can hold.

### Autocorrelation

| Planned or not | Experiments | Gain above the floor | Ended at the record's level |
|---|---|---|---|
| mutation (wide loop) | 300 | 68 | 135 |
| main | 112 | 10 | 98 |
| track | 114 | 31 | 42 |
| revive | 25 | **0** | 22 (all within 2e-8 of the record they started from) |
| backtrack | 25 | 3 | 14 |
| bold | 24 | 10 (on their own low bases) | **0** |
| alternatives kept | 53 | 7 | 10 |

- **The last record came from a short step back, not a restart.**
  - T27 backtracked at generation 218 to p0297, the record of generation 191, one generation before the main track's
    best.
  - Seventy generations later, two mutations and a main experiment on it, using a different polishing method,
    gained 1.1e-5.
- **Every restart from scratch fell into the same well.** All 24 bold experiments started from Code Zero. The 19
  tracks they opened peaked between 0.687 and 0.8825; 0.8825 is the textbook construction f = x^(-1/2). None came
  near 0.94.
- **Backtracks went one step back.** All 25 backtrack roots scored at least 0.9395, and 12 of them were within 1e-6 of
  the record at the time.
- **68% of children handed back their start unchanged** (377 of 558, alternatives aside). That's the same pattern v4
  showed (72%). A failed idea leaves no measurement of how far it fell.
- **The ideas were concentrated.**
  - Of 653 experiments, about 80% mention the peak window or plateau of f∗f, about 70% a change of resolution, and
    about 65% gradient or quasi-Newton polishing. The counts are from keywords, so they're rough.
  - Exact solvers (LP, fractional programming) appear in about 3%, new parameterisations in 15%, and combining two
    constructions in 5%.
  - The best construction kept its 42,496 steps throughout. One planner noted that it is an exact 4x staircase, so
    the function itself has about 10,600 steps.
- **The planner almost never questioned what every program shared:** 3 times in 100 generations, against 9 on the
  VRP. The bold slot's wording offered "Code Zero, to build from nothing", and the planner took it literally every
  time.

## What this says

- **v7 behaved as designed.** Exploration ran in most generations, nothing was closed, and paused tracks came back.
  The VRP's biggest gain is exactly the "it kept working underneath, then jumped on another path" pattern.
- **The system was not restarting from scratch at every stall.**
  - Its backtracks were short steps.
  - Its from-scratch restarts all landed in the model's default basin: 0.8825 on the autocorrelation problem, Code
    Zero's level on the VRP. The one exception, a VRP restart that rebuilt most of the chain in 5 follow-ups, reached
    1.635, just below the hill it came from.
- **What moved the search to a new hill was changing a component that every program shared, and then climbing.** It
  worked once, by luck of a mutation, after being judged and paused once. Revive, as built, contributed almost
  nothing.
- **Small-scale comparisons between versions would mostly measure the model's randomness.** These event-level
  readings (which mechanism produced which gain) say more.

## Smaller findings

- **The VRP report's "Records" table counts generation-to-generation gains above the floor** (1 record). The stall
  clock counts creeps that add up (records at 26, 79, 80, 93). The report should use the same definition.
- **The VRP's measured noise was 0.0012%**, so its floor was the 0.05% minimum. Most of the VRP's gains were smaller
  than that, and were kept and built on without counting as records.
