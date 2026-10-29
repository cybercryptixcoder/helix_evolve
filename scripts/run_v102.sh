#!/usr/bin/env bash
# The Helix v10.2 jobs (docs/V102_DESIGN.md, docs/V10_JOB.md "v10.2"): Helix from Code Zero on the second
# autocorrelation inequality, with the field's ideas (the deep research, helix10/sota.py) as axes of its search space.
# Two seeds side by side, sharing the machine's 2 evaluation slots:
#   ARM=helix SEED=1 / SEED=2   v102-helix / v102-helix-s2: the field's 9 decisions and 38 options on the design map and
#                 its 15 findings in the Atlas; every new exploration (an option of the field, a new design from the
#                 map) is built from nothing on its own track and judged on its own climb, never against the record; the
#                 wide loop works the explorations' own lines; the invariant audit every 10 generations;
#   ARM=field     (optional) a reference: the world's best program (ClaudeExplorer's iterated Dinkelbach and velocity
#                 cycles) from nothing, chained, at the same limit, using at most half of seed 1's CPU (compared at
#                 equal CPU).
# The constraint (docs/V102_DESIGN.md): as the published systems it is compared with: at most CAP = 50,000 steps
# (AlphaEvolve V2's construction), BUDGET = 150 CPU seconds per program (TTT-Discover and OpenEvolve: 10 minutes;
# ThetaEvolve: 350 s), from scratch (Code Zero), 3 + 3 programs a generation (about 1,000 programs in all; theirs:
# 25,600 to 51,200). The report: results/v102/COMPARISON.md (helix10/compare.py: the climb, the cost, where each record came
# from: which of the field's options, built from nothing, took it).
#
#   cd /home/ubuntu/helix_v5_run && git pull && ARM=helix SEED=1 setsid nohup bash scripts/run_v102.sh > v102_s1.log 2>&1 < /dev/null &
#   ARM=helix SEED=2 setsid nohup bash scripts/run_v102.sh > v102_s2.log 2>&1 < /dev/null &
#
# The stages (each done once; a restart skips what is done):
#   0. the pause (Shreyas's order of October 29, 01:56: v10.1 stops, v10.2 replaces it): the v10.1 jobs this one
#      replaces (seed 1 -> v101-axes and v101-field, seed 2 -> v101-warm), each, if it is running, gets one stop
#      signal; it finishes the generation in progress, publishes and pushes everything and exits; this job waits for
#      its lock, however long that takes. If it isn't running, nothing happens. Nothing else is ever stopped;
#   1. preflight: packages, disk, a crash test with a fake model (the run, the reference, the reports), a real model
#      call, GitHub;
#   2. the run (from Code Zero), up to GENS generations or the deadline; progress every 10 minutes, a push every 40;
#   3. the end: the comparison, the verification of every best construction, a push.
#
# Robust by design (docs/AETHER.md, sections 4 and 4b): one copy per NAME (a lock); runs from a snapshot of itself;
# started again after any stop it resumes from the last finished generation; a stop signal finishes the generation in
# progress and pushes; retries on errors; installs no cron job or timer; waits while disk or model are down.
#
# Estimated: about 20-30 minutes a generation per run while both seeds run (6 programs of 150 s each, two slots
# shared), so about 150-200 generations each in 80 hours. Memory about 3 GB in all. Disk: under 500 MB per run.
# Model: about 25 calls a generation per run (reported).
#
# Settings: ARM [required]  SEED [1]  NAME [v102-$ARM, -s$SEED for another seed]  BUDGET [150]  CAP [50000]
#   GENS [400]  HOURS [80]  PATIENCE [10] (ARM=field)  SHARE [0.5] (ARM=field)  EVAL_SLOTS [2]  MIN_FREE_MB [1500]
#   START_DISK_MB [2000]  MIN_DISK_MB_RUN [1200]  STOP_GRACE_S [1800]  MAX_RETRIES [3]  PUSH [1]  FAKE [0]  TICK [600]
#   PUSH_EVERY [4]  PAUSE_V101 [1]
#
#   FAKE=1 PUSH=0 ARM=helix GENS=2 BUDGET=4 bash scripts/run_v102.sh        # the whole job with a fake model (a test)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 3
ARM="${ARM:-}"
SEED="${SEED:-1}"
# run from a snapshot: a `git pull` that changes this file mid-job must not change what the running job does
if [ -z "${V102_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" "runs/.v102_job_snapshot_${ARM:-x}_$SEED.sh.$$" \
    && mv -f "runs/.v102_job_snapshot_${ARM:-x}_$SEED.sh.$$" "runs/.v102_job_snapshot_${ARM:-x}_$SEED.sh" \
    && V102_SNAPSHOT=1 exec bash "runs/.v102_job_snapshot_${ARM:-x}_$SEED.sh" "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
case "$ARM" in helix|field) ;; *) echo "ARM must be helix or field (ARM=helix SEED=1 bash scripts/run_v102.sh)" >&2; exit 3 ;; esac
ROOT_RUNS="${ROOT_RUNS:-runs/v102}"
RESULTS="${RESULTS:-results/v102}"
SUFFIX=""; [ "$SEED" != "1" ] && SUFFIX="-s$SEED"
NAME="${NAME:-v102-$ARM$SUFFIX}"
BUDGET="${BUDGET:-150}"
CAP="${CAP:-50000}"
GENS="${GENS:-400}"
HOURS="${HOURS:-80}"
PATIENCE="${PATIENCE:-10}"
SHARE="${SHARE:-0.5}"
RESET_DEADLINE="${RESET_DEADLINE:-0}"
V101_ROOT="${V101_ROOT:-runs/v101}"
PAUSE_V101="${PAUSE_V101:-1}"
PAIRS="axes field"; [ "$SEED" = "2" ] && PAIRS="warm"     # the v10.1 jobs this one replaces
[ "$ARM" = "field" ] && PAIRS="field"
case "$SEED" in 1|2) ;; *) PAUSE_V101=0 ;; esac
MIN_FREE_MB="${MIN_FREE_MB:-1500}"
START_DISK_MB="${START_DISK_MB:-2000}"
MAX_RETRIES="${MAX_RETRIES:-3}"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"
TICK="${TICK:-600}"
PUSH_EVERY="${PUSH_EVERY:-4}"
export STOP_GRACE_S="${STOP_GRACE_S:-1800}"
export MIN_DISK_MB="${MIN_DISK_MB_RUN:-1200}"     # what the run itself waits for between generations
export HELIX4_EVAL_SLOTS="${EVAL_SLOTS:-2}"
export HELIX4_SLOTS_DIR="${HELIX4_SLOTS_DIR:-$(pwd)/runs/v4/.slots}"   # helix4's default: shared machine-wide
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"
NICE_CMD="nice -n 10"
command -v ionice >/dev/null && NICE_CMD="ionice -c 3 nice -n 10"
FAKE_FLAG=""; [ "$FAKE" = "1" ] && FAKE_FLAG="--fake"
mkdir -p "$ROOT_RUNS" "$HELIX4_SLOTS_DIR" "$RESULTS"
if command -v flock >/dev/null; then
  exec 8> "$ROOT_RUNS/.$NAME.lock"
  flock -n 8 || { echo "== this job is already running (another copy holds $ROOT_RUNS/.$NAME.lock); this copy exits and changes nothing"; exit 0; }
fi
DIR="$ROOT_RUNS/$NAME"
LOG="$ROOT_RUNS/$NAME.log"
HELIX_DIR="$ROOT_RUNS/v102-helix"                  # the reference is matched to seed 1

echo "== Helix v10.2 job ($ARM, seed $SEED): $NAME, from Code Zero, n <= $CAP, $BUDGET s per program, $HELIX4_EVAL_SLOTS evaluation slots shared machine-wide"
echo "   started $(date '+%Y-%m-%d %H:%M:%S %Z'); repo $(pwd) ($(git rev-parse --abbrev-ref HEAD 2>/dev/null) $(git rev-parse --short HEAD 2>/dev/null))"

# ------------------------------------------------------------------ stop signals: passed to the child, then everything is pushed
CHILD=""
STOPPING=0
nap() { sleep "$1" & wait $! 2>/dev/null; }          # a sleep a stop signal interrupts
on_stop() {
  [ "$STOPPING" = "1" ] && { [ -n "$CHILD" ] && kill -TERM "$CHILD" 2>/dev/null; return; }
  STOPPING=1
  echo "== stop requested: the step in progress finishes (a generation: up to ${STOP_GRACE_S} s), then everything is pushed"
  [ -n "$CHILD" ] && kill -TERM "$CHILD" 2>/dev/null
}
trap on_stop TERM INT HUP
run_child() {   # log-file command...: runs a step in the background so a stop signal reaches it; returns its exit code
  local log="$1"; shift
  "$@" >> "$log" 2>&1 &
  CHILD=$!
  local rc=""
  while kill -0 "$CHILD" 2>/dev/null; do wait "$CHILD"; rc=$?; done   # `wait` returns early when a signal arrives
  if [ -z "$rc" ] || [ "$rc" -gt 128 ]; then wait "$CHILD" 2>/dev/null; local r2=$?; [ "$r2" != "127" ] && rc=$r2; fi
  CHILD=""
  return "${rc:-0}"
}

# ------------------------------------------------------------------ 0. the pause of the v10.1 job this arm replaces
# Shreyas's order (October 29, 01:56): v10.1 is replaced by v10.2. One stop signal to the v10.1 job script of the paired
# mode (never to anything else); it finishes the generation in progress, runs its end stage (publish, report,
# verification, its pack and constructions to GitHub) and exits; this job waits for its lock.
v101_main_pid() {   # the v10.1 job script of mode $1 (not its own ticker subshell)
  for p in $(pgrep -f "runs/[.]v101_job_snapshot_$1[.]sh" 2>/dev/null); do
    pp=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
    grep -q "v101_job_snapshot_$1" "/proc/$pp/cmdline" 2>/dev/null || echo "$p"
  done | head -1
}
for PAIR in $PAIRS; do
  [ "$PAUSE_V101" = "1" ] && [ -f "$V101_ROOT/.v101-$PAIR.lock" ] && command -v flock >/dev/null || continue
  if flock -n "$V101_ROOT/.v101-$PAIR.lock" true 2>/dev/null; then
    echo "== v101-$PAIR isn't running: nothing to pause"
    continue
  fi
  pid="$(v101_main_pid "$PAIR")"
  if [ -n "$pid" ]; then
    echo "== pausing v101-$PAIR (Shreyas's order: v10.2 replaces v10.1): one stop signal to its job ($pid); it finishes its step, pushes and exits"
    kill -TERM "$pid" 2>/dev/null
  else
    echo "== v101-$PAIR's lock is held but its job script wasn't found: waiting for the lock to be released"
  fi
  t0=$(date +%s); said_w=""
  while ! flock -n "$V101_ROOT/.v101-$PAIR.lock" true 2>/dev/null; do
    [ "$STOPPING" = "1" ] && { echo "== stopped while waiting for v101-$PAIR; run this script again to continue"; exit 0; }
    w=$(( ($(date +%s) - t0) / 60 ))
    [ $((w % 10)) -eq 0 ] && [ "$w" != "$said_w" ] && { echo "   (waiting for v101-$PAIR to finish and push: $w min so far)"; said_w=$w; }
    nap 20
  done
  echo "   v101-$PAIR has stopped after $(( ($(date +%s) - t0) / 60 )) min (it can be continued later: MODE=$PAIR bash scripts/run_v101.sh)"
done

# ------------------------------------------------------------------ 1. preflight (about 2 minutes)
echo "== preflight"
"$PY" -c "import sys, numpy, scipy; assert sys.version_info >= (3, 10); print('   python', sys.version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "preflight: Python 3.10+ with numpy and scipy is needed: pip install -r helix5/requirements.txt" >&2; exit 3; }
free_disk=$(df -Pm . | awk 'NR==2 {print $4}')
echo "   disk: ${free_disk} MB free (need $START_DISK_MB to start)"
[ "${free_disk:-0}" -ge "$START_DISK_MB" ] || { echo "preflight: only ${free_disk} MB of disk free; need $START_DISK_MB MB. Nothing was started." >&2; exit 3; }
PRE="$(mktemp -d)"
( export HELIX4_SLOTS_DIR="$PRE/slots" HELIX4_DEADLINE=0
  "$PY" -m helix10.job --out "$PRE/v102/v102-helix" --gens 2 --budget 2 --cold --fake \
  && "$PY" -m helix10.baseline --out "$PRE/v102/v102-field" --scratch "$PRE/v102/v102-helix" --budget 2 --patience 1 --hours 0.01 \
  && "$PY" -m helix10.compare "$PRE/v102" --out "$PRE/r/COMPARISON.md" \
  && "$PY" -m helix9.report "$PRE/v102" --out "$PRE/r/REPORT.md" \
  && "$PY" -m helix9.publish --run "$PRE/v102/v102-helix" --out "$PRE/r/v102-helix" --full \
  && "$PY" -c "import tools.verify_ac2" ) > "$PRE/v102.log" 2>&1 \
  || { echo "preflight: the crash test (2 generations with a fake model; the reference; the reports) failed:" >&2; tail -20 "$PRE/v102.log" >&2; rm -rf "$PRE"; exit 3; }
echo "   crash test passed (2 generations with a fake model, the reference stream, the report, publish)"
rm -rf "$PRE"
if [ "$FAKE" != "1" ]; then
  "$PY" - <<'PY' || { echo "preflight: the model can't be reached (is .env in the repo root with LUMINAL_API_KEYS=...?)" >&2; exit 3; }
from helix4.llm import LLM
r = LLM().chat("preflight", "You answer in one word.", "Say OK.", max_tokens=20, effort="none", tries=3)
print("   model answers:", r.text.strip()[:20], f"({r.seconds:.1f} s)")
PY
fi
if [ "$PUSH" = "1" ]; then
  git push --dry-run -q origin HEAD >/dev/null 2>&1 \
    || { echo "preflight: can't push to GitHub (check that the repo's branch tracks origin and access works)" >&2; exit 3; }
  echo "   GitHub: can push"
fi

# ------------------------------------------------------------------ publishing
git_push() {   # message paths...
  [ "$PUSH" = "1" ] || return 0
  local msg="$1"; shift
  ( command -v flock >/dev/null && flock 9
    git add -f "$@" 2>/dev/null
    git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" -c commit.gpgsign=false commit -q -m "$msg" || exit 0
    for i in 1 2 3 4; do git pull -q --rebase --autostash origin HEAD && git push -q origin HEAD && exit 0; sleep $((15 * i)); done
    echo "   (push failed: results stay in $RESULTS and $ROOT_RUNS; the next push sends them)" >&2
  ) 9> "runs/.git.lock"
}
compare() {
  "$PY" -m helix10.compare "$ROOT_RUNS" --out "$RESULTS/COMPARISON.md" > /dev/null 2>&1 || echo "   (the comparison failed; the run data are fine)"
}
publish() {   # message [full]
  if [ "$ARM" = "field" ]; then
    mkdir -p "$RESULTS/$NAME/streams"
    cp -f "$DIR/field.jsonl" "$RESULTS/$NAME/" 2>/dev/null
    cp -f "$DIR"/streams/*.json "$DIR"/streams/*.npy "$RESULTS/$NAME/streams/" 2>/dev/null
    cp -f "$LOG" "$RESULTS/$NAME/run.log" 2>/dev/null
  elif [ -f "$DIR/state.json" ]; then
    "$PY" -m helix9.publish --run "$DIR" --out "$RESULTS/$NAME" --log "$LOG" $([ "${2:-}" = "full" ] && echo --full) 2>&1 | tail -2 \
      || echo "   (publishing failed; the run is fine)"
    { "$PY" -m helix9.report "$ROOT_RUNS" --out "$RESULTS/REPORT.md" > /dev/null 2>&1 || echo "   (the report failed; the run data are fine)"; }
  fi
  compare
  git_push "$1" "$RESULTS"
}

# every start is recorded: commit, settings, machine
"$PY" - "$RESULTS/sessions.jsonl" "$NAME" "$ARM" "$SEED" "$BUDGET" "$GENS" "$HOURS" "$FAKE" <<'PY' || true
import json, os, platform, shutil, subprocess, sys, time
f, name, arm, seed, budget, gens, hours, fake = sys.argv[1:]
def sh(*c):
    try:
        return subprocess.run(c, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None
mem = next((l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal")), None) if os.path.exists("/proc/meminfo") else None
row = {"t": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "name": name, "arm": arm, "seed": int(seed), "budget": float(budget),
       "gens": int(gens), "hours": float(hours), "fake": fake == "1", "commit": sh("git", "rev-parse", "HEAD"),
       "python": platform.python_version(), "machine": platform.machine(), "cpus": os.cpu_count(),
       "mem_total_mb": int(mem) // 1024 if mem else None, "disk_free_mb": shutil.disk_usage(".").free >> 20,
       "eval_slots": os.environ.get("HELIX4_EVAL_SLOTS")}
with open(f, "a") as fh:
    fh.write(json.dumps(row) + "\n")
PY

# ------------------------------------------------------------------ the deadline: fixed at the first start, kept across restarts
if [ ! -f "$ROOT_RUNS/$NAME.deadline" ] || [ "$RESET_DEADLINE" = "1" ]; then
  "$PY" -c "import time; print(int(time.time() + float('$HOURS') * 3600))" > "$ROOT_RUNS/$NAME.deadline"
fi
export HELIX4_DEADLINE="$(cat "$ROOT_RUNS/$NAME.deadline")"
echo "   deadline: $(date -d "@$HELIX4_DEADLINE" '+%Y-%m-%d %H:%M %Z' 2>/dev/null || echo "$HELIX4_DEADLINE") (the run stops after the generation in progress then; RESET_DEADLINE=1 HOURS=n sets a new one)"
if [ -f "$DIR/state.json" ]; then
  done_now=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['gen_done'])" "$DIR/state.json")
  echo "== $NAME already has $done_now finished generations: pushing them first, then resuming"
  publish "Helix v10.2 job ($NAME): catch-up push at a restart"
fi

status() {
  "$PY" - "$DIR" "$ARM" <<'PY'
import json, sys, time
from pathlib import Path
d, arm = Path(sys.argv[1]), sys.argv[2]
def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
if arm == "field":
    rows = jl(d / "field.jsonl")
    if rows:
        r = rows[-1]
        print(time.strftime("== %H:%M progress: ") + f"field round {r['round']}: best {r['best']:.9f}, {r['cpu_total'] / 3600:.2f} CPU h", flush=True)
    else:
        print(time.strftime("== %H:%M progress: ") + "waiting for v102-helix to start", flush=True)
    raise SystemExit
h = jl(d / "history.jsonl")
if not h:
    print(time.strftime("== %H:%M progress: ") + "starting", flush=True)
    raise SystemExit
last = h[-1]
extra = ""
if "map" in last:
    m = last.get("map") or {}
    extra = f", map {m.get('axes', '-')} decisions, {len(m.get('racing') or [])} racing"
print(time.strftime("== %H:%M progress: ") + f"{d.name} g{last['gen']} {last['best']:.9f} "
      f"({sum(1 for x in h if x.get('new_best'))} records){extra}, last generation {last.get('seconds', 0) / 60:.1f} min", flush=True)
PY
}

( SL=""; trap 'kill ${SL:-} 2>/dev/null; exit 0' TERM INT HUP
  n=0
  while true; do sleep "$TICK" & SL=$!; wait $SL; status; n=$((n + 1))
    [ $((n % PUSH_EVERY)) -eq 0 ] && publish "Helix v10.2 job ($NAME): progress at $(date -u +%H:%M) UTC"
  done
) &
TICKER=$!
trap 'kill $TICKER 2>/dev/null' EXIT

# ------------------------------------------------------------------ 2. the run
while [ -r /proc/meminfo ] && [ "$STOPPING" = "0" ]; do
  free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  [ "${free:-0}" -ge "$MIN_FREE_MB" ] && break
  echo "   ($NAME waiting: ${free} MB of memory available, need $MIN_FREE_MB)"; nap 120
done
attempt=0
while [ "$STOPPING" = "0" ]; do
  echo "== $NAME: running (log: $LOG)"
  case "$ARM" in
    helix)    run_child "$LOG" $NICE_CMD "$PY" -m helix10.job --out "$DIR" --gens "$GENS" --seed "$SEED" --budget "$BUDGET" --cold --cap "$CAP" $FAKE_FLAG ;;
    field)    run_child "$LOG" $NICE_CMD "$PY" -m helix10.baseline --out "$DIR" --scratch "$HELIX_DIR" --budget "$BUDGET" --cap "$CAP" \
                  --patience "$PATIENCE" --share "$SHARE" --hours "$HOURS" ;;
  esac
  rc=$?
  case "$rc" in
    0) break ;;                                        # finished, or stopped at the deadline
    75) echo "== $NAME: stopped cleanly on a stop signal"; break ;;
    *) attempt=$((attempt + 1))
       echo "== $NAME: stopped on an error (exit $rc); the last lines of its log:"; tail -5 "$LOG" | sed 's/^/   /'
       [ "$STOPPING" = "1" ] && break
       if [ "$attempt" -gt "$MAX_RETRIES" ]; then
         echo "== $NAME: stopped after $MAX_RETRIES retries; run this script again to continue it"; break
       fi
       echo "   retry $attempt of $MAX_RETRIES in 60 s (it resumes from the last finished generation)"
       nap 60 ;;
  esac
done
kill $TICKER 2>/dev/null
wait $TICKER 2>/dev/null                                 # lets a push in progress finish first
status

# ------------------------------------------------------------------ 3. the end: comparison, verification, push
verify() {
  "$PY" - "$RESULTS" "$RESULTS/VERIFICATION.md" <<'PY' || echo "   (verification failed to run)" >&2
import sys
from pathlib import Path
import numpy as np
from tools.verify_ac2 import verify, ALPHAEVOLVE_MAY_2025
root, out = Path(sys.argv[1]), Path(sys.argv[2])
REC = 0.961021              # the best published construction with n <= 50,000 (AlphaEvolve V2, Nov 2025)
rows = [verify(ALPHAEVOLVE_MAY_2025, "AlphaEvolve, May 2025 (DeepMind's published 50-step construction)")]
for f in sorted(root.glob("*/best.npy")):
    rows.append(verify(np.load(f), f.parent.name, max_n=200_000))
lines = ["# Verification of the Helix v10.2 jobs' constructions", "",
         "Every best construction re-scored independently (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own "
         "verification code (ported line by line), EinsteinArena's verifier (as its API publishes it) and exact "
         "rational arithmetic. Digits are truncated, not rounded. The best published value with n <= 50,000 steps is "
         f"{REC} (AlphaEvolve V2); the published LLM-driven systems' values: results/v102/COMPARISON.md.", "",
         "| Construction | Steps | Helix | DeepMind's code | Arena's code | Exact | All agree | Against AlphaEvolve V2 |",
         "|---|---|---|---|---|---|---|---|"]
for r in rows:
    if not r.get("valid"):
        lines.append(f"| {r['label']} | - | INVALID: {r.get('problem')} | | | | | |")
        continue
    d = r["arena_code"] - REC
    lines.append(f"| {r['label']} | {r['N']} | {r['helix']:.12f} | {r['deepmind_code']:.12f} | {r['arena_code']:.12f} | "
                 f"{r.get('exact_str', '-')} | {r['agree']} | {d:+.3e} |")
out.write_text("\n".join(lines) + "\n")
print("\n".join("   " + l for l in lines[4:]))
PY
}
publish "Helix v10.2 job ($NAME): $( [ "$STOPPING" = "1" ] && echo stopped || echo finished ); results and the comparison" full
if [ "$ARM" != "field" ]; then
  echo "== verifying the best constructions"
  verify
  git_push "Helix v10.2 job ($NAME): verification" "$RESULTS"
fi
echo "== the comparison: $RESULTS/COMPARISON.md"
sed 's/^/   /' "$RESULTS/COMPARISON.md" 2>/dev/null | head -40
echo "== all jobs done ($NAME)"
