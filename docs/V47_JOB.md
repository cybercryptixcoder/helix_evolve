# The Helix v4.7 job

**What it runs:**
- the problem: the second autocorrelation inequality;
- the versions: v4.7 (v4 without the false ceiling, `docs/V47_DESIGN.md`) and plain v4 (Atlas), side by side on the
  same machine and the same night, so the comparison is fair;
- the size: 3 seeds each, so 6 runs, 30 generations each;
- the compute: 30 s of CPU per program, as in every earlier job. v4.7's step-change and challenger experiments get
  60 s, but only while a run is stalled.

## Running it

```bash
cd helix_v5_run && git pull        # the VM's working checkout (it has the .env with the keys)
setsid nohup bash scripts/run_v47_jobs.sh > v47_jobs.log 2>&1 < /dev/null &
```

- **Preflight** (about a minute): numpy and scipy; a crash test of v4.7 and of v4 with a fake model; one real model
  call.
- **It waits** for any other Helix job to finish, the VRP job included, however long that takes. It prints a line
  every 30 minutes while it waits, and it never stops anything. `MAX_WAIT_MIN=n` starts it after n minutes anyway.
- **One copy at a time.** A second start exits at once ("this job is already running").
- **Time:** about 6 to 8 hours once it starts. The deadline is 10 hours after the start and is kept across restarts.
- **Resuming:** run the same command again. Finished runs are skipped, and unfinished ones resume from their last
  generation.
- **Results:**
  - each finished run is copied to `results/v47/<run>/` and pushed;
  - progress is pushed every 40 minutes;
  - `results/v47/COMPARISON.md`: v4.7 against v4, generation by generation;
  - `results/v47/VERIFICATION.md`: every best construction re-scored three ways.
- **If pushing fails:** `tar czf helix_v47_results.tgz results/v47 runs/v47 v47_jobs.log`.

**Knobs** (leave them at their defaults on the shared VM):

| Knob | Default |
|---|---|
| `GENS` | 30 |
| `SEEDS` | "1 2 3" |
| `CONDITIONS` | "v47 v4" |
| `BUDGET` | 30 |
| `HOURS` | 10 |
| `EVAL_SLOTS` | 2 |
| `MIN_FREE_MB` | 1200 |
| `PUSH` | 1 |
| `FAKE` | 1 = no model calls, a test |
| `MAX_WAIT_MIN` | (none) |

## The prompt for the Hermes agent

It starts the job, checks the start once and reports. It contains no instruction to stop, kill or restart
anything, and none to schedule wake-ups, crons or check-ins (standing rule, `docs/REQUESTS.md`).

> Start my Helix v4.7 job on this machine and report back. Don't change any code or settings; just start it.
>
> 1. Work in /home/ubuntu/helix_v5_run (the checkout with the .env file). Run `git pull` there. Don't touch
>    ~/helix_evolve, ~/vrp_work or ~/helix_vrp: the VRP job is running and must be left alone.
> 2. Start the job in the background, exactly like this, from /home/ubuntu/helix_v5_run:
>    `setsid nohup bash scripts/run_v47_jobs.sh > v47_jobs.log 2>&1 < /dev/null &`
>    Don't change GENS, SEEDS, EVAL_SLOTS or any other setting: other agents share this machine, and the job is
>    sized for it.
> 3. Wait about two minutes, then read the last 20 lines of v47_jobs.log, once.
>    - "crash tests passed (v4.7, v4, fake model)" and "model answers: …", then "waiting for the other Helix job to
>      finish", is expected while the VRP job runs. This job starts by itself when the VRP job ends. Leave both alone.
>    - "== v47-s1: starting" (or "resuming") lines mean it is running.
>    - A line starting with "preflight:", or a Traceback, means it stopped. Report the exact lines; don't edit code.
> 4. Report what you saw, then stop. Don't stop, restart or kill any process. Don't set up cron jobs, scheduled
>    check-ins or reminders: I check in myself.
