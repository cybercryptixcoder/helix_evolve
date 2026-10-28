# Helix v10: v9 plus the field's knowledge (October 28, 2026)

Code: `helix10/`. Tests: `tests/test_helix10.py`. The job: `docs/V10_JOB.md`, `scripts/run_v10.sh`. The research it
borrows from: `docs/AC2_SOTA.md`. The request: `docs/BRIEF_2026-10-28.md`.

## What it is for

The October 28 discussion (docs/CONVERSATION_2026-10-28.md) left a hypothesis: Helix's runs plateau at 0.94144
because every hill shares assumptions that are not axes on its map, and the axes that matter can be borrowed from
the field once per problem, by deep research, then searched by the machinery (the third level of borrowing: an idea
as an axis, not a construction and not code). v10 tests it, in two runs that differ in one thing:

| Run | Gets | Tests |
| --- | --- | --- |
| **v10-axes** | the field's design decisions on the map, the field's findings in the Atlas | whether concepts alone move the search past its own prior |
| **v10-warm** | the same, plus the field's constructions (the record 0.963588 and 13 others) and the field's methods as programs | whether the system can go past the world record from the world's best starting point |

Both continue v9-s1 (generation 800, record 0.9414417) with everything it knows, so their difference is only what
the field gives them.

## What stays (v9, unchanged)

The roles, 3 planned experiments and 3 mutations a generation, tracks, the register of hills, the Atlas, the design
map (codebook, annotator, landscape model, drops, flips, ablations, read-back, discovery, upkeep), the race, the
queue, the continuation pack and the vault.

## What v10 adds

| Part | File | What it does |
| --- | --- | --- |
| The field's knowledge | `sota.py` | 9 design decisions with 38 options (objective, the smooth max, the optimiser, positivity, resolution moves, the envelope, the comb, escapes, where the step aims), 14 findings with sources, 14 constructions; all from `docs/AC2_SOTA.md` |
| Borrowed axes | `warm.py` | An option goes on a decision the map already has when it has one for it (5 of 9 here: objective, optimiser, positivity, resolution, where effort goes); otherwise a new decision (4: the smooth max, the envelope, the comb, escapes). Listed in `borrowed.json` |
| Exploration biased to them | `run.py` | Every borrowed option is tried once as a flip of the record before the map's own choices take over (coverage, least-tried first, decisions in turn), then about half of the new explorations target a borrowed option. The slot tells the planner the option comes from the field and gets 3 experiments before it is judged |
| Always on the table | `run.py` | The planner's design table always lists the field's decisions and options, marked, with "untried" until a program here uses them; upkeep never merges a borrowed option away into one of the run's own |
| The field's findings | `run.py` (AtlasField) | 14 findings of kind "field", with sources, shown to the planner as their own block: the records, how R grew with n, the methods and how far each went, the measured dead ends, the structure of the best constructions. The Atlas now knows how far the known approaches go |
| The warm mode | `warm.py`, `field.py`, `programs/` | The field's 14 constructions (verified by SHA-256 and by re-scoring, from `data/field_ac2`) become programs with their own tracks (paused, open to backtracks; each a hill at the first generation); the field's three methods (iterated Dinkelbach; velocity cycles; repeat + pad to the cap + polish), rewritten for one CPU core, run once on the record (and the transfer on Hyra's), and the main track starts there: the coder starts from the field's own polish code |

## v9's failures, fixed

| v9 (docs/V9_RESULTS.md) | v10 |
| --- | --- |
| The race was captured by copies of the record: flips and ablations that landed on its hill kept being promoted; 35 of 100 generations had all three racing slots on it | Any racing exploration that, after its first rung, sits on a known hill below that hill's top stops racing (v9 stopped only drops and restarts) |
| New explorations got one experiment and waited in the queue: a new region was never climbed | The first rung is 3 experiments (v9: 2), and a track below its first rung is never sent to the queue |
| About 70% of the experiments worked on the record's hill | At most one of the wide loop's three bases a generation sits on the record's hill; at least two of the three planned experiments explore, every generation (v9: none while the record climbed) |
| The map's upkeep ran every generation (with the annotator, a fifth of the tokens) | Upkeep every third generation; a decision is tidied above 12 options (v9: 6) |

## Constructions up to 2,000,000 steps

The arena's cap (v9: 1,000,000). A 2M construction is 16 MB; a run makes hundreds. So: a large construction handed
back unchanged is stored as a reference to its start (`constructions/<id>.ref`, and `refs.jsonl`, published); a large
construction nothing needs any more (not a hill's top, a track's best or root, the 12 best, a recent base, or an
import) is removed two generations later (`gc.jsonl`). The wide loop samples only programs whose construction is at
hand, as in v9.

## Settings (`helix10.run.Config`, on top of v9's)

`mode` ("axes" or "warm"), `max_n` (2,000,000), `budget` (150 CPU s), `mem_mb` (2000), `min_explore` (2),
`borrow_share` (0.5), `race_rungs` (3, 6, 12, 24, 48), `record_hill_wide` (1), `upkeep_every` (3), `max_axes` (30),
`map_axes` (12), `tidy_values` (12), `big_n` (300,000), `keep_top` (12), `gc_age` (2).

## What it can and can't show

- **v10-axes** answers the research question cleanly: same machinery, same history, plus concepts. If it climbs past
  0.94144 towards the field's 0.96, the concepts did it (the field's polish alone moves our record by 7e-9: measured).
- **v10-warm** starts at the record. Polishing it on this CPU is exhausted at +3.8e-8 (measured); the arena needs
  +1e-5. So a record from v10-warm has to come from a structural change the field hasn't found, built and polished
  within 150 CPU seconds per program at 2M. That is the honest difficulty; docs/V10_JOB.md gives the odds.
