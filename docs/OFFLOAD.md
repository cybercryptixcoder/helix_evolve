# Offloading the VM to GitHub (November 3, 2026)

Helix is paused, and the cloud VM's disk is needed for other work. This is how everything Helix keeps on the VM goes
to GitHub, losslessly, before the VM's copy is deleted.

## What was already on GitHub, and what wasn't

Checked on November 3 from a fresh clone and the releases API:

| | On GitHub | Missing |
|---|---|---|
| Run records, v3 to v10.2 (`results/`): programs, traces, history, state, summary, best construction | every run that published | anything a job never pushed: runs stopped before a push, test runs, logs outside the run folders |
| Constructions (releases `constructions-*`) | v8-s1, v9-s1 (g800 and final), v10-axes, v10-warm, v10.1-axes, v10.1-warm | **v10.2** (its job script never uploaded them; only each run's `best.npy` is in `results/`); **the runs before v8**, except what v8-s1 inherited from the run it continued (never uploaded; each run's best construction is in `results/`) |
| The run folders themselves (everything a job needs to resume) | no | all of them |
| The private routing problem's package and runs (`helix_vrp`, `vrp_work`) | no (they must never be in this public repo) | all of it |

`results/` holds the records as published, but publishing leaves out the constructions and, from v9 on, splits and
renames the big files, so it is not a copy of the run folder a job resumes from. The run folders are the only exact source. So the offload archives every one of them.

## What the offload does

`scripts/offload_vm.sh` (code: `tools/offload.py`). It changes and deletes nothing on the VM.

1. Refuses to start while a Helix job runs (it never stops anything).
2. Preflight: a real test upload to GitHub, checked and removed; whether the private repo exists and is private.
3. An inventory of the machine (read-only): every folder in the home folder with its size, every run folder with its
   generation, best and whether GitHub's `results/` has the same state, every release, `pip freeze`.
4. v10.2's constructions as releases `constructions-v102-helix` and `constructions-v102-helix-s2`, in the format the
   warm starts read (each construction verified by re-scoring first).
5. One release per unit, `archive-<unit>`:
   - `runs-<folder>` for each folder under `runs/` (except `runs/vault`, which holds copies of releases already on
     GitHub);
   - `checkout-extras`: the checkout's untracked files outside `runs/` and the loose files in `runs/` (logs, job
     snapshots), never `.env`;
   - anything of the private routing problem (`helix_vrp`, `vrp_work`, `vrp*` files and run folders) goes **only** to
     the private repo (`PRIVATE_REPO`, default `cybercryptixcoder/helix_evolve_private`), and only if GitHub says it is
     private; otherwise it is reported as not archived.

   Each unit is a byte-for-byte tar (sorted, deterministic), gzipped, split into parts under GitHub's 2 GiB limit,
   with a manifest of every file's path, size, mode, time and SHA-256, and a `parts.json` with every part's SHA-256.
   Before upload, every file (gzip files decompressed) is scanned for the key values in `.env` and the lines of
   `.offload_forbid` (gitignored); a unit with a hit is not uploaded and the report names the files.
6. Checks every part on GitHub against its SHA-256, writes `OFFLOAD_REPORT.md`, and uploads the report and the
   inventory to the release `archive-index`. Last line: `== offload complete: every unit verified`, or
   `== offload NOT complete: ...; run this script again`.

Started again after any stop, it rebuilds each archive identically and re-sends only the parts GitHub lacks.

**Tested** (November 3, in the cloud session, GitHub replaced by a folder): a mock VM with run folders, constructions,
a symlink, an empty folder, gzip traces, `.env`, a VRP package and work folder; the whole job; a restore compared
byte for byte (`diff -r`); a rerun (every part kept); an upload failing mid-unit, then a rerun (the uploaded part
kept, the rest sent); a same-size change to one file (caught, one part re-sent); a key and a forbidden name inside a
gzip file (both blocked); a second copy started alongside (refused); `.env` never in any archive. Releases can't be
created from the cloud session, so the real upload path is proven by the preflight's test upload on the VM.

## The steps

1. **Shreyas:** create an empty **private** repo `cybercryptixcoder/helix_evolve_private` on GitHub.
2. **Aether** (the prompt below): writes `.offload_forbid`, starts the offload, checks the start once.
3. **Shreyas** checks in until the log's last line is `== offload complete: every unit verified`.
4. **Claude** reads the report from the release `archive-index`, checks the inventory against the archives (every
   folder on the machine accounted for), and restores a sample to check it.
5. Only then, **Shreyas** decides on deleting the VM's copy (a separate prompt, written after step 4).

### The prompt for Aether

> Start my Helix offload job on this machine and report back. Don't change any code or settings; just start it.
>
> 1. Work in /home/ubuntu/helix_v5_run. Run `git pull` there. Check that scripts/offload_vm.sh and tools/offload.py
>    exist.
> 2. Create the file /home/ubuntu/helix_v5_run/.offload_forbid containing these lines, one per line:
>    <the lines Shreyas gives>. Never commit or push it.
> 3. Start the job in the background, exactly like this (one command):
>    `cd /home/ubuntu/helix_v5_run && setsid nohup bash scripts/offload_vm.sh > offload.log 2>&1 < /dev/null &`
> 4. Don't change any setting.
> 5. Wait about 15 minutes, then read the last 30 lines of /home/ubuntu/helix_v5_run/offload.log once. A good start
>    shows, in order: "== Helix offload job", "GitHub: can write releases of cybercryptixcoder/helix_evolve",
>    "private repo cybercryptixcoder/helix_evolve_private: exists and is private", "preflight passed", "== inventory:",
>    then lines for "constructions-v102-helix" and units such as "== runs-v4:" with "progress:" lines. A line
>    starting with "preflight:" or a Traceback means the job stopped: report those lines exactly, and don't edit
>    anything to fix it.
> 6. Report what you saw (quote the lines), the output of `free -m` and `df -h /`, and
>    `pgrep -fa offload_job_snapshot`.
> 7. Then stop. Don't stop, restart, kill or delete anything. Don't set up cron jobs, scheduled check-ins or
>    reminders: I check in myself.

Status later: "read the last 15 lines of /home/ubuntu/helix_v5_run/offload.log and quote them; say whether
`pgrep -fa offload_job_snapshot` shows a process. Nothing else." Starting again after any stop is the same command.

## Restoring and continuing a run

```bash
python3 tools/offload.py restore --unit runs-v102 --out runs/          # -> runs/v102/..., every file's SHA-256 checked
python3 tools/offload.py restore --unit private-vrp_work --repo cybercryptixcoder/helix_evolve_private --out /home/ubuntu/
```

A restored run folder is exactly the folder the job left, so its job script resumes it from its last finished
generation (for v10.2: `ARM=helix SEED=1 GENS=600 bash scripts/run_v102.sh`), as if it had never stopped. Resuming
from an earlier generation than the last isn't built: every log is append-only and tagged by generation, so the
state at an earlier generation can be rebuilt from the archive, but that needs a small tool written first.
