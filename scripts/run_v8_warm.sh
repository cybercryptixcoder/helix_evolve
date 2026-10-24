#!/usr/bin/env bash
# The Helix v8 job on the second autocorrelation inequality (docs/V8_JOB.md): one v8 run that continues the v7 run
# v7-s1 (record 0.9412521, generation 290) for 100 more generations at 60 s per program. Every program, construction,
# finding and track of v7-s1 is kept; the first generation puts every earlier track's best on the map of hills.
#
#   nohup bash scripts/run_v8_warm.sh > v8_warm.log 2>&1 &
#
# - Runs side by side with the VRP v8 job (Shreyas, October 23: "two runs running in parallel on the machine"): it
#   does not wait for the VRP job, and the two share helix4's machine-wide evaluation slots (EVAL_SLOTS, default 2).
#   It waits for any other autocorrelation Helix run (v4, v5, v6, v4.7, v7, v8) to finish first; it never stops anything.
# - Safe to re-run at any time: one copy at a time (a second start exits at once), and the run resumes from its last
#   finished generation. A deadline (HOURS after the first start, default 20) stops it after its current generation;
#   running this script again later continues it.
# - Results: results/v8warm/ (the run, REPORT.md: what exploration did and the map of hills, VERIFICATION.md), pushed as
#   Shreyas Naik;
#   progress is pushed every 40 minutes.
#
#   SRC=/path/to/v7-s1      the run to continue (default: runs/v7warm/v7-s1, else results/v7warm/v7-s1)
#   ADD=100                 generations to add (or GENS=390, the generation to stop at)
#   FAKE=1 PUSH=0 ADD=2 BUDGET=2 bash scripts/run_v8_warm.sh     # the whole job with a fake model (a test)
set -uo pipefail
cd "$(dirname "$0")/.."
# run from a snapshot: a `git pull` that changes this file mid-job must not change what the running job does
if [ -z "${V8_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" runs/.v8_job_snapshot.sh.$$ && mv -f runs/.v8_job_snapshot.sh.$$ runs/.v8_job_snapshot.sh \
    && V8_SNAPSHOT=1 exec bash runs/.v8_job_snapshot.sh "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
ROOT_RUNS="${ROOT_RUNS:-runs/v8warm}"
RESULTS="${RESULTS:-results/v8warm}"
NAME="${NAME:-v8-s1}"
SEED="${SEED:-1}"
BUDGET="${BUDGET:-60}"
ADD="${ADD:-100}"
HOURS="${HOURS:-20}"
MIN_FREE_MB="${MIN_FREE_MB:-1200}"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"
export HELIX4_EVAL_SLOTS="${EVAL_SLOTS:-2}"
export HELIX4_SLOTS_DIR="${HELIX4_SLOTS_DIR:-$(pwd)/runs/v4/.slots}"   # helix4's default: shared machine-wide
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"
NICE_CMD="nice -n 10"
command -v ionice >/dev/null && NICE_CMD="ionice -c 3 nice -n 10"
FAKE_FLAG=""; [ "$FAKE" = "1" ] && FAKE_FLAG="--fake"
mkdir -p "$ROOT_RUNS" "$HELIX4_SLOTS_DIR" "$RESULTS"
if command -v flock >/dev/null; then
  exec 8> "$ROOT_RUNS/.job.lock"
  flock -n 8 || { echo "== this job is already running (another copy holds $ROOT_RUNS/.job.lock); this copy exits and changes nothing"; exit 0; }
fi
DIR="$ROOT_RUNS/$NAME"

# ------------------------------------------------------------------ preflight (about a minute)
echo "== Helix v8 job (autocorrelation, warm): $NAME, $BUDGET s per program, $HELIX4_EVAL_SLOTS evaluation slots shared machine-wide"
echo "== preflight"
"$PY" -c "import numpy, scipy; print('   python', __import__('sys').version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "preflight: numpy or scipy missing: pip install -r helix5/requirements.txt" >&2; exit 3; }
PRE="$(mktemp -d)"
HELIX4_SLOTS_DIR="$PRE/slots" "$PY" -m helix8.run --gens 2 --budget 2 --fake --out "$PRE/v8" > "$PRE/v8.log" 2>&1 \
  || { echo "preflight: the v8 crash test failed:" >&2; tail -20 "$PRE/v8.log" >&2; exit 3; }
echo "   crash test passed (v8, fake model)"
rm -rf "$PRE"
if [ "$FAKE" != "1" ]; then
  "$PY" - <<'PY' || { echo "preflight: the model can't be reached (is .env in the repo root with LUMINAL_API_KEYS=...?)" >&2; exit 3; }
from helix4.llm import LLM
r = LLM().chat("preflight", "You answer in one word.", "Say OK.", max_tokens=20, effort="none", tries=3)
print("   model answers:", r.text.strip()[:20], f"({r.seconds:.1f} s)")
PY
fi

# ------------------------------------------------------------------ the warm start (once)
if [ ! -f "$DIR/state.json" ]; then
  if [ -z "${SRC:-}" ]; then
    SRC="runs/v7warm/v7-s1"
    [ -f "$SRC/programs.jsonl" ] || SRC="results/v7warm/v7-s1"
  fi
  [ -f "$SRC/programs.jsonl" ] || { echo "warm start: $SRC has no programs.jsonl" >&2; exit 3; }
  echo "== warm start from $SRC ($(ls "$SRC/constructions" 2>/dev/null | wc -l) constructions)"
  "$PY" -m helix8.warm --src "$SRC" --out "$DIR" --mode continue --seed "$SEED" --budget "$BUDGET" || exit 3
fi
FROM="$("$PY" -c "import json, sys; s = json.load(open(sys.argv[1])); print(s.get('warm_gen') or s['gen_done'])" "$DIR/state.json")"
GENS="${GENS:-$((FROM + ADD))}"
echo "   $NAME continues from generation $FROM to generation $GENS"

# ------------------------------------------------------------------ never alongside another autocorrelation run
# (the VRP job is not waited for: the two run side by side, as asked; this only waits, it never stops anything)
other_running() {
  pgrep -f "python[0-9.]*( +-[A-Za-z]+)* +-m +helix(4|5|6|47|7|8)\.run" > /dev/null 2>&1 \
    || pgrep -f "^bash .*(\.v[4567]_job_snapshot\.sh|\.v47_job_snapshot\.sh)" > /dev/null 2>&1
}
waited=0
while other_running; do
  [ -n "${MAX_WAIT_MIN:-}" ] && [ "$waited" -ge "$MAX_WAIT_MIN" ] && { echo "   (another Helix run is still running after $waited minutes; starting anyway)"; break; }
  [ $((waited % 30)) -eq 0 ] && echo "   (waiting for another autocorrelation Helix run to finish before starting: $waited min so far)"
  sleep 60; waited=$((waited + 1))
done

# ------------------------------------------------------------------ publishing
git_push() {   # message
  [ "$PUSH" = "1" ] || return 0
  ( command -v flock >/dev/null && flock 9
    git add -f "$RESULTS" 2>/dev/null
    git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" -c commit.gpgsign=false commit -q -m "$1" || exit 0
    for i in 1 2 3 4; do git pull -q --rebase origin HEAD && git push -q origin HEAD && exit 0; sleep $((10 * i)); done
    echo "   (push failed: results stay in $RESULTS and $ROOT_RUNS)" >&2
  ) 9> "$ROOT_RUNS/.git.lock"
}

copy_run() {   # [light]
  local dst="$RESULTS/$NAME"
  mkdir -p "$dst"
  for f in summary.json history.jsonl plans.jsonl findings.jsonl tracks.jsonl hills.jsonl signatures.jsonl noise.json state.json; do
    [ -f "$DIR/$f" ] && cp "$DIR/$f" "$dst/"
  done
  [ -f "$ROOT_RUNS/$NAME.log" ] && cp "$ROOT_RUNS/$NAME.log" "$dst/run.log"
  "$PY" -m helix8.report "$ROOT_RUNS" --out "$RESULTS/REPORT.md" > /dev/null 2>&1 || echo "   (the report failed; the run data are fine)" >&2
  [ "${1:-}" = "light" ] && return 0
  for f in programs.jsonl best.py best.npy; do [ -f "$DIR/$f" ] && cp "$DIR/$f" "$dst/"; done
  [ -f "$DIR/trace.jsonl" ] && gzip -nc "$DIR/trace.jsonl" > "$dst/trace.jsonl.gz"
  return 0
}

verify() {
  "$PY" - "$RESULTS" "$RESULTS/VERIFICATION.md" <<'PY' || echo "   (verification failed to run)" >&2
import sys
from pathlib import Path
import numpy as np
from tools.verify_ac2 import verify, ALPHAEVOLVE_MAY_2025
root, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = [verify(ALPHAEVOLVE_MAY_2025, "AlphaEvolve, May 2025 (DeepMind's published 50-step construction)")]
for f in sorted(root.glob("*/best.npy")):
    rows.append(verify(np.load(f), f.parent.name))
lines = ["# Verification of the Helix v8 job's constructions", "",
         "Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, "
         "DeepMind's own verification code (ported line by line), and exact rational arithmetic. Digits are truncated, "
         "not rounded.", "", "| Construction | Steps | Helix | DeepMind's code | Exact | All agree |", "|---|---|---|---|---|---|"]
for r in rows:
    if not r.get("valid"):
        lines.append(f"| {r['label']} | - | INVALID: {r.get('problem')} | | | |")
        continue
    lines.append(f"| {r['label']} | {r['N']} | {r['helix']:.12f} | {r['deepmind_code']:.12f} | {r.get('exact_str', '-')} | {r['agree']} |")
out.write_text("\n".join(lines) + "\n")
print("\n".join("   " + l for l in lines[5:]))
PY
}

# ------------------------------------------------------------------ the deadline: fixed at the first start, kept across restarts
[ -f "$ROOT_RUNS/deadline" ] || "$PY" -c "import time; print(int(time.time() + float('$HOURS') * 3600))" > "$ROOT_RUNS/deadline"
export HELIX4_DEADLINE="$(cat "$ROOT_RUNS/deadline")"
echo "   deadline: $(date -d "@$HELIX4_DEADLINE" 2>/dev/null || echo "$HELIX4_DEADLINE") (the run stops after the generation in progress then)"

status() {
  "$PY" - "$DIR" <<'PY'
import json, sys, time
from pathlib import Path
d = Path(sys.argv[1])
h = [json.loads(l) for l in (d / "history.jsonl").read_text().splitlines() if l.strip()] if (d / "history.jsonl").exists() else []
h = [x for x in h if "level" in x]
msg = "starting" if not h else (f"{d.name} g{h[-1]['gen']} {h[-1]['best']:.7f}, level {h[-1]['level']}, "
                                f"{sum(1 for x in h if x.get('new_best'))} records so far")
print(time.strftime("== %H:%M progress: ") + msg, flush=True)
PY
}
( SL=""; trap 'kill ${SL:-} 2>/dev/null; exit 0' TERM
  n=0
  while true; do sleep "${TICK:-600}" & SL=$!; wait $SL; status; n=$((n + 1)); [ $((n % 4)) -eq 0 ] && { copy_run light; git_push "Helix v8 job: progress at $(date -u +%H:%M) UTC"; }; done
) &
TICKER=$!
trap 'kill $TICKER 2>/dev/null' EXIT

# ------------------------------------------------------------------ the run
while [ -r /proc/meminfo ]; do
  free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  [ "${free:-0}" -ge "$MIN_FREE_MB" ] && break
  echo "   ($NAME waiting: ${free} MB available, need $MIN_FREE_MB)"; sleep 120
done
echo "== $NAME: running (log: $ROOT_RUNS/$NAME.log)"
$NICE_CMD "$PY" -m helix8.run --out "$DIR" --gens "$GENS" $FAKE_FLAG >> "$ROOT_RUNS/$NAME.log" 2>&1
kill $TICKER 2>/dev/null
status
if [ -f "$DIR/summary.json" ] && [ "$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['gens_done'])" "$DIR/summary.json")" -ge "$GENS" ]; then
  echo "== $NAME: finished: $(grep -E '^[0-9:]+ done:' "$ROOT_RUNS/$NAME.log" | tail -1)"
else
  echo "== $NAME: stopped before generation $GENS (the deadline, or see $ROOT_RUNS/$NAME.log); run this script again to continue it"
fi
copy_run
echo "== verifying the result"
verify
git_push "Helix v8 job ($NAME): results, report and verification"
echo "== the report: $RESULTS/REPORT.md"
"$PY" - "$DIR" <<'PY' || true
import json, sys
from pathlib import Path
s = json.loads((Path(sys.argv[1]) / "summary.json").read_text())
print(f"   best {s['best']:.9f} ({s['best_id']}, track {s['best_track']}, N={s['best_n']}) after generation {s['gens_done']}; "
      f"records at {s['records_at'][-10:]}")
PY
echo "== all jobs done"
