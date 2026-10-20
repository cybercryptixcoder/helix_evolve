#!/usr/bin/env bash
# The Helix v4 overnight job (docs/V4_DESIGN.md): one problem (the second autocorrelation inequality), three memory
# conditions (atlas, journal, control) x three seeds, 20 generations each, all side by side.
#
#   nohup bash scripts/run_v4_jobs.sh > v4_jobs.log 2>&1 &
#
# Safe to re-run at any time: finished runs are skipped, unfinished ones resume from their last generation.
# Gentle on a small shared machine: the runs mostly wait on the model; the CPU-heavy part (running the programs) is
# capped machine-wide at EVAL_SLOTS programs at a time (default 2, one per core), at low priority, and a program only
# starts when at least 600 MB of memory is free. A deadline (HOURS after the first start, default 7.5) stops every
# run after its current generation, so results always exist by morning. Each finished run is copied to
# results/v4/<run>/ and pushed (commits as Shreyas Naik); progress and the report are pushed every 40 minutes too.
#
#   FAKE=1 PUSH=0 GENS=2 bash scripts/run_v4_jobs.sh     # the whole job with a fake model, nothing pushed (a test)
set -uo pipefail
cd "$(dirname "$0")/.."
# run from a snapshot: bash reads a script as it goes, so a `git pull` that changes this file mid-job (the job's own
# pushes pull first) must not change what the running job does
if [ -z "${V4_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" runs/.v4_job_snapshot.sh && V4_SNAPSHOT=1 exec bash runs/.v4_job_snapshot.sh "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
GENS="${GENS:-20}"
SEEDS="${SEEDS:-1 2 3}"
CONDITIONS="${CONDITIONS:-atlas journal control}"
BUDGET="${BUDGET:-20}"
HOURS="${HOURS:-7.5}"
MIN_FREE_MB="${MIN_FREE_MB:-1200}"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"
ROOT_RUNS="${ROOT_RUNS:-runs/v4}"
RESULTS="${RESULTS:-results/v4}"
export HELIX4_EVAL_SLOTS="${EVAL_SLOTS:-2}"
export HELIX4_SLOTS_DIR="$ROOT_RUNS/.slots"
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"
NICE_CMD="nice -n 10"
command -v ionice >/dev/null && NICE_CMD="ionice -c 3 nice -n 10"
FAKE_FLAG=""; [ "$FAKE" = "1" ] && FAKE_FLAG="--fake"
mkdir -p "$ROOT_RUNS" "$HELIX4_SLOTS_DIR"

echo "== Helix v4 job: conditions [$CONDITIONS] x seeds [$SEEDS], $GENS generations, $BUDGET s per program, $HELIX4_EVAL_SLOTS evaluation slots"

# ------------------------------------------------------------------ preflight (about a minute)
echo "== preflight"
"$PY" -c "import numpy, scipy; print('   python', __import__('sys').version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "preflight: numpy or scipy missing: pip install -r helix4/requirements.txt" >&2; exit 3; }
PRE="$(mktemp -d)"
for c in atlas journal control; do
  HELIX4_SLOTS_DIR="$PRE/slots" "$PY" -m helix4.run --condition "$c" --gens 1 --budget 2 --fake --out "$PRE/$c" > "$PRE/$c.log" 2>&1 \
    || { echo "preflight: the $c crash test failed:" >&2; tail -20 "$PRE/$c.log" >&2; exit 3; }
done
echo "   crash tests passed (atlas, journal, control, fake model)"
if [ "$FAKE" != "1" ]; then
  "$PY" - <<'PY' || { echo "preflight: the model can't be reached (is .env in the repo root with LUMINAL_API_KEYS=...?)" >&2; exit 3; }
from helix4.llm import LLM
r = LLM().chat("preflight", "You answer in one word.", "Say OK.", max_tokens=20, effort="none", tries=3)
print("   model answers:", r.text.strip()[:20], f"({r.seconds:.1f} s)")
PY
fi
rm -rf "$PRE"

# ------------------------------------------------------------------ the deadline: fixed at the first start, kept across restarts
[ -f "$ROOT_RUNS/deadline" ] || "$PY" -c "import time; print(int(time.time() + float('$HOURS') * 3600))" > "$ROOT_RUNS/deadline"
export HELIX4_DEADLINE="$(cat "$ROOT_RUNS/deadline")"
echo "   deadline: $(date -d "@$HELIX4_DEADLINE" 2>/dev/null || echo "$HELIX4_DEADLINE") (runs stop after the generation in progress then)"

# ------------------------------------------------------------------ publishing
git_push() {   # message
  [ "$PUSH" = "1" ] || return 0
  ( command -v flock >/dev/null && flock 9
    git add -f "$RESULTS" && git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" -c commit.gpgsign=false commit -q -m "$1" || exit 0
    for i in 1 2 3 4; do git pull -q --rebase origin HEAD && git push -q origin HEAD && exit 0; sleep $((10 * i)); done
    echo "   (push failed: results stay in $RESULTS and $ROOT_RUNS; see the tarball step in docs/V4_JOB.md)" >&2
  ) 9> "$ROOT_RUNS/.git.lock"
}

copy_run() {   # name  (everything worth keeping; constructions only for the best program)
  local name="$1" src="$ROOT_RUNS/$1" dst="$RESULTS/$1"
  mkdir -p "$dst"
  for f in summary.json history.jsonl plans.jsonl programs.jsonl findings.jsonl journal.jsonl journal_summary.json state.json best.py best.npy; do
    [ -f "$src/$f" ] && cp "$src/$f" "$dst/"
  done
  [ -f "$src/trace.jsonl" ] && gzip -c "$src/trace.jsonl" > "$dst/trace.jsonl.gz"
  [ -f "$ROOT_RUNS/$name.log" ] && cp "$ROOT_RUNS/$name.log" "$dst/run.log"
  return 0
}

report() {
  "$PY" -m helix4.report "$ROOT_RUNS" "$RESULTS" > /dev/null 2>&1 || echo "   (report failed; the run data are fine)" >&2
}

progress() {
  for d in "$ROOT_RUNS"/*/; do [ -f "$d/state.json" ] && copy_run "$(basename "$d")"; done
  report
  git_push "Helix v4 job: progress at $(date -u +%H:%M) UTC"
}

# ------------------------------------------------------------------ one run
one() {   # condition seed
  local name="$1-s$2" dir="$ROOT_RUNS/$1-s$2"
  if [ -f "$dir/summary.json" ] && [ -f "$RESULTS/$name/summary.json" ]; then echo "== $name: done already"; return; fi
  while [ -r /proc/meminfo ]; do
    local free; free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    [ "${free:-0}" -ge "$MIN_FREE_MB" ] && break
    echo "   ($name waiting: ${free} MB available, need $MIN_FREE_MB)"; sleep 120
  done
  if [ -f "$dir/state.json" ]; then echo "== $name: resuming"; else echo "== $name: starting"; fi
  $NICE_CMD "$PY" -m helix4.run --condition "$1" --seed "$2" --gens "$GENS" --budget "$BUDGET" --out "$dir" $FAKE_FLAG >> "$ROOT_RUNS/$name.log" 2>&1
  if [ -f "$dir/summary.json" ]; then
    echo "== $name: finished: $(grep -E '^[0-9:]+ done:' "$ROOT_RUNS/$name.log" | tail -1)"
    copy_run "$name"; git_push "Helix v4 run $name: results"
  else
    echo "== $name: did not finish (see $ROOT_RUNS/$name.log); run this script again to resume it" >&2
  fi
}

status() {   # one line: each run's generation and best score so far
  "$PY" - "$ROOT_RUNS" <<'PY'
import json, sys, time
from pathlib import Path
parts = []
for d in sorted(p for p in Path(sys.argv[1]).glob("*-s*") if p.is_dir()):
    h = [l for l in (d / "history.jsonl").read_text().splitlines() if l.strip()] if (d / "history.jsonl").exists() else []
    if h:
        j = json.loads(h[-1])
        parts.append(f"{d.name} g{j['gen']} {j['best']:.5f}")
print(time.strftime("== %H:%M progress: ") + (" | ".join(parts) or "starting"), flush=True)
PY
}

( trap 'kill $SL 2>/dev/null; exit 0' TERM
  n=0
  while true; do sleep 600 & SL=$!; wait $SL; status; n=$((n + 1)); [ $((n % 4)) -eq 0 ] && progress; done
) &   # a status line every 10 minutes; progress pushed every 40
TICKER=$!
trap 'kill $TICKER 2>/dev/null' EXIT

PIDS=()
for s in $SEEDS; do
  for c in $CONDITIONS; do
    one "$c" "$s" &
    PIDS+=($!)
    sleep 15
  done
done
wait "${PIDS[@]}"
kill $TICKER 2>/dev/null

echo "== report"
progress
"$PY" - "$ROOT_RUNS" <<'PY'
import json, sys
from pathlib import Path
for d in sorted(p for p in Path(sys.argv[1]).glob("*-s*") if p.is_dir()):
    s = d / "summary.json"
    if s.exists():
        j = json.loads(s.read_text())
        print(f"   {d.name:12s} best {j['best']:.6f} ({j['best_id']}, N={j['best_n']}) after {j['gens_done']} generations")
    else:
        print(f"   {d.name:12s} unfinished")
PY
echo "== all jobs done"
