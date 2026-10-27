# Aether and the cloud VM: how to run long jobs

A general guide, not tied to one project. It covers who Aether is, the machine it runs on, how to write a job that runs
overnight without supervision, how to trace everything so it can be analysed afterwards, how to use Luminal from a job,
and how to write the prompt that hands a job to Aether.

Earlier documents call the agent **Hermes** (the framework it runs on). It's the same agent.

---

## 1. Who Aether is

Aether is Shreyas's operations agent. It controls an Oracle Cloud VM through a terminal. It works under the coding
agent (Claude): **Claude writes the jobs, Aether starts them and reports on them.** The VM runs whether or not
Shreyas's computer is on, so overnight jobs go there.

**What Aether is for:**
- starting a job exactly as written, and checking that the start went well (preflight lines, first progress lines);
- reading logs, process lists, disk, memory and timings, and reporting them;
- moving files: pulling from GitHub, unpacking an uploaded zip, packing results;
- answering "how far along is it?" from the job's own progress lines.

**What Aether is not for:**
- writing or fixing code (it uses a cheap model and writes messy code);
- analysing traces or results, or drawing conclusions;
- making decisions about a run.

**How to read what Aether says.** When Shreyas pastes an Aether reply, trust the **values it read directly from a
command** (a log line, `free -m`, `df -h`, `ps`, a file's contents). Treat its **interpretations, analysis and
suggestions as unreliable**, and check them against the raw values. Examples: an earlier reply called a flat curve a
"ceiling", and one reported "2.4 GB CPU-time spare", which isn't a real quantity. Ask for raw command output when a
number matters.

## 2. Rules that always apply

1. **No cron jobs, no scheduled check-ins, no outside watchdogs and no outside restarts.** Aether doesn't create
   any, and job scripts don't install any. Shreyas checks in himself. (A job may retry *its own* run a few times
   after a crash, inside the same job process, and never touches any other process: see section 4b.) *(On October 21, Aether's own check-in cron carried a
   "restart if dead" instruction. It killed a running job 19 times, once every 12 minutes, and lost about 3.5 hours.
   See `docs/INCIDENT_2026-10-21.md`.)*
2. **Aether never stops, kills or restarts a process** (no `kill`, `pkill`, `systemctl stop`, and no reboot) unless
   Shreyas gives an explicit order for that specific process.
3. **Aether never edits code or settings to fix a failure.** It reports the exact failure lines and stops.
4. **Start every job detached from the terminal session:**
   `setsid nohup bash <script> > <log> 2>&1 < /dev/null &`.
   `nohup` alone isn't enough: the terminal tool's session was reaped once and took the whole job with it.
5. **Never commit secrets or private data:** `.env`, Luminal keys, proprietary data, or results computed from it.
   Those stay on the machine or with Shreyas.
6. **Git identity:** each repo's own, with no AI attribution: `Shreyas Naik
   <119774329+cybercryptixcoder@users.noreply.github.com>` in helix_evolve; a private repo uses the identity its own
   history uses.

## 2b. GitHub is how everything moves

GitHub is the medium of exchange between Claude, Aether and Shreyas, in both directions:
- **Claude → VM:** code, jobs and their documentation are pushed to a repo; Aether runs `git pull` and starts the job.
  Nothing is copied over by hand unless it can't be on GitHub.
- **VM → Claude:** the job pushes its results, reports and **full traces** while it runs and at the end. Claude
  pulls them and analyses them as if the run had happened locally. Aether never summarises results for Claude.
- **Which repo:** the project's own. **helix_evolve is public**, so private work (anything with
  proprietary code or data) lives and is pushed in its own private repo. Its job only *reads* helix_evolve for the
  search code.
- **The exceptions:** keys (`.env`) and proprietary data never go to GitHub. Proprietary data stays on Shreyas's
  computer; only normalised, name-free numbers may leave it.

## 3. The VM

Measured by Aether on October 26, 2026 (22:35 EDT, idle). Re-measure before sizing a big job, since other agents share
the machine.

| | Value |
|---|---|
| Shape | Oracle Ampere A1.Flex, **aarch64** (ARM Neoverse-N1) |
| CPU | **2 vCPU** (2 cores, 1 thread each) |
| RAM | **11.9 GB**; about 9.8 GB available at idle (most of the rest is page cache) |
| Swap | 4.1 GB swapfile (2.4 GB in use at idle, held by an old finished Python process) |
| Disk (storage) | **48 GB boot volume, 39 GB used, 8.5 GB free (83%)**. "Disk" in this guide always means this storage, not RAM |
| GPU | none |
| Uptime record | weeks; no OOM kill seen in the journal |

**Guards already on the machine:**

| Guard | What it does |
|---|---|
| `mem-guard.py` | warns below 900 MB available; below 350 MB restarts Chrome if Chrome holds over 1.2 GB (600 s cooldown) |
| `mem-ballast.py` | a small reserve that keeps the OOM killer away from real work |
| `earlyoom` | running (seen in the October 21 incident) |
| Chrome CDP cap | the browser is killed above 3.5 GB |
| Kernel OOM killer | the last resort; never fired so far |

**Other tenants:** a Chrome browser (Aether's own) and other agents. Assume a few GB and some CPU are always taken.

**Notes on the machine:**
- It is ARM: the occasional wheel isn't prebuilt and compiles slowly. Check imports in the preflight.
- `unzip` isn't installed. Extract with
  `python3 -c "import zipfile; zipfile.ZipFile('x.zip').extractall('.')"`.
- `flock`, `setsid`, `nice` and `ionice` are available.

### Budget rules: what a job may use

**CPU (the binding limit for compute):**
- There are 2 cores. At most **2 CPU-heavy processes on the whole machine**, counting every job.
- Running more doesn't finish sooner. It makes every time limit measure something else, because CPU-time-limited
  programs get less done per wall second. Under heavy contention, programs also time out and runs die.
- Share a machine-wide limit across jobs with file-lock slots (helix4's `HELIX4_SLOTS_DIR` and `HELIX4_EVAL_SLOTS=2`
  are the existing pattern).
- Run compute under `ionice -c 3 nice -n 10`.

**Memory:**
- Size a job's peak at **no more than about 5 GB** in total.
- Cap each worker (for example the evaluator's `MEM_MB`).
- Gate the start on `MemAvailable ≥ 1200 MB` (`MIN_FREE_MB`): the job **waits**, it doesn't fail.
- Swap use isn't a problem by itself; a growing swap while a job runs is.

**Disk, meaning storage (the binding limit today, at 83%):**
- The preflight must check free space, and refuse to start below about 3 GB free or below 2× the job's estimated output.
- Gzip traces.
- Don't keep duplicate copies of run folders.
- Never commit archives over about 50 MB (GitHub warns at 50 MB and rejects files over 100 MB). Split them, or keep the
  big ones on the VM and say where they are.
- Clean-up of old run folders and tarballs is Shreyas's call. Aether may list sizes (`du -sh`), but never deletes
  without an order.

**Model calls:** see section 6. The surge and per-second limits apply **per key, across every job and agent using that
key**.

## 4. Anatomy of an airtight job

A job is one bash script (plus the code it runs) that needs **one command to start**. After that it is self-sufficient:
started, stopped by a crash or a reboot, and started again, it carries on. Every job written for the VM has all of the
following. `scripts/run_v8_warm.sh` is a working example of each part.

| # | Part | What it does |
|---|---|---|
| 1 | **Header** | the exact start command, what the job does, how long it takes, where results go, and every setting it reads |
| 2 | **Snapshot** | the script copies itself and re-executes the copy, so a `git pull` mid-job can't change a running job |
| 3 | **One copy at a time** | `flock -n` on a lock file; a second start prints "already running" and exits **0**, changing nothing |
| 4 | **Settings by environment variable** | defaults in the script, overrides on the command line: `GENS`/`ADD`, `HOURS`, `SEEDS`, `BUDGET`, `EVAL_SLOTS`, `MEM_MB`, `MIN_FREE_MB`, `PUSH`, `FAKE`, `MAX_WAIT_MIN` |
| 5 | **Preflight** | fails loudly in the first minute; every failure line starts with `preflight:` and the job exits 3. Checks: packages import; disk free; memory; a **crash test with a fake model** (the whole pipeline, 1–2 tiny generations); **one real model call**; the input folders exist |
| 6 | **Deadline** | fixed at the first start (a `deadline` file) and kept across restarts; the job stops after the generation in progress. Extending it is an explicit setting (`RESET_DEADLINE=1 HOURS=…`), never a side effect |
| 7 | **Resume** | the run's state is saved atomically after every generation (write a temp file, then `mv`). A restart prints `resuming after generation N` and drops only the unfinished generation |
| 8 | **Extend** | the same command with a larger `ADD` or `GENS` continues a finished run from its last generation |
| 9 | **Waits, never stops** | if another heavy job is running, it waits (printing a line every 30 minutes, up to `MAX_WAIT_MIN`). It never kills anything |
| 10 | **Memory gate** | it waits while `MemAvailable < MIN_FREE_MB`, then starts |
| 11 | **Gentle** | `ionice -c 3 nice -n 10`; shared evaluation slots |
| 12 | **Progress lines** | every 10 minutes, one line starting with `== HH:MM progress:` and its numbers (generation, best, elapsed) |
| 13 | **Push as it goes** | a light push (logs, history, summary, report) every 40 minutes; a full push (programs, gzipped traces) at the end |
| 14 | **Final report** | written into the results folder: what ran, for how long, the best results, anything that went wrong |
| 15 | **Last line** | `== all jobs done`, or `== stopped before generation N (…); run this script again to continue it` |

### 4b. Interruptions: degrade gracefully, resume as if nothing happened

Anything can interrupt a job: a reboot, an out-of-memory kill, the model or the network going down, the disk filling
up, a bug, or Shreyas ordering a stop. Every job must survive all of these: save everything it needs, and when it
is started again, carry on from where it was as if nothing had happened. The parts (all in
a private project's `helix/` folder as a worked, tested example):

| Threat | What the job does |
|---|---|
| **Any stop at all** | State is saved **atomically** after every generation (write a temp file, then `os.replace`). Every log (programs, trace, history) is append-only and flushed per line. Started again, the job resumes after the last finished generation; only the generation in progress is lost and redone |
| **A stop signal** (SIGTERM/SIGINT/SIGHUP: Shreyas's order, a reboot) | The job passes it to the run. The run **finishes the generation in progress** (up to a grace period, e.g. 5 minutes) and saves, then the job **pushes everything** and exits. A second signal, or the grace running out, stops the run at once (the generation in progress is redone on resume). Duplicate signals arriving together (a shutdown signals every process) count as one |
| **A hard kill** (SIGKILL, OOM, power loss) | Nothing runs at that moment, so the next start does the clean-up: JSONL files cut off mid-line are trimmed back to their last whole line, partial results of unfinished programs are deleted, and a **catch-up push** sends what was saved before the run resumes |
| **The run crashes** (a bug, an unexpected exception) | The job retries **its own run** up to `MAX_RETRIES` (3) times, 60 s apart, each resuming from the last finished generation, then stops and says so. It never restarts anything else |
| **The model or network is down** | Before each generation the run checks the model with a one-word call. While it fails, the run **waits** (1, 2, 4 ... up to 30 minutes between checks) instead of burning generations on empty replies |
| **The disk fills up** | The preflight refuses to start below a threshold (3 GB); between generations the run waits while less than 800 MB is free |
| **Memory gets tight** | The job waits for `MIN_FREE_MB` before starting; every evaluation waits for free memory and a machine-wide slot |
| **The deadline passes** | The run stops after the generation in progress; `RESET_DEADLINE=1 HOURS=n` and the same command continue it |
| **A `git pull` mid-run** | The job runs from a snapshot of itself, so the running job never changes under its own feet |
| **A push fails** | Results stay on disk; the next push (every 40 minutes, at the end, or at the next start) sends them |

**Test every one of these before handing a job over** (with a fake model): a stop signal mid-generation, a restart
(it must resume and push first), a `kill -9` of the run mid-generation (it must retry and resume), a torn last line,
and the grace running out.

### Line vocabulary (so Aether can match lines without interpreting)

| Prefix | Meaning |
|---|---|
| `== ` | a normal step or milestone |
| `   ` (indent) | detail under a step |
| `preflight:` | a fatal problem before the start |
| `warm start:` | a fatal problem in the warm start |
| `Traceback` | a crash; the job may stop |
| `(push failed: …)` | results are safe locally but not on GitHub yet |

### Pushing safely

```bash
git_push() {   # message
  [ "$PUSH" = "1" ] || return 0
  ( flock 9
    git add -f "$RESULTS"
    git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" -c commit.gpgsign=false commit -q -m "$1" || exit 0
    for i in 1 2 3 4; do git pull -q --rebase origin HEAD && git push -q origin HEAD && exit 0; sleep $((10 * i)); done
    echo "   (push failed: results stay in $RESULTS)" >&2
  ) 9> "$ROOT_RUNS/.git.lock"
}
```

- Results are **copied** from the run folder (`runs/`, git-ignored) into `results/<job>/` and pushed from there.
- Only `results/<job>/` is added, never `git add -A`, so a stray `.env` can't be committed.

## 5. Tracing: everything, pushed

The coding agent must be able to analyse a run as if it had watched it. A run records everything, in its run folder,
as it happens:

| File | Contents |
|---|---|
| `trace.jsonl` | **every model call:** role, model, effort, max_tokens, the **full prompt** (system and user), the **full response** (and the reasoning text, if any), token usage, latency, retries and errors, and a timestamp. One JSON object per line, appended and flushed per call |
| `programs.jsonl` | every program written: id, parent(s), generation, role, the full code, its evaluation (score, validity, metrics, CPU time, errors) |
| `history.jsonl` | one line per generation: best, records, timings, what each slot did |
| `state.json` | everything needed to resume (written atomically) |
| `summary.json` | the final numbers |
| `run.log` | the human-readable log |
| `env.json` | written at start: git commit, settings, Python and package versions, machine (cores, RAM, disk) |

- **Pushed:** every file above. Big, growing files (the trace, programs) are pushed as **gzipped chunks of 10
  generations** (`trace/gens_0001-0010.jsonl.gz`, ...). A finished chunk is written once and never changes, and gzip
  is run deterministically (`mtime=0`), so each push adds only what is new. Re-committing one ever-growing file every
  40 minutes would fill the repo, and the VM's disk, with copies. Never truncate a trace.
- **Private problems** (real data) are the exception: their runs are never pushed. Only normalised, name-free numbers
  may leave the machine.
- **Resuming** keeps appending to the same files. Every line carries its generation, so a resumed run reads as one
  run.

## 6. Luminal from a job

Full reference: Shreyas's private Luminal guide (it holds keys, so it's never committed). The essentials:

- **API:** OpenAI-compatible, `https://flash.luminal.cloud/v1`. Model `deepseek-ai/DeepSeek-V4.1-Flash`; 163,840-token
  context (declare it yourself).
- **Keys:** read from `.env` (`LUMINAL_API_KEY`, or a pool in `LUMINAL_API_KEYS`). Never hard-code, log or commit a key.
  Traces record which key *index* was used, never the key.
- **Always send `reasoning_effort`** (`none`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`). Left out, hidden
  thinking eats the output and answers come back empty or cut off. Use `none` for mechanical work and `low` or above
  for reasoning.
- **Always send `max_tokens`.** Without it there's a silent 8,192 cap. With thinking on, add about 24,000 for the
  thinking.
- **Stream** anything non-trivial and assemble the answer yourself. Long non-streamed answers get cut off.
- **Rate limits, per key:** about 13 requests may *start* at the same instant, and a bucket of about 60 refills at about
  1 per second (about 60 a minute sustained). Calls in flight and prompt size aren't limited. Stay at **8 or fewer
  concurrent starts per key** and **1 or fewer new calls per second on average**. Use several keys for more throughput,
  and remember other agents may share them.
- **Retry** 429, 503, socket errors, mid-stream errors and empty bodies: about 4 tries with backoff (2, 4, 8 s plus
  jitter), honouring `Retry-After`. Don't retry 400 or 422 (fix the request) or 401 (the key).
- **Forced tool calls only with thinking off.** With thinking on, use `tool_choice: "auto"`. `json_schema` output isn't
  available; `json_object` and tool calls work.
- **Cost:** prepaid wallet, `GET /v1/balance`, which settles late. Log the balance at the start and end of a job.
- **In the preflight:** one tiny call (`effort="none"`, `max_tokens` 20) proves the key, the network and the model
  before hours are committed.

## 7. Handing a job to Aether: the prompt

Every job comes with a prompt Shreyas pastes to Aether as is. The prompt is a procedure, not a discussion:

1. **One line on the goal**, and "don't change any code or settings; just start it".
2. **Where to work** (absolute paths), and `git pull` there. Check that the named inputs exist (exact paths) and
   **don't change them**.
3. **Uploaded files:** where to put them, how to extract them (Python, not `unzip`), and what must never be committed.
4. **The start command, exactly**, as one line with every variable, launched with
   `setsid nohup … > LOG 2>&1 < /dev/null &`.
5. **"Don't change any setting"**, with the reason (shared machine, sized for it).
6. **The one check:** wait N minutes, read the last 20 lines of the named logs **once**, and list the exact lines that
   mean it started well (quoted, in order) and the prefixes that mean it stopped (`preflight:`, `Traceback`, …).
7. **Report** what was seen, quoting the lines verbatim, plus `free -m`, `df -h /`, and the job's PID with
   `ps -o pid,sid,ppid,etime,cmd`.
8. **Stop.** "Don't stop, restart or kill any process. Don't set up cron jobs, scheduled check-ins or reminders: I
   check in myself."

### Template

> Start my <job> on this machine and report back. Don't change any code or settings; just start it.
>
> 1. Work in <REPO>. Run `git pull` there. Check that <script> exists and that <input paths> exist. Don't change
>    anything in <input paths>.
> 2. <If a file was uploaded: put it at <path> and extract it with
>    `python3 -c "import zipfile; zipfile.ZipFile('<zip>').extractall('.')"`. Never commit or push anything from
>    <private paths>.>
> 3. Start the job in the background, exactly like this, from <REPO> (one command):
>    `cd <REPO> && <VAR=…> setsid nohup bash <script> > <log> 2>&1 < /dev/null &`
> 4. Don't change any setting: other agents share this machine, and the job is sized for it.
> 5. Wait about <N> minutes, then read the last 20 lines of <log> and <run log> once. A good start shows, in order:
>    "<line 1>", "<line 2>", "<line 3>". A line starting with "preflight:" or a Traceback means the job stopped:
>    report those lines exactly, and don't edit anything to fix it.
> 6. Report what you saw (quote the lines), the output of `free -m` and `df -h /`, and
>    `ps -o pid,sid,ppid,etime,cmd -p <pid>` for the job.
> 7. Then stop. Don't stop, restart or kill any process. Don't set up cron jobs, scheduled check-ins or reminders:
>    I check in myself.

**Finding the job's process:** `setsid` forks, so `$!` after the start command is *not* the job. Find it by its
snapshot's name, e.g. `pgrep -fa <job>_snapshot`, and report it with `ps -o pid,sid,ppid,etime,cmd -p <pid>`.

**Stopping a job on purpose** (only on Shreyas's explicit order): `kill -TERM <the job's pid>`, the job's bash process,
not its Python run. Then wait for the job's log to end with "all jobs done" (up to the grace period plus a push). Never
`kill -9`.

**Status checks later** (when Shreyas asks Aether "how is it going?"): read the latest `== HH:MM progress:` line and
the run log's last generation line, report them verbatim, and say whether the process is alive (`ps`). Nothing else.

**Collecting results:** a pushed job needs nothing; the coding agent pulls `results/<job>/`. For a private job, Aether
packs the named folder into a tarball and Shreyas downloads it whole (attach it only once the download has finished).

## 8. Checklist before handing a job over

- [ ] `FAKE=1 PUSH=0` with tiny settings runs the whole job end to end, including every interruption in section 4b
      (stop signal, restart, `kill -9` of the run, torn line, grace running out) and the final report.
- [ ] The job and its results go to the right repo (private work never to helix_evolve).
- [ ] A second start exits at once with "already running".
- [ ] The preflight fails cleanly on a missing package, a missing input and low disk.
- [ ] The estimated peak RAM, CPU processes, disk output and wall time are in the header, and fit section 3.
- [ ] The trace holds full prompts and responses; the results folder holds everything in section 5.
- [ ] Nothing private or secret can be added by the push.
- [ ] The Aether prompt quotes the exact success lines this version of the job prints.
