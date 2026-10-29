# The Helix v10, v10.1 and v10.2 jobs (October 28-29, 2026)

## v10.2 (October 29, 01:56-02:14): from Code Zero, the field's ideas as axes, against the published systems

Design, the published baselines and the odds: `docs/V102_DESIGN.md`. In short:
- two seeds of Helix from Code Zero, with the field's 9 decisions and 38 options on the design map and its findings in
  the Atlas;
- every new exploration is built from nothing on its own track and judged on its own climb;
- the constraint is the published systems' or tighter: at most 50,000 steps, 150 s per program, 400
  generations, 2,400 programs (theirs: 25,600 to 51,200);
- the report is results/v102/COMPARISON.md: the programs Helix needed to pass each published value (AlphaEvolve
  0.8962, best-of-25,600 0.9344, ThetaEvolve 0.9434/0.9469, OpenEvolve 0.9449, TTT-Discover 0.9591, AlphaEvolve V2
  0.9610).

### The prompt for Aether (v10.2)

> In /home/ubuntu/helix_v5_run, run `git pull`. Then start the two Helix v10.2 jobs, each once. By Shreyas's order
> (October 29), they replace the v10.1 jobs: seed 1 pauses v101-axes and v101-field, seed 2 pauses v101-warm (one stop
> signal each; each finishes its generation and pushes, which can take up to about 40 minutes), then each starts a new
> run from Code Zero. Don't stop anything yourself.
> `ARM=helix SEED=1 setsid nohup bash scripts/run_v102.sh > v102_s1.log 2>&1 < /dev/null &`
> `ARM=helix SEED=2 setsid nohup bash scripts/run_v102.sh > v102_s2.log 2>&1 < /dev/null &`
> One hour later, report the last 25 lines of v102_s1.log and v102_s2.log, and the output of `df -h .` and `free -m`.
> Don't stop, restart or kill anything, don't change any file, and don't set up any cron job, timer, monitor or
> check-in: Shreyas checks in himself.

What it should report, in each log:
- "pausing v101-..." (or "isn't running"), then "v101-... has stopped after N min";
- the preflight ("crash test passed", "model answers", "GitHub: can push");
- "v102-helix...: running", then progress lines ("g1 0.8...").

Restarting either is the same command; each resumes. The optional reference stream:
`ARM=field setsid nohup bash scripts/run_v102.sh > v102_field.log 2>&1 < /dev/null &`.

### Tested (October 29, in the cloud session)

| Step | Result |
| --- | --- |
| Crash tests | both seeds through the whole job with a fake model (pause, preflight, run, report, publish, verification); resume after a stop; tests/test_helix10.py, 18 passing, 4 of them new for v10.2 |
| The pause | a stand-in v10.1 job holding the lock got one stop signal and the v10.2 job waited for its lock |
| Live, real model | seed 1: 5 generations (3 alone at 40 s per program, then 2 more through the job script, resumed); seed 2 alongside: 2 generations (60 s per program); about 4.5 minutes a generation at 60 s |
| What happened | seed 1 went from 0.667 to 0.8631 in 5 generations. The record changed track 4 times, and each time a new exploration took it: three designs built from nothing around field options, then a flip on its own line. Coarse-to-fine came first (0.832), then a later option the planner chose (0.847), then [small, big, small] triplets (0.848, best 0.860). Seed 2 was at 0.820 after 2 generations. The planner turned each field option into a whole program (multigrid Dinkelbach, Gaussian-bump combs), and the step limit read 50,000 everywhere |
| Found and fixed | (1) The audit ran at generation 3 of a cold run and put trivial invariants (fixed random seeds) ahead of the field's options. It now first runs at generation 10, and the field's options are built before the audit's. (2) The reader named a build's target option in its own words, so a new option was created and the build was told it had missed its target. Such a reading is now merged into the target. |
| Not ours | tests/test_helix47.py has one test that fails the same way without these changes (a text check in the v4.7 map view) |

---

## v10.1 (October 28, 20:42): Helix against the world's best program, at the same constraint

**Why.** At 2,000,000 steps our CPU can't optimise a new idea far enough to show its height, so v10 could only lose
to a record polished for weeks on GPUs (measured: the field's own polish adds +3.8e-8 to it here, then stops). The
fair test of Helix's claim (it searches the field's ideas as axes and finds what the field's own approach doesn't) is
at a size where our compute matches the field's, against the field's program given exactly our constraint.

**The constraint, for everyone:** constructions of at most **100,000 steps** (zero ends don't count), **300 CPU
seconds per program**, the same total CPU, the same start. The best known construction in that class is
**0.962273842955** (JSAgent's public seed); the arena's best entry in it is 0.962214.

| Job | What it is | Starts from |
| --- | --- | --- |
| **v101-axes** | v10-axes continued (paused first, gracefully) in the size class: the field's ideas as axes only | our record, 0.9414417 (92,514 steps once its zero ends are trimmed) |
| **v101-warm** | v10-warm continued (paused first) in the size class: the field's constructions and methods plus the axes | the class's best, JSAgent's 0.962273842955, polished once by the field's methods |
| **v101-field** | the bar: the world's best program (ClaudeExplorer's iterated Dinkelbach alternating with the velocity cycles behind the July record), chained, under the same constraint, in three streams: from v101-axes's start, from v101-warm's start, and from nothing | the same starts; matched to its run in CPU seconds; a stream that goes 10 rounds without a gain has converged and stops |

**Also new:** the invariant audit ("what does every program do the same way?", docs/IDEAS.md 3.4), every 10
generations in both runs (`helix10/audit.py`): a describer names what the strongest, most different programs all do
the same way and sorts it (a constraint of the problem, a detail below design, or a design decision); a second
reading on a different sample confirms it (at least 75% share it); each confirmed decision goes on the map with its
alternatives, which are built and raced like the field's options; after two empty rounds it rests until the record
moves.

**What would prove the claim** (`results/v101/COMPARISON.md` is written at every push):

| Result | What it shows |
| --- | --- |
| v101-warm ends above v101-field's warm stream (same start, same CPU) | Searching the field's ideas beats the field's own best program at equal resources |
| v101-warm ends above 0.962273842955 | A new best known construction with n <= 100,000 (and above the arena's 0.962214 in that class) |
| v101-axes ends above v101-field's axes stream by more than 1e-6 | From our own lineage, the ideas as axes do what the field's program can't (it adds 7e-9 and stops) |
| A gain traced on the map to a borrowed option or an audited invariant | The gain came from the axes, not from luck in polishing |

My expectation, honestly: the field's program converges within a few rounds from both starts, so the bar is low in
compute but high in quality (both starts are polished vertices). A clear gain for v101-axes is about even odds; a
gain for v101-warm above the field's program, about one in three; by more than 1e-6, about one in ten.

### The prompt for Aether (v10.1)

> In /home/ubuntu/helix_v5_run, run `git pull`. Then start the three Helix v10.1 jobs, each once. By Shreyas's order,
> the first two pause the running v10 job of the same mode themselves (one stop signal; it finishes its generation
> and pushes, which can take up to about 40 minutes) and then continue where it left off; don't stop anything
> yourself.
> `MODE=axes setsid nohup bash scripts/run_v101.sh > v101_axes.log 2>&1 < /dev/null &`
> `MODE=warm setsid nohup bash scripts/run_v101.sh > v101_warm.log 2>&1 < /dev/null &`
> `MODE=field setsid nohup bash scripts/run_v101.sh > v101_field.log 2>&1 < /dev/null &`
> One hour later, report the last 25 lines of v101_axes.log, v101_warm.log and v101_field.log, and the output of
> `df -h .` and `free -m`. Don't stop, restart or kill anything, don't change any file, and don't set up any cron
> job, timer, monitor or check-in: Shreyas checks in himself.

What it should report: in v101_axes.log and v101_warm.log, "pausing v10-axes" (or "isn't running"), then "v10-...
has stopped after N min", the preflight, the warm start ("size class n <= 100,000", the record in the class), and a
first generation; in v101_field.log, the streams starting once the runs exist. Restarting any of them is the same
command; each resumes.

### Tested live (October 28, 21:00-21:35, real model, as the VM will run it; 120 s per program to keep it short)

| Step | Result |
| --- | --- |
| The pause | a live v10-axes job mid-generation got one stop signal from v101-axes; it finished its generation, published, packed and exited after 8 minutes; v101-axes waited for its lock and continued from its generation 801 |
| Warm starts | axes: the class's record is ours (0.941441744, 92,514 steps once trimmed); warm: JSAgent's seed imported, the field's methods on it (+2.4e-11), main track reset to it; the 2M imports stay known but out of the class |
| A generation each | 8 min (axes) and 7 min (warm) with the bar running alongside; the planner built borrowed flips (Adam with elitist respawn, a piecewise-constant autoconvolution, zero-padding to the step limit) |
| The bar | the field's program from the same starts: +7.4e-9 on ours, +3e-11 on the seed and flat after 4 rounds; from nothing, 0.849 after 2 rounds |
| The comparison | `COMPARISON.md` written by every push of every job |
| The invariant audit | first version: the real model called the scorer's formula and the timing code "decisions", and they were confirmed. Fixed: both readings get the full problem statement and must each sort an item as a design decision, and one the map already has is dropped. Rerun live: the scorer and the convolution routine were sorted out; kept were real choices (no auxiliary variable for the max; a single trajectory, not a population; no imposed structure; the best exact iterate is returned) |
| Also found and fixed | the bar read a run's state mid-warm-start (now waits for the finished v10.1 start); another run's folder reused program ids (extents now verified by length and score; a job reads only its own mode's v10 folder); the comparison looked for the bar in the wrong folder |

---

## v10 (the first two runs, at 2,000,000 steps; paused by v10.1)

Two runs side by side on the VM, continuing v9-s1 (generation 800, record 0.9414417) with the field's knowledge
(docs/V10_DESIGN.md, docs/AC2_SOTA.md). Script: `scripts/run_v10.sh` (its header has every setting).

| Run | MODE | Starts from | Gets from the field |
| --- | --- | --- | --- |
| v10-axes | axes | v9-s1's record, 0.9414417 | 9 decisions and 38 options on the design map, 14 findings in the Atlas |
| v10-warm | warm | the arena record, 0.963588110582 (n = 1,999,999) | the same, plus 14 constructions (verified) and 3 of the field's methods as programs |

Defaults: 150 CPU seconds per program, steps up to 2,000,000, 120 generations each (deadline 60 hours), the two
runs sharing the machine's 2 evaluation slots. Results go to `results/v10/v10-axes` and `results/v10/v10-warm`, the
report to `results/v10/REPORT.md`, each run's constructions at the end to a GitHub release built on v9-s1's.

The first job to reach it also finishes v9's pending upload: the 298 constructions of v9-s1 that GitHub lacks go up
as the release `constructions-v9-s1`, built on `constructions-v8-s1` and `constructions-v9-s1-g800` (a lock makes the
other job wait for it).

## The prompt for Aether

> In /home/ubuntu/helix_v5_run, run `git pull`. Then start the two Helix v10 jobs, each once:
> `MODE=warm setsid nohup bash scripts/run_v10.sh > v10_warm.log 2>&1 < /dev/null &`
> then, 30 seconds later,
> `MODE=axes setsid nohup bash scripts/run_v10.sh > v10_axes.log 2>&1 < /dev/null &`
> Fifteen minutes after the second start, report the last 20 lines of v10_warm.log and of v10_axes.log, and the
> output of `df -h .` and `free -m`. Don't stop, restart or kill anything (an earlier run included), don't change any
> file, and don't set up any cron job, timer, monitor or check-in: Shreyas checks in himself.

What it should report: each log's preflight ("crash test passed", "model answers: OK", "GitHub: can push"), the
vault line, the warm start (v10-warm: 14 constructions imported, then the three field methods, about 8 minutes),
"running", and within 30 minutes each run's first generation line. A preflight failure exits with a line starting
`preflight:` and starts nothing.

Starting again after any stop is the same command (a running job refuses a second copy of itself); each resumes from
its last finished generation. To stop one: `kill -TERM <its bash script's pid>` (it finishes the generation in
progress, up to 20 minutes, and pushes) - only on Shreyas's order.

## Tested live (October 28, in the cloud session, with the real model)

Both jobs, end to end, side by side, exactly as the VM will run them (`scripts/run_v10.sh`, 150 s per program, two
generations each; PUSH=0 and a test folder, so nothing went to GitHub), from GitHub's v9-s1 alone:

| Stage | Result |
| --- | --- |
| Preflight | crash test (2 generations, fake model, report, publish, pack), a real model call: passed in both |
| Constructions of v9-s1 | no local folder here, so restored from the releases: 3,235 + 1,055 (the VM uses its own folders and uploads the 298 GitHub lacks) |
| The field's constructions | 14 of 14 from data/field_ac2, each checked by SHA-256 and re-scored |
| Warm start, axes | 9 decisions (5 on the map's own), 38 new options, 14 findings; 18 s |
| Warm start, warm | the same, 14 imports on their own tracks; the field's methods on the record: Dinkelbach polish +3.25e-8, velocity cycles +0 (on one core its cycles can't recover their own noise), the transfer on Hyra's (repeat 3x, pad to 2M) +7.3e-8 |
| Generations | 11 min a generation with both running, 6.5-7 min alone |
| What the planner did with the field | first generation of v10-axes, its own words: "The one lever this run has never pulled is the field's method behind every construction above 0.962 ... all three slots bet on that cascade". Borrowed flips each generation (Anderson-accelerated L-BFGS, irregular blocks, simulated annealing, the exact max); read-back landed 1/1 on two of them |
| v9's failures | the three racing copies of the record (T278, T279, T282, 13-26 experiments on H22) stopped racing at once |
| 2M programs | the record polished by the coder's own program (+2.8e-9); a simulated-annealing flip at 2M ran (-8.6e-6, then +1.1e-8); one program killed at its CPU or memory limit (handled) |
| Stop and resume | a stop signal two minutes into a warm generation: it finished the generation (9 minutes), published, verified, packed and exited; started again, it pushed, resumed at 802 and finished |
| End | publish (borrowed.json included), report, verification (helix, DeepMind's code, the arena's code agree: v10-warm 0.963588145916, +3.5e-8 over the record), continuation packs |
| Disk | 430 MB of constructions for the warm run after 2 generations (14 imports included), 285 MB for the axes run |

Fixed because of the test: the verification refused 2M constructions (it now uses the run's limit, the arena's own
verifier, and FFT convolution in DeepMind's code above 200k); a v10 continuation added the field's findings twice;
the wide loop's replacement bases (off the record's hill) were sampled too flatly, missing the imports.

## How likely is a record

The target: **0.963598110582** (the arena's #1, 0.963588110582, plus its gate of 1e-5), at n <= 2,000,000.

| Outcome | v10-warm | v10-axes |
| --- | --- | --- |
| A value above 0.963588110582 at all | certain: done already (the field's polish adds +3.3e-8 at the warm start). Not a discovery, and the arena would refuse it | under 1% |
| The arena's record (0.963598 or more) within the run (about 2 days on the VM) | about 3% | under 0.5% |
| A clear gain on its own start (more than 1e-6 relative) | about 10% | about 50% |
| Past 0.95 | (starts above) | about 15% |

Why, from measurements, not hopes:
- **Polishing won't do it here.** The field's own polish, rewritten for one CPU core, gains +3.78e-8 on the record
  and then nothing (+3.4e-8, +3.3e-9, +4.2e-10, +3.9e-11, then about 1.4e-11 a round; +3.79e-8 after eight
  133 s rounds). The arena needs 260 times that.
  The record's basin was still giving about 2e-5 a day in July, on GPUs, with thousands of L-BFGS iterations per
  cycle; a 150 s program at 2M gets about 150-250 evaluations here.
- **So v10-warm needs a structural idea the field doesn't have**, built and polished inside 150 CPU seconds per
  program at 2M. Hyra's lattice was that kind of idea (+2.6e-4 over the older family at equal n); it took the field
  three months and many agents to find once, and GPUs to convert (+6.9e-4 of polish at the cap).
- **v10-axes is the cleaner test of the research question.** Borrowing the field's polish moves our record by 7e-9
  (measured), so any real climb in v10-axes comes from the concepts reaching the design, not from a better polisher.

What would change the odds: GPU time for the polishing stage (the field's route; it would make a +1e-5 polish of the
record plausible in a few GPU-days, but it would prove compute, not the point), a longer budget per program at 2M
(`BUDGET`), or searching structure at Hyra's scale (n about 500k, 4 times cheaper per evaluation) and moving it to
2M with the exact repeat.
