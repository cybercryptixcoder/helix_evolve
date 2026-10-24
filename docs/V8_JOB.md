# The v8 jobs (October 24, 2026): autocorrelation and the VRP, side by side

Two runs of Helix v8 (`docs/V8_DESIGN.md`), each continuing its v7 run with everything it had, running at the same
time on the VM. As before, they share helix4's machine-wide evaluation slots (2).

| | Autocorrelation (ac2) | VRP (fake data on the VM) |
|---|---|---|
| Script | `scripts/run_v8_warm.sh` (this repo) | `helix_vrp/scripts/run_vrp_job.sh` with `VERSION=v8` (the private package) |
| Continues | v7-s1 at generation 290: 942 programs, their constructions, findings, tracks; record 0.9412521 | v7-s1 at generation 100: 602 programs, findings, tracks, the noise measurement; record 1.650480 |
| First generation | every earlier track's best is put on the map of hills (free: from the constructions) | the same, after the record, Code Zero and the 12 best earlier tracks are evaluated once more for their signatures (about 15 minutes) |
| Generations | 100 more (291–390), 60 s of CPU per program | 100 more (101–200) |
| Time, estimated | 9–15 hours | 11–13 hours |
| Deadline | 20 hours after the first start | 20 hours after the first start |
| Results | pushed to `results/v8warm/`: the run (with `hills.jsonl`), `REPORT.md` with the map, `VERIFICATION.md` | `vrp_work/results/held_out_scores_v8.md` (v8 against v7, v4.7 and v4, scored in the same session), `REPORT_v8-s1.md`, `vrp_work/vrp_results_v8.tgz`; never pushed |

**What to look for in the run logs**, one line per generation:
- `N hills, K new` and events such as `new hill H5, found by T93 (restart)`, `T95 landed on H2 (distance 0.03)` and
  `T97 is now the top of H3`;
- whether a side track on a new hill takes the record (`T.. took the record`).

## Starting both (what the Hermes prompt below does)

```bash
cd /home/ubuntu/helix_v5_run && git pull                       # the VM's checkout of this repo (with .env)
HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots nohup bash scripts/run_v8_warm.sh > v8_warm.log 2>&1 &

cd /home/ubuntu && python3 -c "import zipfile; zipfile.ZipFile('helix_vrp.zip').extractall('.')"   # the new private package
cd /home/ubuntu && VERSION=v8 SEEDS=1 GENS=200 HOURS=20 MAX_WAIT_MIN=0 \
  HELIX_EVOLVE=/home/ubuntu/helix_v5_run HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots \
  WARM_FROM=/home/ubuntu/vrp_work/runs/v7-s1 \
  nohup bash helix_vrp/scripts/run_vrp_job.sh > vrp_job_v8.log 2>&1 &
```

- **Both are safe to re-run.** A second copy exits at once, and a stopped run resumes from its last finished
  generation.
- **The sources are only read.** The new runs are copies: `runs/v8warm/v8-s1` and `vrp_work/runs/v8-s1`.
- **Neither job stops anything.**

## The prompt for the Hermes agent

> Start my two Helix v8 jobs on this machine, side by side, and report back. Don't change any code or settings; just
> start them.
>
> 1. Work in /home/ubuntu/helix_v5_run (the checkout with the .env file). Run `git pull` there. Check that
>    scripts/run_v8_warm.sh exists, and that runs/v7warm/v7-s1 exists and has a constructions/ folder. Don't change
>    anything in runs/v7warm.
> 2. Start the autocorrelation job in the background, exactly like this, from /home/ubuntu/helix_v5_run:
>    `HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots nohup bash scripts/run_v8_warm.sh > v8_warm.log 2>&1 &`
> 3. I uploaded helix_vrp.zip. Put it at /home/ubuntu/helix_vrp.zip (rename it if it arrived with another name) and
>    extract it in /home/ubuntu so that it replaces /home/ubuntu/helix_vrp. unzip may be missing; use Python:
>    `cd /home/ubuntu && python3 -c "import zipfile; zipfile.ZipFile('helix_vrp.zip').extractall('.')"`.
>    Never commit or push anything from helix_vrp/ or vrp_work/ (they are private), and don't put them inside
>    helix_v5_run. Don't change anything in vrp_work/runs.
> 4. Start the VRP job in the background, exactly like this, from /home/ubuntu (one command):
>    `cd /home/ubuntu && VERSION=v8 SEEDS=1 GENS=200 HOURS=20 MAX_WAIT_MIN=0 HELIX_EVOLVE=/home/ubuntu/helix_v5_run HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots WARM_FROM=/home/ubuntu/vrp_work/runs/v7-s1 nohup bash helix_vrp/scripts/run_vrp_job.sh > vrp_job_v8.log 2>&1 &`
> 5. Don't change any setting: other agents share this machine, and the two jobs are sized for it together.
> 6. Wait about five minutes, then read the last 20 lines of each of these once:
>    /home/ubuntu/helix_v5_run/v8_warm.log, /home/ubuntu/helix_v5_run/runs/v8warm/v8-s1.log,
>    /home/ubuntu/vrp_job_v8.log and /home/ubuntu/vrp_work/runs/v8-s1.log.
>    - The autocorrelation job should show "crash test passed (v8, fake model)", "model answers", "warm start from
>      runs/v7warm/v7-s1 (... constructions)", "continues from generation 290 to generation 390" and "running". Its
>      run log should show "resuming after generation 290", then "gen 291: ...", with "the map begins with ... known
>      hills".
>    - The VRP job should show "continuing /home/ubuntu/vrp_work/runs/v7-s1 (602 programs, after generation 100)",
>      "your loaders compile a tiny fake world ... ok" and "v8-s1: starting". Its run log should show "prepared ... as
>      a v8 run" and "resuming after generation 100". The first generation takes longer than the others (about 15
>      minutes more): it first evaluates earlier programs again for the map, and then logs "the map: ... earlier
>      programs evaluated again for their signatures".
>    - A line starting with "preflight:" or "warm start:", or a Traceback, means a job stopped. Report the exact
>      lines; don't edit any code to fix it.
> 7. Report what you saw, including the line with "the map begins with" from each run log once it appears. Then
>    stop. Don't stop, restart or kill any process. Don't set up cron jobs, scheduled check-ins or reminders: I check
>    in myself.

## Collecting the results later

- **ac2:** pushed by the job to `results/v8warm/`. `REPORT.md` has the map: every hill, who found it, its top, how
  often it was reached, and the shared decisions with where their flips landed.
- **VRP:** `/home/ubuntu/vrp_work/vrp_results_v8.tgz`. It includes `runs/v8-s1/hills.jsonl` and
  `signatures.jsonl`, the held-out table and the report. To bring it over, download it whole and attach it once the
  download has finished.
