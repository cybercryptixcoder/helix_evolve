#!/usr/bin/env bash
# The Helix v4.6 + v6 overnight job (docs/V6_DESIGN.md): the second autocorrelation inequality, v6 (the agent) and
# v4.6 (Atlas around ideas, with the mutation halo) x three seeds, 30 generations each, all side by side. The v4,
# v4.5 and v5 results are the baselines.
#
#   nohup bash scripts/run_v6_jobs.sh > v6_jobs.log 2>&1 &
#
# - If another Helix job is still running on this machine, it waits for it to finish first (never two at once). It
#   only ever waits: it never stops anything.
# - At the end it verifies every best construction three ways (tools/verify_ac2.py) into results/v6/VERIFICATION.md.
# - Safe to re-run at any time: finished runs are skipped, unfinished ones resume from their last generation.
# - Gentle on a small shared machine: programs are evaluated at most EVAL_SLOTS at a time machine-wide (default 2,
#   one per core), at low priority, only with MIN_FREE_MB free; a deadline (HOURS after the first start, default 8)
#   stops every run after its current generation. Each finished run is copied to results/v6/<run>/ and pushed
#   (commits as Shreyas Naik); progress and the report are pushed every 40 minutes.
#
#   FAKE=1 PUSH=0 GENS=2 bash scripts/run_v6_jobs.sh     # the whole job with a fake model, nothing pushed (a test)
set -uo pipefail
cd "$(dirname "$0")/.."
# run from a snapshot: bash reads a script as it goes, so a `git pull` that changes this file mid-job must not
# change what the running job does
if [ -z "${V6_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" runs/.v6_job_snapshot.sh && V6_SNAPSHOT=1 exec bash runs/.v6_job_snapshot.sh "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
GENS="${GENS:-30}"
SEEDS="${SEEDS:-1 2 3}"
CONDITIONS="${CONDITIONS:-v6 v46}"
BUDGET="${BUDGET:-30}"
HOURS="${HOURS:-8}"
MIN_FREE_MB="${MIN_FREE_MB:-1200}"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"
ROOT_RUNS="${ROOT_RUNS:-runs/v6}"
RESULTS="${RESULTS:-results/v6}"
V5_RESULTS="${V5_RESULTS:-results/v5}"
V4_RESULTS="${V4_RESULTS:-results/v4}"
export HELIX4_EVAL_SLOTS="${EVAL_SLOTS:-2}"
export HELIX4_SLOTS_DIR="$ROOT_RUNS/.slots"
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"
NICE_CMD="nice -n 10"
command -v ionice >/dev/null && NICE_CMD="ionice -c 3 nice -n 10"
FAKE_FLAG=""; [ "$FAKE" = "1" ] && FAKE_FLAG="--fake"
mkdir -p "$ROOT_RUNS" "$HELIX4_SLOTS_DIR" "$RESULTS"
# one copy at a time: a second start while the job runs (by hand or by an agent) exits at once and touches nothing
if command -v flock >/dev/null; then
  exec 8> "$ROOT_RUNS/.job.lock"
  flock -n 8 || { echo "== this job is already running (another copy holds $ROOT_RUNS/.job.lock); this copy exits and changes nothing"; exit 0; }
fi

echo "== Helix v4.6 + v6 job: conditions [$CONDITIONS] x seeds [$SEEDS], $GENS generations, $BUDGET s per program, $HELIX4_EVAL_SLOTS evaluation slots"

# ------------------------------------------------------------------ never run alongside another Helix job
# an earlier run is a python process started with "-m helix4.run" or "-m helix5.run"; an earlier job runs as
# "bash runs/.v4_job_snapshot.sh" or "bash runs/.v5_job_snapshot.sh" (and keeps running through its final report and
# push). Match exactly those, so that unrelated processes that merely mention the names never hold this job back.
# This only waits; it never stops anything.
other_running() {
  pgrep -f "^[^ ]*python[0-9.]* -m helix[45]\.run( |$)" > /dev/null 2>&1 || pgrep -f "^bash runs/\.v[45]_job_snapshot\.sh" > /dev/null 2>&1
}
waited=0
while other_running; do
  [ "$waited" -ge "${MAX_WAIT_MIN:-240}" ] && { echo "   (another Helix job is still running after $waited minutes; starting anyway)"; break; }
  [ $((waited % 30)) -eq 0 ] && echo "   (waiting for the other Helix job to finish before starting: $waited min so far)"
  sleep 60; waited=$((waited + 1))
done

# ------------------------------------------------------------------ preflight (about a minute)
echo "== preflight"
"$PY" -c "import numpy, scipy; print('   python', __import__('sys').version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "preflight: numpy or scipy missing: pip install -r helix5/requirements.txt" >&2; exit 3; }
PRE="$(mktemp -d)"
for c in v46 v6; do
  HELIX4_SLOTS_DIR="$PRE/slots" "$PY" -m helix6.run --condition "$c" --gens 1 --budget 2 --fake --out "$PRE/$c" > "$PRE/$c.log" 2>&1 \
    || { echo "preflight: the $c crash test failed:" >&2; tail -20 "$PRE/$c.log" >&2; exit 3; }
done
echo "   crash tests passed (v4.6, v6, fake model)"
if [ "$FAKE" != "1" ]; then
  "$PY" - <<'PY' || { echo "preflight: the model can't be reached (is .env in the repo root with LUMINAL_API_KEYS=...?)" >&2; exit 3; }
from helix4.llm import LLM
r = LLM().chat("preflight", "You answer in one word.", "Say OK.", max_tokens=20, effort="none", tries=3)
print("   model answers:", r.text.strip()[:20], f"({r.seconds:.1f} s)")
PY
fi
rm -rf "$PRE"

# ------------------------------------------------------------------ publishing
git_push() {   # message
  [ "$PUSH" = "1" ] || return 0
  ( command -v flock >/dev/null && flock 9
    git add -f "$RESULTS" 2>/dev/null
    git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" -c commit.gpgsign=false commit -q -m "$1" || exit 0
    for i in 1 2 3 4; do git pull -q --rebase origin HEAD && git push -q origin HEAD && exit 0; sleep $((10 * i)); done
    echo "   (push failed: results stay in $RESULTS and $ROOT_RUNS; see the tarball step in docs/V6_JOB.md)" >&2
  ) 9> "$ROOT_RUNS/.git.lock"
}

verify() {   # folder-with-run-folders  output.md  title
  "$PY" - "$1" "$2" "$3" <<'PY' || echo "   (verification failed to run)" >&2
import sys
from pathlib import Path
from tools.verify_ac2 import verify, ALPHAEVOLVE_MAY_2025
root, out, title = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
rows = [verify(ALPHAEVOLVE_MAY_2025, "AlphaEvolve, May 2025 (DeepMind's published 50-step construction)")]
for f in sorted(root.glob("*/best.npy")):
    import numpy as np
    rows.append(verify(np.load(f), f.parent.name))
lines = [f"# {title}", "", "Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, "
         "DeepMind's own verification code (ported line by line), and exact rational arithmetic (on the float heights "
         "themselves up to 12,000 steps; above that on a copy rounded to integers at 2^30, itself a valid construction). "
         "Digits are truncated, not rounded.", "",
         "| Construction | Steps | Helix | DeepMind's code | Exact | All agree |", "|---|---|---|---|---|---|"]
for r in rows:
    if not r.get("valid"):
        lines.append(f"| {r['label']} | - | INVALID: {r.get('problem')} | | | |")
        continue
    lines.append(f"| {r['label']} | {r['N']} | {r['helix']:.12f} | {r['deepmind_code']:.12f} | {r.get('exact_str', '-')} | {r['agree']} |")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines) + "\n")
print("\n".join("   " + l for l in lines[5:]))
PY
}

# ------------------------------------------------------------------ the deadline: fixed at the first start, kept across restarts
[ -f "$ROOT_RUNS/deadline" ] || "$PY" -c "import time; print(int(time.time() + float('$HOURS') * 3600))" > "$ROOT_RUNS/deadline"
export HELIX5_DEADLINE="$(cat "$ROOT_RUNS/deadline")"
echo "   deadline: $(date -d "@$HELIX5_DEADLINE" 2>/dev/null || echo "$HELIX5_DEADLINE") (runs stop after the generation in progress then)"

copy_run() {   # name [light]
  local name="$1" src="$ROOT_RUNS/$1" dst="$RESULTS/$1"
  mkdir -p "$dst"
  for f in summary.json history.jsonl plans.jsonl findings.jsonl meta.jsonl threads.jsonl theory.jsonl state.json; do
    [ -f "$src/$f" ] && cp "$src/$f" "$dst/"
  done
  [ -f "$ROOT_RUNS/$name.log" ] && cp "$ROOT_RUNS/$name.log" "$dst/run.log"
  [ "${2:-}" = "light" ] && return 0
  for f in programs.jsonl best.py best.npy; do [ -f "$src/$f" ] && cp "$src/$f" "$dst/"; done
  [ -f "$src/trace.jsonl" ] && gzip -nc "$src/trace.jsonl" > "$dst/trace.jsonl.gz"
  return 0
}

report() {
  "$PY" -m helix6.report "$V4_RESULTS" "$V5_RESULTS" "$ROOT_RUNS" --out "$RESULTS" > /dev/null 2>&1 || echo "   (report failed; the run data are fine)" >&2
}

progress() {   # [final]
  for d in "$ROOT_RUNS"/*/; do
    [ -f "$d/state.json" ] || continue
    if [ "${1:-}" = "final" ] || [ -f "$d/summary.json" ]; then copy_run "$(basename "$d")"; else copy_run "$(basename "$d")" light; fi
  done
  report
  git_push "Helix v4.6 + v6 job: progress at $(date -u +%H:%M) UTC"
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
  $NICE_CMD "$PY" -m helix6.run --condition "$1" --seed "$2" --gens "$GENS" --budget "$BUDGET" --out "$dir" $FAKE_FLAG >> "$ROOT_RUNS/$name.log" 2>&1
  if [ -f "$dir/summary.json" ]; then
    echo "== $name: finished: $(grep -E '^[0-9:]+ done:' "$ROOT_RUNS/$name.log" | tail -1)"
    copy_run "$name"; git_push "Helix v4.6 + v6 run $name: results"
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
  while true; do sleep "${TICK:-600}" & SL=$!; wait $SL; status; n=$((n + 1)); [ $((n % 4)) -eq 0 ] && progress; done
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
progress final
echo "== verifying the v4.6 and v6 results"
verify "$RESULTS" "$RESULTS/VERIFICATION.md" "Verification of the Helix v4.6 and v6 constructions"
git_push "Helix v4.6 + v6: independent verification of every best construction"
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
