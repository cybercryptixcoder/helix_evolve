# The Helix v4.6 + v6 overnight job

**What it runs:**
- the problem: the second autocorrelation inequality;
- the versions: v6 (the agent) and v4.6 (Atlas around ideas, with the mutation halo);
- the size: 3 seeds each, so 6 runs, 30 generations each, side by side;
- the compute: 30 s of CPU per program, the same per generation as v4, v4.5 and v5.

The baselines are v4, v4.5 and v5 (`docs/V4_ANALYSIS.md`, `docs/V5_RESULTS.md`). The design is in
`docs/V6_DESIGN.md`.

## Running it

```bash
cd helix_evolve && git pull
# .env in the repo root, one line (never committed): LUMINAL_API_KEYS=key1,key2,key3,key4
pip install -r helix5/requirements.txt
nohup bash scripts/run_v6_jobs.sh > v6_jobs.log 2>&1 &
```

- **One copy at a time.** A second start while the job is running exits at once and changes nothing. The log says
  "this job is already running".
- **It never stops anything.** If an earlier Helix job (v4 or v5) is still running, this one waits for it:
  - it checks every minute and prints a line every 30 minutes;
  - after 4 hours it starts anyway.
- **Preflight** (about a minute):
  - numpy and scipy are present;
  - a crash test of v4.6 and v6 with a fake model;
  - one real model call.
- **Load:** six Python processes of about 40 MB each. Programs are evaluated at most two at a time machine-wide, at
  low priority, and only with 1,200 MB free.
- **Time:** about 5 to 5.5 hours. The v5 job's 20 generations took 2.6 to 3.3 hours, almost exactly its evaluation
  time on 2 slots; 30 generations is 1.5 times that. A deadline, 8 hours after the first start and kept across
  restarts, stops every run after its current generation.
- **Resuming:** if the machine restarts or the job dies, run the same command again. Finished runs are skipped, and
  unfinished ones resume from their last completed generation.
- **Results:**
  - each finished run is copied to `results/v6/<run>/` and pushed;
  - progress and `results/v6/report.html` (every version on one page) are pushed every 40 minutes;
  - a status line goes to the log every 10 minutes;
  - at the end, `results/v6/VERIFICATION.md` re-scores every best construction three ways.
- **If pushing fails:** `tar czf helix_v6_results.tgz results/v6 runs/v6 v6_jobs.log`.
- **To start over from nothing:** `rm -rf runs/v6`. This also clears the deadline.

**Knobs** (leave them at their defaults on the shared VM):

| Knob | Default |
|---|---|
| `GENS` | 30 |
| `SEEDS` | "1 2 3" |
| `CONDITIONS` | "v6 v46" |
| `BUDGET` | 30 |
| `HOURS` | 8 |
| `EVAL_SLOTS` | 2 |
| `MIN_FREE_MB` | 1200 |
| `PUSH` | 1 |
| `FAKE` | 1 = no model calls, a test |
| `TICK` | 600 |
| `MAX_WAIT_MIN` | 240 |

## The prompt for the Hermes agent

It starts the job, checks the start once and reports. It contains no instruction to stop, kill or restart
anything, and none to schedule wake-ups, crons or check-ins. Shreyas checks in himself (standing rule,
`docs/REQUESTS.md`).

> Start my Helix v4.6 + v6 job on this machine and report back. Don't change any code or settings; just start it.
>
> 1. cd helix_evolve && git pull (or clone https://github.com/cybercryptixcoder/helix_evolve first). You need push
>    access to this repo: the job pushes its results to it.
> 2. Make sure the repo root has a file named .env containing exactly this one line:
>    LUMINAL_API_KEYS=<the four keys, comma-separated>
>    Never commit this file (it is gitignored).
> 3. pip install -r helix5/requirements.txt
> 4. Start the job in the background, exactly like this:
>    nohup bash scripts/run_v6_jobs.sh > v6_jobs.log 2>&1 &
>    Don't change GENS, SEEDS, EVAL_SLOTS or any other setting: other agents share this machine, and the job is
>    sized for it.
> 5. Wait about two minutes, then read the last 20 lines of v6_jobs.log, once.
>    - If you see "== v6-s1: starting" (or "resuming") lines and no error, it is running.
>    - If you see "(waiting for the other Helix job to finish ...)", that is also fine: it starts by itself later.
>    - If it stopped with a "preflight:" error, or says "this job is already running", don't try to fix anything.
>
>    In every case, tell me what the last 20 lines say, and stop there.
>
> Rules:
> - Never stop, kill or restart this job or any other process, and never start a second copy.
> - Don't schedule any wake-ups, cron jobs, reminders or check-ins for yourself. I will check on it myself.
> - The job pushes its own results to GitHub. Don't commit or push anything yourself.
> - Conserve your context: don't read the code, the traces or the run folders.

## When Shreyas checks in

The useful lines are at the end of `v6_jobs.log`:
- `== HH:MM progress: v46-s1 g12 0.93… | …`, every 10 minutes;
- `== <run>: finished`;
- `== all jobs done`.

The job pushes everything by itself, so the results can also be read on GitHub (`results/v6/`). If the machine
restarted, the same `nohup` command resumes the job; that is a decision for Shreyas, not for the agent.
