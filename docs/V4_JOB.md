# The Helix v4 overnight job

What it runs: one problem (the second autocorrelation inequality), three memory conditions (Atlas, Journal,
Control) × three seeds = 9 runs, 20 generations each, all side by side. Design and rationale: `docs/V4_DESIGN.md`.

## Running it

```bash
cd helix_evolve && git pull
# .env in the repo root, one line (never committed): LUMINAL_API_KEYS=key1,key2,key3,key4
pip install -r helix4/requirements.txt
nohup bash scripts/run_v4_jobs.sh > v4_jobs.log 2>&1 &
```

- **Preflight** (about a minute): numpy and scipy present; a crash test of each condition with a fake model; one
  real model call. It stops with a clear error if anything is wrong.
- **Load on the machine.** Nine Python processes of about 40 MB each, which mostly wait on the model. Programs are
  evaluated at most two at a time across the whole job (`EVAL_SLOTS=2`, one per core), at low priority (nice 10,
  idle IO class). A program only starts when at least 600 MB of memory is free, and a run only starts with 1,200 MB.
  Peak memory is under 1 GB.
- **Time.** See "Timing" below. A deadline (default 7.5 hours after the first start, kept across restarts) stops
  every run after its current generation, so results exist by morning however slow the machine is.
- **Resuming.** If the machine restarts or the script dies, run the same command again: finished runs are skipped
  and unfinished ones resume from their last completed generation.
- **Results.** Each finished run copies itself to `results/v4/<run>/` and pushes (commits as Shreyas Naik).
  Every 40 minutes the job also pushes progress and a fresh `results/v4/report.html`, so a partial result is on
  GitHub even if the job dies. At the end it pushes the final report and prints each run's best score.
- **If pushing fails**: `tar czf helix_v4_results.tgz results/v4 runs/v4 v4_jobs.log`.
- **To start over from nothing**: `rm -rf runs/v4` (also clears the deadline).

Knobs (environment variables): `GENS` (20), `SEEDS` ("1 2 3"), `CONDITIONS` ("atlas journal control"), `BUDGET`
(30 s of CPU per program), `HOURS` (7.5), `EVAL_SLOTS` (2), `PUSH` (1), `FAKE` (1 = no model calls, a test), `TICK`
(600: seconds between status lines; progress is pushed every fourth).

## Timing

Measured on October 20 on a 2-core cloud container (the same core count as the OCI VM), with the full job
configuration in miniature (9 runs side by side, 3 generations, 20 s per program):

- Programs used most of their budget (median 18 s of CPU, mean 15 s; 78% used at least 15 s).
- A generation took 3.5 to 8.5 minutes per run (about 6.5 typical); Atlas runs are the slowest (two extra model
  calls and a larger prompt). Model calls are not the bottleneck: Coders and Mutators answer in 3 to 5 s, the
  Researcher in 20 to 200 s, and nine runs stay well inside Luminal's limits.
- Memory: about 40 MB per run process, under 600 MB for the whole job.

The overnight job gives each program 30 s instead of 20, so a generation should take about 9 to 11 minutes and
20 generations **about 3.5 to 4.5 hours** (allow up to 5 on the VM). The 7.5-hour deadline is a backstop.

## The prompt for the Hermes agent

> Run my Helix v4 job unattended. Don't change any code; just run the setup and report back.
>
> 1. cd helix_evolve && git pull (or clone https://github.com/cybercryptixcoder/helix_evolve first).
>    You need push access to this repo: results are pushed to it. Pull only before starting, not while it runs.
> 2. Make sure the repo root has a file named .env containing exactly this one line:
>    LUMINAL_API_KEYS=<the four keys, comma-separated>
>    Never commit this file (it is gitignored).
> 3. pip install -r helix4/requirements.txt
> 4. Start the job in the background, with the default settings:
>    nohup bash scripts/run_v4_jobs.sh > v4_jobs.log 2>&1 &
>    It first runs a ~1-minute preflight and stops with a clear error if anything is wrong. If it stops for that
>    reason, tell me the error and do nothing else. Don't change GENS, SEEDS, EVAL_SLOTS or any other setting:
>    other agents share this machine, and the job is sized for it.
> 5. If the machine restarts or the script dies for any other reason, run the same command again. Finished runs are
>    skipped and unfinished ones resume. Repeat until v4_jobs.log ends with "== all jobs done". Expect about
>    4 to 5 hours; it stops itself at 7.5 hours at the latest. Lines like "(waiting: ... MB available)" are normal:
>    it is waiting for free memory.
> 6. The job pushes its results to GitHub by itself (results/v4/), every 40 minutes and at the end. If pushing fails,
>    don't debug it: at the end run tar czf helix_v4_results.tgz results/v4 runs/v4 v4_jobs.log and send me that file.
> 7. When done, send me the last 30 lines of v4_jobs.log.
>
> Note: I need you to conserve your context. Do not read any of the code, the traces or the run folders. Just run
> this job, check that it is running, and report back. Check in with short cron wake-ups: the first one 10 minutes
> after starting (look at the last 15 lines of v4_jobs.log: you should see "== ...: starting" lines and no error),
> the second one 30 minutes after starting, then every 1 to 2 hours until it is done. Each time, read only the last
> 15 lines of v4_jobs.log and the output of: ls results/v4. Don't wake up every few minutes.
