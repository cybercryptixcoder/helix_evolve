# Helix v9: v8 plus a design map (October 27, 2026)

Code: `helix9/`. Tests: `tests/test_helix9_map.py`, `tests/test_helix9_run.py`. The job: `docs/V9_JOB.md`. The
reasoning: `docs/SEARCH_SPACE_MODEL.md` (sections 4, 6 and 7). The request: `docs/BRIEF_2026-10-27.md`. The
simulator's results: `docs/V9_SIM.md`. The viewer: `viz/mapview.html`.

## What it is for

v8 keeps a register of hills by what programs produce, but its exploration is blind: restarts sample the coder's
habits (19 of 19 fell into the same well on the autocorrelation problem), flips pick a shared decision at random,
and a new hill is judged after two follow-ups although early height doesn't predict final height. The October 27
discussion asked for a map of the design space with literal coordinates, jumps to chosen points on it, axes
discovered while searching, and a proof of concept that can be trusted before scaling. v9 is that map, added to v8
without removing anything.

## What stays (v8, unchanged)

The roles, 3 planned experiments and 3 mutations a generation, the stall levels, the main track's guaranteed slot,
tracks never closed, alternatives, the noise floor, warm starts, the register of hills by output signature, the
Cartographer, the Atlas of findings. While the record climbs (level 0), a v9 generation is v8's plus a read-only table
and the reading of its programs.

## What v9 adds

| Part | File | What it does |
|---|---|---|
| Codebook | `codebook.py` | Design decisions (axes) and options (values) with **permanent ids** given at birth (A3, A3.v2), never renumbered (NEAT's historical markings). Names are matched before anything is added; merges become aliases; impossible pairs are recorded. Seeded with 8 generic questions with no options; everything else comes from the run's own programs |
| Annotator | `annotate.py` | One cheap call per new program: **from the diff** (the base's coordinate plus what changed; an error stays local) or **in full** (no base coordinate, a rewrite, a landing to check, or a 12% sample read twice). Agreement and Cohen's kappa per axis; an axis read with less than 50% agreement stops steering |
| Model | `model.py` | Bayesian one-hot regression: main effects, screened pairwise interactions, a saturating effort term, per-axis variances by empirical Bayes; **a decision nobody has varied stays uncertain** (the pooled prior), because the decisions every program shares are where the most is unknown. Thompson samples, importance per axis, residuals |
| Drops, flips, ablations | `drops.py` | Exploration **chosen from the map**: a drop changes 2-4 decisions at once and lands at least 2 decisions from every known hill's top; a flip changes one; every 12 generations an ablation undoes one of the record's decisions to measure what it is worth. Targets come from Thompson sampling, so untried options keep a chance. Tabu on tried targets, no known-impossible pairs |
| Blueprint and read-back | `prompts.py`, `run.py` | The planner gets the target and plans how to build it; the coder gets it as a blueprint (the target decisions; everything else as the base). The result is read in full: decisions not built are named to the next follow-up |
| The fair race | `race.py`, `run.py` | Replaces v8's two-follow-up patience for drops, flips, ablations and restarts: a new design is compared with designs that started the same way **at the same effort** (rungs of 2, 4, 8, 16, 32 experiments) and continues while it keeps rising. **Breadth is kept:** about half the exploration slots open new directions whatever races; at most 3 race at once, and when a fourth arrives the weakest at equal effort waits in the queue. Racing tracks that gained at their last experiment are served first, then in turn |
| The queue of earlier explorations | `race.py`, `warm.py` | A continuation judges the earlier run's explorations as the race would have. Those still rising when they were paused qualify; the 2 strongest race again at once, the rest **wait in a queue** (strongest at equal effort first) and are taken one at a time as a kind of new direction, about twice as often as each kind of new exploration |
| Discovery | `run.py` | Two programs at the same coordinate scoring further apart than the model explains prompt "what design decision differs?"; the answer becomes an axis. Cartographer scans are matched into the codebook instead of replacing it; above 16 axes a consolidation call merges duplicates |
| The planner's view | `run.py` | A table: each decision, its options, how many programs use each, their best, the estimated effect and its uncertainty, what is untried, and the model's suggested move for a track |
| Constructions on demand | `run.py` | A base without a construction is copied from a local folder if one verifies, else rebuilt by running its code from a close ancestor or the program whose output is most like its own (approximate, logged). The wide loop samples programs whose construction is at hand |

**Cost per generation:** v8's calls, plus about 7 short annotation calls (diffs), a full reading for each landing,
an occasional discovery or consolidation call, and a model fit in milliseconds.

**If the map can't steer** (fewer than 2 reliable axes), exploration falls back to v8's kinds.

## Continuing from GitHub

| Part | File | What it does |
|---|---|---|
| Continuation pack | `pack.py` | Built once where the constructions are: every construction **verified** (re-scored, the recorded score to 1e-12 and the recorded number of steps), signatures for all, the constructions that matter most packed losslessly up to 80 MB in files of at most 40 MB, with SHA-256s. A later pack names its base and holds only what is new |
| Warm start | `warm.py` | v8's warm start (everything kept; generations continue the numbering), plus the pack restored (checked), the replay's map, and the retroactive race. Reads a source as pushed to GitHub, plain, gzipped or in chunks |
| Replay | `replay.py` | Stage 0 of the proof of concept: a codebook from the earlier run's Cartographer scans, 150 programs read (a quarter twice), two verdicts in REPLAY.md (are decisions read reliably; does the model, fitted on earlier programs, rank later gains better than chance), and the map's seed |
| Publishing | `publish.py` | Every push sends the whole run: small files as they are, big growing files in fixed gzipped chunks (each push adds only what is new), and mapview.json |
| Robust run | `job.py` | Graceful stop (finish the generation, exit 75), torn-line repair, health waits for disk and model, the deadline |
| Report | `report.py` | v8's report plus the design map: decisions, reliability, importance, every chosen exploration with its target, what was built, its race and its landing, discoveries, rebuilt constructions |

## Seeing it: `viz/mapview.html`

One page for the simulator and for any Helix run (v4 to v9), finished or live. `helix9/mapview.py` writes its data
(`mapview.json`); the job pushes one with every push. The page shows:
- **the map**: every program placed by design (v9's coordinates), by what it produces (v8's signatures) or by
  generation and track (earlier versions), coloured by kind, with the record's path; behind it the landscape (the
  planted one in the simulator; estimated from the scores in a run) as contours, or as a terrain you can turn;
- a slider and play button to replay the run generation by generation;
- the record's climb, the race's curves (each exploration's best against the experiments spent on it), the design
  map's decisions and their importance, what happened in each generation, and a table of programs;
- **Live**: reloads the source every minute (a run's `mapview.json` on GitHub changes with each push).

Sources: the presets (simulator runs committed in `viz/data/`, the v8 run, the live v9 run), any URL (a GitHub raw
link works), or a file dropped on the page. Light and dark themes, phone width.

## The simulator: `helix9/sim.py` and `helix9/planted.py`

Stage 1 of the proof of concept: a planted world where the truth is known. Designs are coordinates on d axes (some
hidden at first); hills are planted cones with peaks, widths and maturation times (a trap where the coder's habits
are, the record's hill, a taller hill 3 coordinated changes away, decoys, ruggedness); a program's score is its
design's height minus a gap that closes with the effort spent there (a hill's height is not visible from its foot);
the coder samples its habits, builds what it is asked with some fidelity and drifts; the annotator reads with some
error. Policies: v8, v9, and v9 with each part off or changed, v8 with the race, and a simple baseline (sequential
conditioned sampling). Families of worlds from easy to nearly impossible, warm and cold.

`helix9/planted.py` puts the same world behind the **real** v9 run (a fake coder that obeys blueprints with some
fidelity, a fake annotator that reads the program's declared design), so drops, read-back, the codebook, the model
and the race are tested end to end on data where the truth is known.

What it found, and what was changed because of it, is in `docs/V9_SIM.md`.

## Settings (`helix9.run.Config`, on top of v8's)

`annotate` (True), `double_rate` (0.12), `reliable_min` (0.5), `model_min_rows` (12), `model_pairs` (6), `kmin`/`kmax`
(2/4), `drop_min_dist` (2), `race_rule` ("rising"), `race_rungs` (2, 4, 8, 16, 32), `running_cap` (3),
`breadth` ("half"), `race_serve` ("gain"), `ablate_every` (12), `discover_every` (4), `residual_z` (2.5), `map_axes`/`map_values` (10/6, the table's size),
`suggest_moves` (True), `seed_axes` (True), `max_axes` (16).

## Known limits

- The map is only as good as the readings. The replay measures this before the run relies on it, and an axis read
  unreliably stops steering.
- The model is data-limited near the record (it ranks designs there weakly in the simulator); its value is as an
  accountant of what is untried and uncertain, which is what Thompson sampling needs.
- A construction rebuilt without its original start is approximate; the job avoids this on the VM by using the local
  folder.
- One run is one sample: section 2.2 of the search-space model shows single runs are noisy. The live job tests
  behaviour (do drops land, does the race promote, does the queue revive the right explorations) more than it ranks
  versions.
