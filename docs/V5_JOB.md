# The Helix v4.5 + v5 overnight job

What it runs: the second autocorrelation inequality; v5 (the researcher) and v4.5 (Atlas+) × three seeds = 6 runs,
20 generations each, side by side, 30 s of CPU per program. The 9 runs of the v4 job are the baselines. Design:
`docs/V5_DESIGN.md`.

## Running it

```bash
cd helix_evolve && git pull
# .env in the repo root, one line (never committed): LUMINAL_API_KEYS=key1,key2,key3,key4
pip install -r helix5/requirements.txt
nohup bash scripts/run_v5_jobs.sh > v5_jobs.log 2>&1 &
```

- **If the v4 job is still running** on the machine, this job waits for it to end before starting (it checks every
  minute and prints a line every 30 minutes; after 4 hours it starts anyway). The two never compete for the CPU.
- **Verification first**: it re-scores every v4 best construction three ways (`tools/verify_ac2.py`) and pushes
  `results/v4/VERIFICATION.md`. At the end it does the same for v4.5 and v5 (`results/v5/VERIFICATION.md`).
- **Preflight** (about a minute): numpy and scipy present; a crash test of v4.5 and v5 with a fake model; one real
  model call.
- **Load**: six Python processes of about 40 MB each; programs evaluated at most two at a time machine-wide, at low
  priority, only with 600 MB free.
- **Time**: about 4 to 5 hours once it starts (estimated from the v4 job's pace with nine runs and from test runs:
  v5's planner thinks longer than v4's). A deadline (6 hours after the first start, kept across restarts) stops every
  run after its current generation.
- **Resuming**: if the machine restarts or the script dies, run the same command again; finished runs are skipped,
  unfinished ones resume from their last completed generation.
- **Results**: each finished run is copied to `results/v5/<run>/` and pushed; progress and `results/v5/report.html`
  (v4, v4.5 and v5 on one page) are pushed every 40 minutes; a status line goes to the log every 10 minutes.
- **If pushing fails**: `tar czf helix_v5_results.tgz results/v5 results/v4 runs/v5 v5_jobs.log`.
- **To start over from nothing**: `rm -rf runs/v5` (also clears the deadline).

Knobs: `GENS` (20), `SEEDS` ("1 2 3"), `CONDITIONS` ("v5 v45"), `BUDGET` (30), `HOURS` (6), `EVAL_SLOTS` (2), `PUSH`
(1), `FAKE` (1 = no model calls, a test), `TICK` (600), `MAX_WAIT_MIN` (240).

## The prompt for the Hermes agent

> Run my Helix v4.5 + v5 job unattended. Don't change any code; just run the setup and report back.
>
> 1. cd helix_evolve && git pull (or clone https://github.com/cybercryptixcoder/helix_evolve first).
>    You need push access to this repo: results are pushed to it. Pull only before starting, not while it runs.
>    It's fine if the previous Helix v4 job is still running: this one waits for it to finish by itself.
> 2. Make sure the repo root has a file named .env containing exactly this one line:
>    LUMINAL_API_KEYS=<the four keys, comma-separated>
>    Never commit this file (it is gitignored).
> 3. pip install -r helix5/requirements.txt
> 4. Start the job in the background, with the default settings:
>    nohup bash scripts/run_v5_jobs.sh > v5_jobs.log 2>&1 &
>    If the v4 job is still running, the log will say "(waiting for the v4 job to finish before starting ...)": that
>    is normal. Then it runs a ~1-minute preflight and stops with a clear error if anything is wrong. If it stops for
>    that reason, tell me the error and do nothing else. Don't change GENS, SEEDS, EVAL_SLOTS or any other setting:
>    other agents share this machine, and the job is sized for it.
> 5. If the machine restarts or the script dies for any other reason, run the same command again. Finished runs are
>    skipped and unfinished ones resume. Repeat until v5_jobs.log ends with "== all jobs done". Expect about 4 to 5
>    hours after it starts (plus any wait for the v4 job); it stops itself 6 hours after starting at the latest.
>    Lines like "(waiting: ... MB available)" are normal: it is waiting for free memory.
> 6. The job pushes its results to GitHub by itself (results/v5/ and results/v4/VERIFICATION.md), every 40 minutes
>    and at the end. If pushing fails, don't debug it: at the end run
>    tar czf helix_v5_results.tgz results/v5 results/v4 runs/v5 v5_jobs.log and send me that file.
> 7. When done, send me the last 30 lines of v5_jobs.log.
>
> Note: I need you to conserve your context. Do not read any of the code, the traces or the run folders. Just run
> this job, check that it is running, and report back. Check in with short cron wake-ups: the first one 10 minutes
> after starting (look at the last 15 lines of v5_jobs.log: you should see either the waiting line, or
> "== ...: starting" lines and no error), the second one 30 minutes after starting, then every 1 to 2 hours until it
> is done. Each time, read only the last 15 lines of v5_jobs.log and the output of: ls results/v5. Don't wake up
> every few minutes.
