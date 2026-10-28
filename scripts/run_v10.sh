#!/usr/bin/env bash
# The Helix v10 job on the second autocorrelation inequality (docs/V10_JOB.md): one v10 run, continuing the v9 run
# v9-s1 (record 0.9414417, generation 800) with the field's knowledge (docs/AC2_SOTA.md, helix10/sota.py), in one of
# two modes:
#   MODE=axes  the field's design decisions on the map (exploration biased towards them) and its findings in the Atlas;
#              no construction and no program of the field;
#   MODE=warm  the same, plus the field's constructions (the arena record 0.963588 and 13 others, verified) and the
#              field's methods (helix10/programs/) as starting points.
# The two are meant to run side by side, sharing the machine's 2 evaluation slots:
#
#   cd /home/ubuntu/helix_v5_run && git pull && MODE=warm setsid nohup bash scripts/run_v10.sh > v10_warm.log 2>&1 < /dev/null &
#   cd /home/ubuntu/helix_v5_run && MODE=axes setsid nohup bash scripts/run_v10.sh > v10_axes.log 2>&1 < /dev/null &
#
# The stages (each done once; a restart skips what is done):
#   1. preflight (about 2 minutes): packages, disk, a crash test of the whole pipeline with a fake model, one real
#      model call, GitHub push access;
#   2. the source: results/v9warm/v9-s1 as pulled from GitHub, its continuation pack, and every construction of it
#      (the local folders, or the GitHub releases when they are missing here);
#   3. MODE=warm: the field's constructions from data/field_ac2 (in the repo), each verified by SHA-256 and re-scored;
#   4. the warm start (helix10/warm.py) into runs/v10/$NAME; MODE=warm also runs the field's three methods once
#      (3 x BUDGET s of CPU);
#   5. the run (helix10/job.py) for ADD generations. Progress every 10 minutes, a push every 40 minutes;
#   6. at the end: the report, the verification of the record, the run's own continuation pack, pushed, and the run's
#      constructions as a GitHub release built on the source's.
#
# Robust by design (docs/AETHER.md, sections 4 and 4b):
# - One copy per NAME at a time (a lock); a second start of the same NAME prints "already running" and exits 0.
# - Runs from a snapshot of itself, so a `git pull` mid-run can't change the running job.
# - Started again after any stop (a crash, a reboot, a stop signal, the deadline), it pushes what it has, then resumes
#   from the last finished generation: only the generation in progress is lost and redone.
# - A stop signal (SIGTERM/SIGINT/SIGHUP) is passed to the step in progress: the run finishes the generation in
#   progress (up to STOP_GRACE_S), saves, and the job pushes everything before exiting. A second signal stops at once.
# - If the run stops on an error, the job retries it up to MAX_RETRIES times (60 s apart, resuming each time).
#   It never restarts anything else, never kills any process but its own steps, and installs no cron job or timer.
# - Before every generation the run checks the disk and the model; while either is down it waits.
# - It waits (never stops anything) while a Helix run of an earlier version (v4-v9) is running. The two v10 runs
#   don't wait for each other: they share the machine-wide evaluation slots (EVAL_SLOTS, 2).
#
# Estimated (measured live, see docs/V10_JOB.md): 15-25 minutes a generation for each run while both run, so 120
# generations take about 2 days (deadline 60 h). Peak memory about 5 GB for the two (each program up to MEM_MB, two at
# a time machine-wide, plus each run's own process, about 1 GB). Disk: about 1.5 GB per run at most (large
# constructions handed back unchanged are kept as references; those nothing needs are removed after 3 generations);
# refuses to start below 4 GB free. Model: about 15-20 calls and 150k tokens in a generation per run.
#
# Settings (environment variables; defaults in brackets):
#   MODE [axes|warm, required]  NAME [v10-$MODE]  SEED [1]  BUDGET [150] (CPU s per program)  ADD [120] (or GENS)
#   HOURS [60] (deadline after the first start)  RESET_DEADLINE [0]  SRC [results/v9warm/v9-s1]  PACK [$SRC/pack]
#   LOCAL_SEARCH [runs/v9warm/v9-s1/constructions,runs/v8warm/v8-s1/constructions]  EVAL_SLOTS [2]  MEM_MB [2000]
#   MIN_FREE_MB [1500]  START_DISK_MB [4000]  MIN_DISK_MB_RUN [1500]  STOP_GRACE_S [1200]  MAX_RETRIES [3]
#   MAX_WAIT_MIN [unset]  PUSH [1]  FAKE [0]  TICK [600]  PUSH_EVERY [4]
#
#   FAKE=1 PUSH=0 MODE=axes ADD=2 BUDGET=4 bash scripts/run_v10.sh        # the whole job with a fake model (a test)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 3
# run from a snapshot: a `git pull` that changes this file mid-job must not change what the running job does
if [ -z "${V10_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" runs/.v10_job_snapshot_${MODE:-x}.sh.$$ && mv -f runs/.v10_job_snapshot_${MODE:-x}.sh.$$ runs/.v10_job_snapshot_${MODE:-x}.sh \
    && V10_SNAPSHOT=1 exec bash runs/.v10_job_snapshot_${MODE:-x}.sh "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
MODE="${MODE:-}"
case "$MODE" in axes|warm) ;; *) echo "MODE must be axes or warm (MODE=axes bash scripts/run_v10.sh)" >&2; exit 3 ;; esac
ROOT_RUNS="${ROOT_RUNS:-runs/v10}"
RESULTS="${RESULTS:-results/v10}"
NAME="${NAME:-v10-$MODE}"
SEED="${SEED:-1}"
BUDGET="${BUDGET:-150}"
ADD="${ADD:-120}"
HOURS="${HOURS:-60}"
RESET_DEADLINE="${RESET_DEADLINE:-0}"
SRC="${SRC:-results/v9warm/v9-s1}"
PACK="${PACK:-$SRC/pack}"
PACK_MB="${PACK_MB:-80}"
LOCAL_SEARCH="${LOCAL_SEARCH:-runs/v9warm/v9-s1/constructions,runs/v8warm/v8-s1/constructions}"
FIELD_DIR="${FIELD_DIR:-runs/field}"
MEM_MB="${MEM_MB:-2000}"
MIN_FREE_MB="${MIN_FREE_MB:-1500}"
START_DISK_MB="${START_DISK_MB:-4000}"
MAX_RETRIES="${MAX_RETRIES:-3}"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"
TICK="${TICK:-600}"
PUSH_EVERY="${PUSH_EVERY:-4}"
export STOP_GRACE_S="${STOP_GRACE_S:-1200}"
export MIN_DISK_MB="${MIN_DISK_MB_RUN:-1500}"     # what the run itself waits for between generations
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

echo "== Helix v10 job (autocorrelation, mode $MODE, from $SRC): $NAME, $BUDGET s per program, $HELIX4_EVAL_SLOTS evaluation slots shared machine-wide"
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

# ------------------------------------------------------------------ 1. preflight (about 2 minutes)
echo "== preflight"
"$PY" -c "import sys, numpy, scipy; assert sys.version_info >= (3, 10); print('   python', sys.version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "preflight: Python 3.10+ with numpy and scipy is needed: pip install -r helix5/requirements.txt" >&2; exit 3; }
free_disk=$(df -Pm . | awk 'NR==2 {print $4}')
echo "   disk: ${free_disk} MB free (need $START_DISK_MB to start)"
[ "${free_disk:-0}" -ge "$START_DISK_MB" ] || { echo "preflight: only ${free_disk} MB of disk free; need $START_DISK_MB MB. Nothing was started." >&2; exit 3; }
PRE="$(mktemp -d)"
( export HELIX4_SLOTS_DIR="$PRE/slots" HELIX4_DEADLINE=0
  "$PY" -m helix10.job --out "$PRE/v10" --gens 2 --budget 2 --fake \
  && "$PY" -m helix9.report "$PRE/v10" --out "$PRE/r/REPORT.md" \
  && "$PY" -m helix9.publish --run "$PRE/v10" --out "$PRE/r/v10" --full \
  && "$PY" -m helix9.pack build --run "$PRE/v10" --search "$PRE/v10/constructions" --out "$PRE/r/pack" \
  && "$PY" -c "import helix10.warm, helix10.field, helix10.programs, tools.verify_ac2" ) > "$PRE/v10.log" 2>&1 \
  || { echo "preflight: the crash test (2 generations with a fake model, report, publish, pack) failed:" >&2; tail -20 "$PRE/v10.log" >&2; rm -rf "$PRE"; exit 3; }
echo "   crash test passed (v10: 2 generations with a fake model, report, publish, pack)"
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
  ) 9> "$ROOT_RUNS/.git.lock"
}
publish() {   # message [full]
  [ -f "$DIR/state.json" ] || return 0
  "$PY" -m helix9.publish --run "$DIR" --out "$RESULTS/$NAME" --log "$LOG" $([ "${2:-}" = "full" ] && echo --full) 2>&1 | tail -2 \
    || echo "   (publishing failed; the run is fine)"
  "$PY" -m helix9.report "$ROOT_RUNS" --out "$RESULTS/REPORT.md" > /dev/null 2>&1 || echo "   (the report failed; the run data are fine)"
  git_push "$1" "$RESULTS"
}

# every start is recorded: commit, settings, machine
"$PY" - "$RESULTS/sessions.jsonl" "$NAME" "$SEED" "$BUDGET" "$ADD" "$HOURS" "$FAKE" "$SRC" <<'PY' || true
import json, os, platform, shutil, subprocess, sys, time
f, name, seed, budget, add, hours, fake, src = sys.argv[1:]
def sh(*c):
    try:
        return subprocess.run(c, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None
mem = next((l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal")), None) if os.path.exists("/proc/meminfo") else None
row = {"t": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "name": name, "seed": int(seed), "budget": float(budget), "add": int(add),
       "hours": float(hours), "fake": fake == "1", "source": src, "commit": sh("git", "rev-parse", "HEAD"),
       "python": platform.python_version(), "machine": platform.machine(), "cpus": os.cpu_count(),
       "mem_total_mb": int(mem) // 1024 if mem else None, "disk_free_mb": shutil.disk_usage(".").free >> 20,
       "eval_slots": os.environ.get("HELIX4_EVAL_SLOTS")}
with open(f, "a") as fh:
    fh.write(json.dumps(row) + "\n")
PY

# local constructions (the earlier runs' own folders on this machine): used to build the pack, and by the run on demand
# for a base the pack doesn't hold (each verified before use; nothing is copied in bulk)
LOCAL_HAVE=""
IFS=',' read -ra dirs <<< "$LOCAL_SEARCH"
for d in "${dirs[@]}"; do [ -n "$d" ] && [ -d "$d" ] && LOCAL_HAVE="$LOCAL_HAVE${LOCAL_HAVE:+,}$(cd "$d" && pwd)"; done
# every construction on GitHub, as release files (helix9/vault.py). v9-s1's: the releases constructions-v8-s1 and
# constructions-v9-s1-g800 hold 3,848 of them; the 298 they lack exist only on this machine and go up once, as
# constructions-v9-s1 built on those two (docs/V9_RESULTS.md). On a machine without the local folders they come down
# from GitHub instead, so a continuation is lossless from GitHub alone. One job at a time does this (a lock).
SRC_TAG="${SRC_TAG:-constructions-$(basename "$SRC")}"
SRC_BASES="${SRC_BASES:-constructions-v8-s1,constructions-v9-s1-g800}"
(
  command -v flock >/dev/null && flock 7
  if [ -n "$LOCAL_HAVE" ] && [ "$PUSH" = "1" ] && [ "$STOPPING" = "0" ]; then
    if "$PY" -m helix9.vault exists --tag "$SRC_TAG" > /dev/null 2>&1; then
      echo "== every construction of $(basename "$SRC") is on GitHub already (release $SRC_TAG)"
    else
      echo "== the constructions of $(basename "$SRC") that GitHub lacks go up as release $SRC_TAG (built on $SRC_BASES; verified first)"
      $NICE_CMD "$PY" -m helix9.vault upload --run "$SRC" --folder "$LOCAL_HAVE" --tag "$SRC_TAG" --base "$SRC_BASES" >> "$LOG" 2>&1 \
        || echo "   (the upload failed; see $LOG. The constructions stay on this machine; the next start tries again)"
      grep -E "^vault:" "$LOG" | tail -1 | sed 's/^/   /'
    fi
  fi
) 7> "runs/.vault.lock"
if [ -z "$LOCAL_HAVE" ]; then
  for tag in "$SRC_TAG" ${SRC_BASES//,/ }; do
    if "$PY" -m helix9.vault exists --tag "$tag" > /dev/null 2>&1; then
      echo "== no local constructions: restoring every construction of $(basename "$SRC") from GitHub (release $tag and its bases)"
      ( command -v flock >/dev/null && flock 7
        "$PY" -m helix9.vault download --tag "$tag" --out "runs/vault/$(basename "$SRC")" 2>&1 | tail -1 | sed 's/^/   /'
      ) 7> "runs/.vault.lock"
      [ "$tag" = "$SRC_TAG" ] && break
    fi
  done
  [ -d "runs/vault/$(basename "$SRC")" ] && LOCAL_HAVE="$(cd "runs/vault/$(basename "$SRC")" && pwd)"
fi
export HELIX9_LOCAL_CONSTRUCTIONS="$LOCAL_HAVE"

if [ ! -f "$DIR/state.json" ]; then
  # ---------------------------------------------------------------- 2. the source
  [ -f "$SRC/state.json" ] || [ -f "$SRC/programs.jsonl" ] || [ -d "$SRC/programs" ] \
    || { echo "warm start: $SRC has no run (state.json, programs); did \`git pull\` run?" >&2; exit 3; }
  "$PY" - "$SRC" <<'PY' || { echo "warm start: $SRC can't be read" >&2; exit 3; }
import json, sys
from pathlib import Path
from helix9.pack import jl
src = Path(sys.argv[1])
s = json.loads((src / "state.json").read_text())
progs = jl(src / "programs.jsonl")
best = max((p for p in progs if p.get("valid") and p.get("score") is not None), key=lambda p: p["score"])
print(f"== the source: {src} ({s.get('version')}), generation {s['gen_done']}, {len(progs)} programs, record {best['score']:.9f} ({best['id']})")
PY
  # ---------------------------------------------------------------- 3. the continuation pack
  if [ ! -f "$PACK/manifest.json" ] && [ "$STOPPING" = "0" ]; then
    have="$LOCAL_HAVE"
    if [ -n "$have" ]; then
      echo "== the continuation pack: not on GitHub yet; building it from $have (each construction verified by re-scoring)"
      run_child "$LOG" $NICE_CMD "$PY" -m helix9.pack build --run "$SRC" --search "$have" --out "$PACK" --budget-mb "$PACK_MB"
      if [ -f "$PACK/manifest.json" ]; then
        grep -E "^pack:" "$LOG" | tail -1 | sed 's/^/   /'
        # the source's map, now by what its programs produce (the pack has every signature), for viz/mapview.html
        "$PY" -m helix9.mapview run "$SRC" --out "$SRC/mapview.json" > /dev/null 2>&1 || echo "   (the source's map view failed; the pack is fine)"
        git_push "Helix v10 job: the continuation pack of $(basename "$SRC") (constructions and signatures)" "$PACK" "$SRC/mapview.json"
      else
        [ "$STOPPING" = "1" ] && echo "   (the pack build was stopped: it is done again at the next start)" \
          || echo "   (the pack build failed; see $LOG. The run continues without it: only the record's construction is known, the others are rebuilt on demand)"
      fi
    else
      echo "== the continuation pack: not on GitHub, and no local constructions ($LOCAL_SEARCH): the run starts with the record's construction only; others are rebuilt on demand"
    fi
  elif [ -f "$PACK/manifest.json" ]; then
    echo "== the continuation pack: $PACK ($("$PY" -c "import json,sys; m=json.load(open(sys.argv[1])); print(len(m['packed']), 'constructions,', m['signatures'], 'signatures, built', m['built'])" "$PACK/manifest.json"))"
  fi
  # ---------------------------------------------------------------- 3. the field's constructions (MODE=warm)
  if [ "$MODE" = "warm" ]; then
    echo "== the field's constructions (data/field_ac2 in the repo): each checked by SHA-256 and re-scored"
    "$PY" -m helix10.field get --out "$FIELD_DIR" 2>&1 | tail -1 | sed 's/^/   /'
    [ -f "$FIELD_DIR/arena-2416.npy" ] || { echo "warm start: the field's record (arena-2416) isn't at hand; nothing was started" >&2; exit 3; }
  fi
  [ "$STOPPING" = "1" ] && { echo "== stopped before the warm start; run this script again to continue"; exit 0; }
  # ---------------------------------------------------------------- 4. the warm start
  echo "== the warm start ($MODE): $SRC -> $DIR$([ "$MODE" = "warm" ] && echo "; the field's three methods run once on its constructions (about $((3 * ${BUDGET%.*} / 60 + 1)) min)")"
  run_child "$LOG" $NICE_CMD "$PY" -m helix10.warm --src "$SRC" --out "$DIR" --mode "$MODE" --seed "$SEED" --budget "$BUDGET" \
      $([ -f "$PACK/manifest.json" ] && echo "--pack $PACK") $([ "$MODE" = "warm" ] && echo "--field $FIELD_DIR")
  grep -E "^(the field|field:|prepared|restored)" "$LOG" | tail -24 | sed 's/^/   /'
  [ -f "$DIR/state.json" ] || { echo "warm start: failed (see above); nothing was started" >&2; exit 3; }
else
  done_now=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['gen_done'])" "$DIR/state.json")
  echo "== $NAME already has $done_now finished generations: pushing them first, then resuming"
  publish "Helix v10 job ($NAME): catch-up push at a restart"
fi
FROM="$("$PY" -c "import json, sys; s = json.load(open(sys.argv[1])); print(s.get('warm_gen') if s.get('warm_gen') is not None else s['gen_done'])" "$DIR/state.json")"
GENS="${GENS:-$((FROM + ADD))}"
echo "   $NAME continues from generation $FROM to generation $GENS"
if [ -n "$LOCAL_HAVE" ]; then
  echo "   constructions the pack doesn't hold: taken from $LOCAL_HAVE when needed (verified), so nothing is lost"
else
  echo "   no local constructions: bases the pack doesn't hold are rebuilt when needed, and the wide loop samples the programs whose constructions are at hand"
fi

# ------------------------------------------------------------------ the deadline: fixed at the first start, kept across restarts
if [ ! -f "$ROOT_RUNS/$NAME.deadline" ] || [ "$RESET_DEADLINE" = "1" ]; then
  "$PY" -c "import time; print(int(time.time() + float('$HOURS') * 3600))" > "$ROOT_RUNS/$NAME.deadline"
fi
export HELIX4_DEADLINE="$(cat "$ROOT_RUNS/$NAME.deadline")"
echo "   deadline: $(date -d "@$HELIX4_DEADLINE" '+%Y-%m-%d %H:%M %Z' 2>/dev/null || echo "$HELIX4_DEADLINE") (the run stops after the generation in progress then; RESET_DEADLINE=1 HOURS=n sets a new one)"

# ------------------------------------------------------------------ never alongside another autocorrelation run (it waits; it never stops anything)
other_running() {
  pgrep -f "python[0-9.]*( +-[A-Za-z]+)* +-m +helix(4|5|6|47|7|8)\.run|python[0-9.]*( +-[A-Za-z]+)* +-m +helix9\.(run|job) " 2>/dev/null \
    | while read -r pid; do grep -qF -- "$DIR" "/proc/$pid/cmdline" 2>/dev/null || echo "$pid"; done | grep -q .
}
waited=0
while other_running && [ "$STOPPING" = "0" ]; do
  [ -n "${MAX_WAIT_MIN:-}" ] && [ "$waited" -ge "$MAX_WAIT_MIN" ] && { echo "   (another Helix run is still running after $waited minutes; starting anyway)"; break; }
  [ $((waited % 30)) -eq 0 ] && echo "   (waiting for another autocorrelation Helix run to finish before starting: $waited min so far)"
  nap 60; waited=$((waited + 1))
done

status() {
  "$PY" - "$DIR" <<'PY'
import json, sys, time
from pathlib import Path
from helix9.pack import jl
d = Path(sys.argv[1])
h = [x for x in jl(d / "history.jsonl") if "level" in x]
s = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else {}
w = s.get("warm_gen") or 0
mine = [x for x in h if x["gen"] > w]
if not mine:
    print(time.strftime("== %H:%M progress: ") + "starting", flush=True)
    raise SystemExit
last = mine[-1]
m = last.get("map") or {}
racing = len(m.get("racing") or [])
print(time.strftime("== %H:%M progress: ") + f"{d.name} g{last['gen']} {last['best']:.9f}, level {last['level']}, "
      f"{sum(1 for x in mine if x.get('new_best'))} records this run, map {m.get('axes', '-')} decisions / "
      f"{m.get('coords', '-')} placed, {racing} racing, last generation {last.get('seconds', 0) / 60:.1f} min", flush=True)
PY
}

( SL=""; trap 'kill ${SL:-} 2>/dev/null; exit 0' TERM INT HUP
  n=0
  while true; do sleep "$TICK" & SL=$!; wait $SL; status; n=$((n + 1))
    [ $((n % PUSH_EVERY)) -eq 0 ] && publish "Helix v10 job ($NAME): progress at $(date -u +%H:%M) UTC"
  done
) &
TICKER=$!
trap 'kill $TICKER 2>/dev/null' EXIT

# ------------------------------------------------------------------ 6. the run
while [ -r /proc/meminfo ] && [ "$STOPPING" = "0" ]; do
  free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  [ "${free:-0}" -ge "$MIN_FREE_MB" ] && break
  echo "   ($NAME waiting: ${free} MB of memory available, need $MIN_FREE_MB)"; nap 120
done
attempt=0
while [ "$STOPPING" = "0" ]; do
  echo "== $NAME: running (log: $LOG)"
  run_child "$LOG" $NICE_CMD "$PY" -m helix10.job --out "$DIR" --gens "$GENS" $FAKE_FLAG
  rc=$?
  case "$rc" in
    0) break ;;                                        # finished, or stopped at the deadline
    75) echo "== $NAME: the run stopped cleanly on a stop signal"; break ;;
    *) attempt=$((attempt + 1))
       echo "== $NAME: the run stopped on an error (exit $rc); the last lines of its log:"; tail -5 "$LOG" | sed 's/^/   /'
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
done_gens=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['gen_done'])" "$DIR/state.json" 2>/dev/null || echo 0)

# ------------------------------------------------------------------ 7. the end: report, verification, the run's own pack, push
verify() {
  "$PY" - "$RESULTS" "$RESULTS/VERIFICATION.md" <<'PY' || echo "   (verification failed to run)" >&2
import sys
from pathlib import Path
import numpy as np
from tools.verify_ac2 import verify, ALPHAEVOLVE_MAY_2025
root, out = Path(sys.argv[1]), Path(sys.argv[2])
REC = 0.963588110582029
rows = [verify(ALPHAEVOLVE_MAY_2025, "AlphaEvolve, May 2025 (DeepMind's published 50-step construction)")]
for f in sorted(root.glob("*/best.npy")):
    rows.append(verify(np.load(f), f.parent.name, max_n=2_000_000))
lines = ["# Verification of the Helix v10 jobs' constructions", "",
         "Every best construction re-scored independently (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own "
         "verification code (ported line by line), EinsteinArena's verifier (as its API publishes it) and, up to "
         "400,000 steps, exact rational arithmetic. Digits are truncated, not rounded. The arena's record is "
         f"{REC:.12f}; a new arena #1 needs {REC + 1e-5:.12f}.", "",
         "| Construction | Steps | Helix | DeepMind's code | Arena's code | Exact | All agree | Against the record |",
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
if [ "${done_gens:-0}" -ge "$GENS" ]; then
  echo "== $NAME: finished: $(grep -E '^[0-9:]+ done:' "$LOG" | tail -1)"
  MSG="Helix v10 job ($NAME): finished, $done_gens generations; results, report, verification and continuation pack"
else
  echo "== $NAME: stopped before generation $GENS (at $done_gens: the deadline, a stop, or an error; see $LOG); run this script again to continue it"
  MSG="Helix v10 job ($NAME): stopped after generation $done_gens; results, report, verification and continuation pack"
fi
"$PY" -m helix9.publish --run "$DIR" --out "$RESULTS/$NAME" --log "$LOG" --full 2>&1 | tail -2
"$PY" -m helix9.report "$ROOT_RUNS" --out "$RESULTS/REPORT.md" > /dev/null 2>&1 || echo "   (the report failed; the run data are fine)"
echo "== verifying the record"
verify
echo "== the run's own continuation pack (only what its source's pack doesn't hold)"
$NICE_CMD "$PY" -m helix9.pack build --run "$DIR" --search "$DIR/constructions" --out "$RESULTS/$NAME/pack" --budget-mb "$PACK_MB" \
    $([ -f "$PACK/manifest.json" ] && echo "--base $PACK") 2>&1 | tail -1 | sed 's/^/   /'
git_push "$MSG" "$RESULTS"
if [ "$PUSH" = "1" ]; then
  echo "== every construction of $NAME to GitHub, as release constructions-$NAME-g$done_gens"
  # only what the source's release doesn't hold, naming it as the base: a download of this release restores the chain
  VBASE=""; "$PY" -m helix9.vault exists --tag "$SRC_TAG" > /dev/null 2>&1 && VBASE="$SRC_TAG"
  if $NICE_CMD "$PY" -m helix9.vault upload --run "$DIR" --folder "$DIR/constructions${LOCAL_HAVE:+,$LOCAL_HAVE}" \
      --tag "constructions-$NAME-g$done_gens" --base "$VBASE" >> "$LOG" 2>&1; then
    grep -E "^vault:" "$LOG" | tail -1 | sed 's/^/   /'
  else
    echo "   (the upload failed: $(grep -E '^vault:' "$LOG" | tail -1); the constructions stay in $DIR/constructions; running this script again retries)"
  fi
fi
echo "== the report: $RESULTS/REPORT.md; the map: viz/mapview.html ($RESULTS/$NAME/mapview.json)"
"$PY" - "$DIR" <<'PY' 2>/dev/null || true
import json, sys
from pathlib import Path
from helix9.pack import jl
d = Path(sys.argv[1])
st = json.loads((d / "state.json").read_text())
s = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else {}
if s.get("gens_done") == st.get("gen_done"):
    print(f"   best {s['best']:.9f} ({s['best_id']}, track {s['best_track']}, N={s['best_n']}) after generation {s['gens_done']}; "
          f"records at {s['records_at'][-10:]}")
else:                       # no summary of this session (the grace ran out before it was written): the history says
    h = [x for x in jl(d / "history.jsonl") if "best" in x]
    if h:
        print(f"   best {h[-1]['best']:.9f} ({h[-1].get('best_id')}) after generation {h[-1]['gen']}")
PY
if [ "${done_gens:-0}" -ge "$GENS" ]; then
  echo "== all jobs done"
else
  echo "== stopped before generation $GENS (at $done_gens); run this script again to continue it"
fi
