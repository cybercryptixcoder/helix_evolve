# The v4.7 warm-start job: how far past 0.9408 can it go?

Asked by Shreyas on October 23, 2026, 03:50. Start the second autocorrelation problem from the best of the
150-generation v4 run (0.940795), under v4.7, and see how good it can get. The from-scratch comparison of v4.7 with v4
(`docs/V47_JOB.md`) comes after this job.

## The question it also answers: keep the old Atlas, or start fresh?

Two runs, the same starting construction, the same compute:

| Run | What it starts with |
|---|---|
| **v47-s1, "continue"** | Generation 151 of the same run. Every program (901), their constructions, every finding (892) and the history are kept. All earlier programs form line L1, which gets 4 generations under v4.7 before it can close. Then new lines open from alternatives, from other branches of the 150-generation tree, or from Code Zero. |
| **v47-s2, "best only"** | Just the best program and its construction, with a fresh Atlas. The archive holds Code Zero (for fresh lines) and the best program. Line L1 starts from it. |

**What each one bets on:**
- **The continue run bets that the old knowledge helps.** The 892 findings include what works (gradient ascent with a
  smooth max, resolution ladders, polishing near the maximum) and around 400 failures on the 0.9408 construction.
  - In v4 that knowledge produced the false ceiling.
  - In v4.7 the failures of a closed line are only counted, not listed, and the tree offers other branches as starting
    points.
- **The fresh run bets that a clean slate frees the search.** It doesn't re-read 150 generations of "saturated", but it
  also can't know what was tried.

My expectation is that the continue run does better. Its knowledge of methods carries over, v4.7 keeps the failures
from dominating the view, and its tree gives new lines real alternatives to start from. The fresh run's only other
starting points are Code Zero and alternatives it builds itself. This is the first direct test of that.

**Both runs are numbered from generation 151**, so the comparison table (`helix47/compare.py`) counts generations from
the start of the warm phase.

## Why 60 s per program, not 30

Above 0.94 the binding limit is compute per attempt. The constructions that beat 0.9408 in the literature use
400,000–1,600,000 steps and minutes to hours of optimisation (`docs/VERSIONS.md` has the references). At 30 s on one
ARM core, a program can't do many passes at 200,000+ steps.

60 s doubles what each attempt can do, at twice the evaluation time per generation. This job asks how far it can go,
not how v4.7 compares with v4 at equal compute (the other job does that), so the extra compute is fair here.

## Running it

From the VM's working checkout, after the VRP v4.7 job (which this job waits for):

```bash
cd /home/ubuntu/helix_v5_run && git pull
setsid nohup bash scripts/run_v47_warm.sh > v47_warm.log 2>&1 < /dev/null &
```

- **It finds the 150-generation run folder by itself.** That is the folder whose state says generation 150, with the
  most constructions. If none is found, it falls back to `results/v4cont/atlas-s1` in the repo, which has the programs
  and the best construction only.
- **Then it runs `scripts/run_v47_jobs.sh`** for the two runs: waiting for other jobs, preflight, a 10-hour deadline,
  and results pushed to `results/v47warm/` (`COMPARISON.md`, and every best construction re-scored in `VERIFICATION.md`).
- **Time:** 40 generations; about 6–7 minutes per generation for the two runs together, so about 4.5 hours.
- **Settings:**
  - `SRC=/path` gives the source run folder.
  - `GENS` is the last generation (default 190).
  - `BUDGET` is the seconds per program (default 60).

## The Hermes prompt

The from-scratch v4.7 job is already queued and waiting for the VRP job. It has to stop waiting first, or both jobs
would start together when the VRP job ends. Stopping it loses nothing, since it hasn't started any run.

> One-time exception, explicitly authorised by me: replace the queued v4.7 job with the warm-start job. Don't edit
> code.
>
> 1. The queued job is only waiting (it has started no run). Show it:
>    `pgrep -af "v47_job_snapshot|run_v47_jobs"`
>    Stop exactly those processes with `kill <pid>`. Touch nothing else, and in particular not the VRP job
>    (vrp_job_snapshot, helix_vrp). Check that `pgrep -af "v47_job_snapshot|run_v47_jobs"` prints nothing and that
>    `pgrep -af "vrp_job_snapshot"` still shows the VRP job.
> 2. cd /home/ubuntu/helix_v5_run && git pull. Check that scripts/run_v47_warm.sh exists.
> 3. Start the warm-start job, from /home/ubuntu/helix_v5_run:
>    `setsid nohup bash scripts/run_v47_warm.sh > v47_warm.log 2>&1 < /dev/null &`
> 4. Wait about two minutes, then read the last 20 lines of v47_warm.log, once.
>    - Expected: "== warm start from <a folder> (N constructions)"; two lines "continue: 901 programs …" and
>      "best: Code Zero and …"; "crash tests passed"; "model answers"; then "waiting for the other Helix job to
>      finish" (the VRP job).
>    - Report which folder it chose and how many constructions it found.
>    - A line starting with "warm start:" or "preflight:", or a Traceback: report the exact lines; don't edit code.
> 5. Report, then stop. No further kills, no restarts, no cron jobs, check-ins or reminders: I check in myself.

## Afterwards

- **The from-scratch job:** run `scripts/run_v47_jobs.sh` as in `docs/V47_JOB.md`. It waits for this one.
- **What to read:**
  - in `results/v47warm/COMPARISON.md`, whether either run passes 0.940795, by how much, and when;
  - whether L1 closed and new lines took over;
  - which of the two runs did better, which answers keep-the-Atlas versus start-fresh.
