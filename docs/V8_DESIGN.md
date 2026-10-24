# Helix v8: v7 plus a register of hills (October 24, 2026)

Code: `helix8/`. Tests: `tests/test_helix8.py`. The jobs: `docs/V8_JOB.md`. The reasoning behind it:
`docs/SEARCH_SPACE.md`. The request: `docs/BRIEF_2026-10-24.md` (the second message).

## What it is for

Helix climbs well. What it lacks is a reliable way to find a new hill, and to tell a new hill from the one it is
already on or one it has already found. In v7:
- restarts from scratch all fell into the same well (19 of 19 on the autocorrelation problem, at or below 0.8825);
- revive tracks were judged against unchanged copies of the record;
- the one real change of hill (the VRP's T40) was found by chance and judged after one follow-up.

Shreyas asked for something surgical:
- at least as good as v4 and v7;
- no new architecture;
- elements added that target exactly this: discovering new hills one after another, testing reliably that each is
  new, and not redoing work.

## What it adds to v7, and nothing else

### 1. A hill is defined by what the program produces, measured by code

Two programs are on the same hill if their outputs are nearly the same. The model never judges this.

- **The autocorrelation problem: the shape of the construction.**
  - The support is trimmed and rescaled to [0, 1], the mass normalised, and the shape resampled to 64 bins,
    preserving mass.
  - The distance is the total-variation distance, taking the closer of the two orientations (mirroring doesn't change
    the score).
  - It ignores scale, padding, mirroring and resolution: a 4x staircase of a construction is the same shape.
- **The VRP: the trips the solutions are made of.**
  - Each trip is reduced to its truck type and the set of villages it serves, hashed.
  - The distance is 1 minus the mean, over instances, of the Jaccard similarity of two programs' sets of trips.
  - Only the hashes leave the evaluator, never ids or names.

**Calibration**, before choosing the radii:

| Problem | Pair | Distance |
|---|---|---|
| Autocorrelation | the textbook 0.8825 constructions of 6 different earlier runs | ≤ 0.04 of each other |
| Autocorrelation | v4.7's record against v7's (100 generations of polishing) | 0.06 |
| Autocorrelation | the bests of genuinely different runs | 0.09–0.6 |
| VRP | the same program evaluated twice | 0.02 |
| VRP | steps along one climb | 0.03–0.08 |
| VRP | the change of hill at generation 79 (a new starting construction), from its base | 0.20 |
| VRP | a restart that rebuilt the chain, from the record | 0.33 |
| VRP | Code Zero, from everything | 0.84 |
| VRP | v7's bold "shared decision" changes of generations 44 and 54, from the record of generation 47 | **0.007** |
| VRP | v7's bold change of generation 57, from its base | **0.000** |

The last two rows mean those changes barely changed, or didn't change, what the program produced. The planner of
generation 58 diagnosed the last one itself: the new start had never activated. v8 reports this at once.

**Radii:** 0.075 for the autocorrelation problem and 0.12 for the VRP. Each is raised, at most to twice its value, if
the run's own steps along a climb turn out larger: twice their median.

### 2. A register of hills (`hills.jsonl`)

- **What each hill records:** its top (best program), who found it and how, when, how often other tracks landed on
  it, and a description of its design.
- **The starting program's hill is fixed**, so a restart that ends up back at Code Zero is recognised.
- **Each track's best is placed after each generation:**
  - **on the nearest known hill**, if within the radius. That is a landing; if the track beats the hill's top, the
    hill's top moves to it;
  - **on a new hill**, if far from every known hill after its opening and at least one follow-up. Until then it is a
    candidate;
  - **a track that carries a hill** (it founded it, or holds its top) moves that hill's top as it climbs, so a long
    climb is one hill, not one hill per step. If it climbs into another known hill below that hill's top, it is
    recorded as landing there.
- **On a warm start**, the first generation registers the hills the run already knows: every earlier track's best is
  placed. On the VRP, the record, Code Zero and the 12 best earlier tracks are evaluated once more to get their
  signatures (about 15 minutes).

### 3. A side track's best counts only programs that changed their start

A child whose output is the same as its base's (an idea that failed and handed back its start) no longer counts
towards its track's best. In v7, all 22 valid revive programs handed the record back unchanged. Each revive track's
best was therefore the record itself, and no follow-up could ever gain. That is why revive looked dead.

### 4. The exploration slots

v7's levels still decide how many there are. What they do:

- **flip (replaces revive):**
  - change one design decision that every known hill shares, on the record or on another hill's top, keeping the
    rest, so the chain of improvements carries over and nothing is redone;
  - the options come from the Cartographer's scan (below); revive's findings are offered as well;
  - if the result doesn't beat its start, the program hands back the construction the change produced, so it is
    measured.
- **restart (replaces bold):**
  - a design unlike every known hill;
  - the planner and the coder see the map of known hills (with descriptions and how often each was reached), and the
    record's whole chain of improvements to apply in this one program where they fit;
  - a restart that lands on a known hill below its top stops at once: the hill's count goes up, and the planner sees
    it.
- **backtrack (v7's):** each option is now shown with the hill it is on, or how far it is from the nearest.
- **continue a side track (v7's):** the slot and the coder now say where the track stands. Still on a known hill
  ("the change has not moved it off that hill yet; make the change take effect"), a candidate new hill, or a hill it
  founded.

**Flips and restarts get 2 follow-ups without a gain before they pause** (v7: 1). Other kinds keep v7's 1.

**Explorations keep alternative constructions down to half their start's score** (v7: 0.9), so a flip's own result
is never lost.

### 5. The Cartographer: one model call, when needed

- **When a hill is found:** it describes, in at most 3 sentences, which design decisions the hill's top makes
  differently from the record's.
- **While the run explores** (every 5 generations, or 2 after a new hill): it lists up to 8 design decisions that
  every known hill's top makes the same way, with the option they all use and two alternatives. These are the flip
  slot's options.

### 6. The planner's view

v7's view plus:
- **the map:** the known hills, their tops, how each was found, how often other tracks landed on it, and its
  description;
- **the shared decisions**, each marked with where its flips landed;
- **each side track's place on the map.**

The system prompt explains hills and the four kinds of exploration.

## What stays exactly as in v7

- **Unchanged:**
  - the roles;
  - 3 planned experiments and 3 mutations per generation;
  - the stall levels and the run's own typical gap;
  - the main track's guaranteed slot;
  - tracks that are never closed;
  - the wide loop (sampling, side parents at level 2);
  - the noise floor and the VRP's calibration;
  - alternatives, warm starts, the Atlas and its Distiller.
- **While the record climbs (level 0), a generation is v7's**, apart from the map in the planner's view.
- **The budget that moves is the exploration that produced nothing in v7:** revive (0 gains on the autocorrelation
  problem), and restarts that fell into known wells.

## Risks to watch

- **The shape is one description of a hill.** Two different designs can produce nearly the same output, and then
  they are one hill here. That is the intended meaning: same output, same hill. A design change that doesn't change
  the output is reported as such, and that is the useful signal.
- **The Cartographer's shared decisions are only as good as the model.** When it lists none, the flip slot asks the
  planner to name one, which the VRP's planner did unprompted 9 times in v7.
- **Hills multiply if the radius is too small.** The radius follows the run's own climbing steps, and the report
  shows every hill and its founder, so an over-split map is visible.

## Files

| File | What |
|---|---|
| `helix8/hills.py` | the shape signature and distance |
| `helix8/run.py` | `Config` and `Run`: signatures, moved-only bests, the register (place, land, carry, seed), the Cartographer, the map, flip and restart slots, the generation |
| `helix8/prompts.py` | the planner's system prompt, the slot texts, the coder's notes, the Cartographer's prompts |
| `helix8/warm.py` | continue a v7 (or earlier) run as v8 |
| `helix8/report.py` | v7's report plus the map |
| `scripts/run_v8_warm.sh` | the autocorrelation job |
| (private) `helix_vrp/run_vrp.py` `install8`, `evaluator.py` `solution_signature` | the VRP |
