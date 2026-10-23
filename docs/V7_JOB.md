# The v7 jobs (October 23, 2026): autocorrelation and the VRP, side by side

Two runs of Helix v7 (`docs/V7_DESIGN.md`), each warm-started from the best that exists, running at the same time on
the VM, as Shreyas asked ("two runs running in parallel on the machine"). They share helix4's machine-wide
evaluation slots (2), so each runs a bit slower than alone.

| | Autocorrelation (ac2) | VRP (fake data on the VM) |
|---|---|---|
| Script | `scripts/run_v7_warm.sh` (this repo) | `helix_vrp/scripts/run_vrp_job.sh` with `VERSION=v7` (the private package) |
| Starts from | v47-s2 at generation 190, kept whole: 289 programs, constructions, findings, history; record 0.9412296 | the best VRP program so far, atlas-s1/p0292 (1.6961 on the held-out worlds), with Code Zero kept as p0001; a fresh Atlas |
| Generations | 100 more (191–290), 60 s of CPU per program | 100 (1–100) |
| Time, estimated | about 5–6 minutes a generation: 9–11 hours | about 7 minutes a generation: 11–13 hours |
| Deadline | 20 hours after the first start | 20 hours after the first start |
| Results | `results/v7warm/` (pushed): the run, `REPORT.md`, `VERIFICATION.md` | `vrp_work/results/held_out_scores_v7.md` and `vrp_work/vrp_results_v7.tgz` (never pushed) |

**What each tests.**
- **ac2:** whether the run that broke through at generation 177 goes further when nothing is closed and exploration
  rises as the record stalls. In v4.7, rule 1 closed the record's line at generation 182, while it was still climbing.
- **VRP:** whether v7 moves past the plateau of the 49-generation v4 run, starting from its best program.

On the VRP, v7 first evaluates the starting program 3 times. The spread between those scores becomes its noise floor
(`noise.json`), so a lucky re-evaluation isn't counted as a record.

## Starting both (what the Hermes prompt below does)

```bash
cd /home/ubuntu/helix_v5_run && git pull                       # the VM's checkout of this repo (with .env)
HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots nohup bash scripts/run_v7_warm.sh > v7_warm.log 2>&1 &

cd /home/ubuntu && unzip -o helix_vrp.zip                      # the new private package, next to the other folders
cd /home/ubuntu && VERSION=v7 SEEDS=1 GENS=100 HOURS=20 MAX_WAIT_MIN=0 \
  HELIX_EVOLVE=/home/ubuntu/helix_v5_run HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots \
  SEED_PROGRAM=/home/ubuntu/vrp_work/runs/atlas-s1/programs.jsonl:p0292 \
  nohup bash helix_vrp/scripts/run_vrp_job.sh > vrp_job_v7.log 2>&1 &
```

- **Both scripts are safe to re-run.** A second copy exits at once, and a stopped run resumes from its last finished
  generation (the same command again).
- **The autocorrelation job** waits for any other autocorrelation Helix run, but not for the VRP job. The VRP job
  (with `MAX_WAIT_MIN=0`) starts at once.
- **Neither stops anything.**
- **Progress:**
  - `v7_warm.log` and `vrp_job_v7.log` get a line every 10 minutes;
  - `runs/v7warm/v7-s1.log` and `vrp_work/runs/v7-s1.log` get a line per generation, showing the level, the slots and
    the track events;
  - the autocorrelation job pushes its progress every 40 minutes.

## The prompt for the Hermes agent

> Start my two Helix v7 jobs on this machine, side by side, and report back. Don't change any code or settings; just
> start them.
>
> 1. Work in /home/ubuntu/helix_v5_run (the checkout with the .env file). Run `git pull` there. Check that
>    scripts/run_v7_warm.sh exists, and that the folder runs/v47warm/v47-s2 exists and has a constructions/ folder.
>    Don't touch runs/v47warm.
> 2. Start the autocorrelation job in the background, exactly like this, from /home/ubuntu/helix_v5_run:
>    `HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots nohup bash scripts/run_v7_warm.sh > v7_warm.log 2>&1 &`
> 3. I uploaded helix_vrp.zip. Unzip it in /home/ubuntu, so that it replaces /home/ubuntu/helix_vrp:
>    `cd /home/ubuntu && unzip -o helix_vrp.zip`. Never commit or push anything from helix_vrp/ or vrp_work/ (they are
>    private), and don't put them inside helix_v5_run. Don't touch vrp_work/runs.
> 4. Start the VRP job in the background, exactly like this, from /home/ubuntu (one command):
>    `cd /home/ubuntu && VERSION=v7 SEEDS=1 GENS=100 HOURS=20 MAX_WAIT_MIN=0 HELIX_EVOLVE=/home/ubuntu/helix_v5_run HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots SEED_PROGRAM=/home/ubuntu/vrp_work/runs/atlas-s1/programs.jsonl:p0292 nohup bash helix_vrp/scripts/run_vrp_job.sh > vrp_job_v7.log 2>&1 &`
> 5. Don't change any setting: other agents share this machine, and the two jobs are sized for it together.
> 6. Wait about five minutes, then read the last 20 lines of each of these once:
>    /home/ubuntu/helix_v5_run/v7_warm.log, /home/ubuntu/helix_v5_run/runs/v7warm/v7-s1.log,
>    /home/ubuntu/vrp_job_v7.log and /home/ubuntu/vrp_work/runs/v7-s1.log.
>    - The autocorrelation job should show "crash test passed", "model answers", "warm start from
>      runs/v47warm/v47-s2 (... constructions)", "continues from generation 190 to generation 290", "running".
>      Its run log should show "resuming after generation 190", then "gen 191: ...".
>    - The VRP job should show "the starting program: atlas-s1/p0292", "your loaders compile a tiny fake world ...
>      ok", "v7-s1: starting". Its run log should show "Code Zero (the current method) scores ...", then "the warm
>      start (atlas-s1/p0292) scores ... (median of 3)" and a "calibration" line. Generation 1 takes several minutes
>      after that.
>    - A line starting with "preflight:" or "warm start:", or a Traceback, means a job stopped. Report the exact
>      lines; don't edit any code to fix it.
> 7. Report what you saw: the lines above, and the calibration line in full. Then stop. Don't stop, restart or kill any
>    process. Don't set up cron jobs, scheduled check-ins or reminders: I check in myself.

## Collecting the results later

- **ac2:** pushed by the job, to `results/v7warm/`:
  - `v7-s1/`: summary, history, plans, findings, tracks, programs, the best construction;
  - `REPORT.md`: records, levels, slots and tracks, generation by generation;
  - `VERIFICATION.md`: the best construction re-scored three ways.
- **VRP:** `/home/ubuntu/vrp_work/vrp_results_v7.tgz`, with:
  - `vrp_work/results/held_out_scores_v7.md`, which also scores the earlier v4 and v4.7 runs in the same session, so
    all three can be compared;
  - `vrp_work/results/REPORT_v7-s1.md`, what v7's exploration did, generation by generation.
