# The v9 job (October 27, 2026): v8-s1 continued as a v9 run, on the autocorrelation problem

One run of Helix v9 (`docs/V9_DESIGN.md`) that continues the v8 run v8-s1 with everything it had, and adds the
design map. Script: `scripts/run_v9_warm.sh`. It runs on the VM, gently (the budget in `docs/AETHER.md`).

| | |
|---|---|
| Continues | v8-s1 at generation 700, as pushed to GitHub (`results/v8warm/v8-s1`): 3,625 programs, 6,555 findings events (the Atlas), 242 tracks, 73 hills; record **0.9414417** (p3596, N = 104,992) |
| Adds | the design map: a codebook of design decisions, coordinates for every program, a model of the landscape, drops and flips chosen from it, ablations, the fair race, discovery |
| Generations | 100 more (701–800), 60 s of CPU per program, 2 evaluation slots shared machine-wide |
| Time, estimated | first start: preflight 2 min, the pack a few minutes; then 3-8 min a generation (measured live: 160-510 s, about 4 min on average), so about 7 hours |
| Deadline | 24 hours after the first start (the run stops after the generation in progress) |
| Model | DeepSeek V4.1 Flash via Luminal, as v8; measured live: about 20 calls, 155k tokens in and 40k out a generation (about $0.10 at DeepSeek's list prices, so about $10 for the job) |
| Memory | about 2 GB at peak (the run, and up to 2 evaluations of about 0.5 GB) |
| Disk | about 1 GB in `runs/v9warm` (constructions of new programs are 0.8 MB each); refuses to start below 3 GB free |
| Results | pushed to `results/v9warm/` every 40 minutes and at the end (below) |

## What comes from GitHub, and what from the VM

The continuation is built from GitHub's copy of v8-s1, so it could run on any machine. One thing GitHub didn't have:
the constructions (0.8 MB each, 3,441 of them, about 3 GB) and the signatures computed from them. Without them every
base but the record would be lost. So:

1. **The continuation pack** (`helix9/pack.py`), built once on the VM by the job's first start, from
   `runs/v8warm/v8-s1/constructions`: every construction is **verified** (re-scored with the problem's own scorer, it
   must give the recorded score to 1e-12 and the recorded number of steps), the signatures of all of them are kept,
   and the constructions a continuation builds on most (the record, every hill's top, every track's best, the
   record's lineage, the 60 strongest, the last 10 generations) are packed losslessly up to 80 MB, in files of at most
   40 MB. It is pushed to `results/v8warm/v8-s1/pack/`. From then on, a continuation needs only GitHub.
2. **On the VM, nothing is lost:** a base the pack doesn't hold is copied from the local folder when the run needs it,
   verified first (`HELIX9_LOCAL_CONSTRUCTIONS`, set by the job). Nothing is copied in bulk.
3. **On a machine with only GitHub:** a base the pack doesn't hold is rebuilt by running its code again (from its
   close ancestor, or the program whose output is most like its own), approximately, and logged; and the wide loop
   samples the programs whose constructions are at hand.

At the end the job builds the v9 run's own pack (only what v8's pack doesn't hold, naming it as its base) and pushes
the run in full, so the next continuation (v9 or later) starts from GitHub alone the same way.

## The stages

1. **Preflight** (`preflight:` lines on failure; exits 3): Python, numpy and scipy; disk; a crash test of the whole
   pipeline (2 v9 generations with a fake model, the report, publishing, a pack); one real model call; GitHub push
   access.
2. **The source**: `results/v8warm/v8-s1` (after `git pull`), printed with its generation, programs and record.
3. **The pack**: built and pushed if GitHub doesn't have it yet; otherwise used as it is.
4. **The replay** (`helix9/replay.py`, stage 0 of the proof of concept): **already done, live, and on GitHub**
   (`results/v9warm/replay/`): the model built a codebook from the Cartographer's 82 scans, read 458 of v8's
   programs (a quarter twice), and 120 later changes from their diffs. Verdicts: 12 of 13 decisions read with at
   least 80% agreement; the model ranks later changes better than chance, weakly (+0.16, p = 0.04). The job prints
   these verdicts and uses its codebook and coordinates to seed the run's design map; it would run the replay
   itself only if GitHub didn't have it (10-20 minutes; `REPLAY=0` skips it).
5. **The warm start** (`helix9/warm.py`): everything of v8-s1 kept, the pack and the replay restored, and the race
   applied to v8's explorations as v9 would have judged them (the 2 strongest that were still rising race again; the
   rest wait, paused, and a gain wakes one).
6. **The run** (`helix9/job.py`): generations 701–800. Progress every 10 minutes; a push every 40 minutes.
7. **The end**: the report, the verification of the record (three independent ways, `tools/verify_ac2.py`), the run's
   own pack, and the push.

**Robust** (`docs/AETHER.md` sections 4 and 4b, all tested with a fake model): one copy at a time; runs from a
snapshot of itself; a stop signal finishes the generation in progress (up to 5 minutes) and pushes everything; a
second signal or the grace running out stops at once; `kill -9` of the run is retried (up to 3 times) and resumes;
lines cut off by a hard stop are trimmed; a restart pushes what it has, then resumes; while the disk or the model is
down, the run waits; it waits (never stops anything) while another autocorrelation Helix run is running. It installs
no cron job or timer and kills nothing but its own run.

## Starting it (what the Aether prompt below does)

```bash
cd /home/ubuntu/helix_v5_run && git pull                       # the VM's checkout of this repo (with .env)
HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots setsid nohup bash scripts/run_v9_warm.sh > v9_warm.log 2>&1 < /dev/null &
```

Settings (environment variables): `ADD` (100) or `GENS` (800), `HOURS` (24), `RESET_DEADLINE=1` to set a new one,
`BUDGET` (60), `EVAL_SLOTS` (2), `REPLAY` (1), `REPLAY_SAMPLE` (150), `PACK_MB` (80), `SRC`, `LOCAL_SEARCH`,
`MAX_WAIT_MIN`, `PUSH`, `FAKE`. The whole job with a fake model, as a test:
`FAKE=1 PUSH=0 ADD=2 BUDGET=2 bash scripts/run_v9_warm.sh`.

## The prompt for Aether

> Start my Helix v9 job on this machine and report back. Don't change any code or settings; just start it.
>
> 1. Work in /home/ubuntu/helix_v5_run (the checkout with the .env file). Run `git pull` there. Check that
>    scripts/run_v9_warm.sh exists, that results/v8warm/v8-s1/state.json exists, and that
>    runs/v8warm/v8-s1/constructions exists; report how many files it holds
>    (`ls runs/v8warm/v8-s1/constructions | wc -l`). Don't change anything in runs/v8warm or results/v8warm.
> 2. Start the job in the background, exactly like this (one command):
>    `cd /home/ubuntu/helix_v5_run && HELIX4_SLOTS_DIR=/home/ubuntu/helix_v5_run/runs/v4/.slots setsid nohup bash scripts/run_v9_warm.sh > v9_warm.log 2>&1 < /dev/null &`
> 3. Don't change any setting: other agents share this machine, and the job is sized for it.
> 4. Wait about 20 minutes (its first start builds a pack before the run begins), then read the last
>    30 lines of /home/ubuntu/helix_v5_run/v9_warm.log and the last 10 lines of
>    /home/ubuntu/helix_v5_run/runs/v9warm/v9-s1.log once. A good start shows, in order:
>    "crash test passed (v9: 2 generations with a fake model, report, publish, pack)", "model answers",
>    "GitHub: can push", "the source: results/v8warm/v8-s1 (v8), generation 700, 3625 programs, record 0.941441744
>    (p3596)", a line starting "pack:" with how many constructions were verified, "the replay: done already", the
>    replay's verdict lines ("Reliability: 12 of 13 ...", "The model's knowledge: ..."), "the warm start",
>    "v9-s1 continues from generation 700 to generation 800", "constructions the pack doesn't hold: taken from" and
>    "running". The run log should show "resuming after generation 700" and then "gen 701: ..." (a generation takes
>    3 to 8 minutes). If the pack is still being built at 20 minutes, wait 15 more and read again, once.
>    A line starting with "preflight:" or "warm start:", or a Traceback, means the job stopped: report those lines
>    exactly, and don't edit anything to fix it.
> 5. Report what you saw (quote the lines, including the "pack:" line and the replay's verdict lines), the output of
>    `free -m` and `df -h /`, and the job's process: find it with `pgrep -fa v9_job_snapshot` and report
>    `ps -o pid,sid,ppid,etime,cmd -p <pid>`.
> 6. Then stop. Don't stop, restart or kill any process. Don't set up cron jobs, scheduled check-ins or reminders: I
>    check in myself.

**Status later** ("how is it going?"): the latest `== HH:MM progress:` line of `v9_warm.log` and the last `gen ...`
line of `runs/v9warm/v9-s1.log`, verbatim, and whether the process is alive. **Stopping it** (only on Shreyas's
order): `kill -TERM <the job's pid>` (the bash process found above, not its Python run); the job finishes the
generation in progress, pushes, and ends with "== stopped before generation N ...". Never `kill -9`. Running the same
start command again later continues it.

## Watching it, and the results

- **Live, from any browser:** `viz/mapview.html` (open it from a clone, or any static host of this repo), source
  "v9 on the autocorrelation problem (live)", then **Live**: it reloads `results/v9warm/v9-s1/mapview.json` from
  GitHub every minute (it changes at each push, every 40 minutes). The map of programs by design, the landscape
  estimated from their scores (contours, or the terrain view), the record's climb, the race's curves, the design map's
  decisions and what happened, generation by generation.
- `results/v9warm/REPORT.md`: v8's report (records, tracks, the map of hills) plus the design map: each decision,
  how reliably it is read, its importance; every drop, flip and ablation with its target, how much of it was built,
  its race, where it landed; discoveries; constructions rebuilt.
- `results/v9warm/replay/REPLAY.md`: the replay's verdicts. `results/v9warm/VERIFICATION.md`: the record, verified.
- `results/v9warm/v9-s1/`: the whole run. Small files as they are; programs, the trace (every model call, in full),
  tracks, hills, plans, findings and the map's rows in gzipped chunks (`programs/part-0001.jsonl.gz`, ...);
  `python -m helix9.publish --join results/v9warm/v9-s1 --out /tmp/v9-s1` turns them back into plain files, and
  helix9's tools read them as they are. `pack/`: the run's own continuation pack.
