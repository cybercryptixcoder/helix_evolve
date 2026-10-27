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

## Keeping the map tidy (`upkeep.py`): found by testing live

The first replay with the real model (DeepSeek V4.1 Flash) on v8's archive showed what fake models never could: the
model names the same decision and the same option in new words almost every time, and word matching can't tell
paraphrases apart. 386 readings grew the codebook to **874 decisions**, one with **296 options**; the annotator saw
only the first 8 options of each, so it named new ones, and two readings of a program picked different paraphrases:
only 2 of 9 decisions were read with 80% agreement. Now:

- **the annotator is told** to use a listed option whenever one fits, to name a new one only if it is clearly
  different (at most 8 words), and a new decision only if a major one is missing (at most one per reading);
- **consolidate:** decisions that are the same in other words are merged (as before, now also between waves);
- **tidy:** a decision with more than 6 options has them grouped by the model into at most 6 distinct choices with
  short names; the most used option of each group survives, the others become its aliases, so every earlier reading
  still resolves; agreement is measured on resolved options;
- **prune:** a decision found by reading programs that, 10 generations on, fewer than 3 programs make is dropped;
- **importance** is weighted by how many programs make each choice (a decision read on two programs explains little
  of the whole, however far apart they scored).

The replay reads in waves of 48 programs with upkeep between them; the run does upkeep at the start of every
generation (at most 3 decisions tidied per generation).

## Live tests (October 27, with the real model)

| Test | Result |
|---|---|
| The replay on v8-s1 (458 programs read, 119 twice, 120 later changes read from their diffs) | **12 of 13 decisions read with at least 80% agreement** (kappa 0.23-1.00). The model, fitted up to generation 562, ranks the 120 later changes better than chance but weakly: rank correlation **+0.16 (p = 0.04)**; a second full replay gave +0.06 (p = 0.28). It does not rank the later programs' scores (+0.06; their parents' scores alone: +0.996). `results/v9warm/replay/REPLAY.md` |
| The job, end to end, on GitHub's v8-s1 (5 generations, 60 s per program, then stopped mid-generation and resumed) | Every stage ran: preflight with a real call, warm start with the replay's map and the queue (2 racing, 81 waiting), annotations (0 unreadable), upkeep, an ablation built from its blueprint and read back (landed 1/1, then its follow-up drifted: 0/1, named to the coder), a discovery (a new decision), the race pausing it, the report, publishing, the pack. A stop signal mid-generation finished the generation and pushed; the restart resumed at 705. 160-510 s a generation; about 20 calls, 155k tokens in and 40k out a generation |
| The planted problem with the real model (12 generations, cold) | The real coder built what blueprints asked: 8 of 9 target decisions in 4 read-backs. The run reached the planted world's **taller hill** (true height 0.9395 of a best possible 0.962, from 0.737). The check for reworded duplicates at generation 10 merged 11 decisions into 8; the first ablation came at generation 12. The real annotator maps the program's mechanics rather than the declared `DESIGN`, so this tests the machinery live, not the map's match to the planted truth |
| A cold run from Code Zero (8 generations, 30 s per program) | 0.6667 -> 0.8953; the map grew from the 8 generic questions to 14 decisions of at most 6 options each; a drop landed 2 of its 3 target decisions, flips 1 of 1; 139 calls, 776k tokens in, 224k out |

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
- The model is data-limited near the record. In the simulator, targets chosen at random on the map did as well as
  the model's (`docs/V9_SIM.md`, section 4): v9's measured gain comes from where it jumps (drops and flips from the
  record, away from known hills) and from keeping breadth, not from the model's choice. On the real archive the
  model's knowledge is weak (rank correlation +0.06 to +0.16 on later changes): Thompson sampling with a model that
  knows little behaves much like choosing untried targets at random, which the simulator says is what works.
- A construction rebuilt without its original start is approximate; the job avoids this on the VM by using the local
  folder.
- One run is one sample: section 2.2 of the search-space model shows single runs are noisy. The live job tests
  behaviour (do drops land, does the race promote, does the queue revive the right explorations) more than it ranks
  versions.
