# The Helix v10 jobs (October 28, 2026)

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
