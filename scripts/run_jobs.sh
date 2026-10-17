#!/usr/bin/env bash
# The unattended job list: Helix runs on the problem suite, then a meta run. Meant for a cloud machine.
# Safe to re-run at any time: finished jobs are skipped, unfinished ones resume from their last generation.
# Each finished job is copied to results/v3/<job>/ and pushed to GitHub (commits as Shreyas Naik).
#
#   scripts/run_jobs.sh                    # everything below
#   PARALLEL=3 META_HOURS=4 scripts/run_jobs.sh
#   SKIP_META=1 scripts/run_jobs.sh        # only the Helix runs
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$(command -v python3 || command -v python)}"
PARALLEL="${PARALLEL:-3}"                 # Helix runs at the same time
META_HOURS="${META_HOURS:-4}"
PUSH="${PUSH:-1}"
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"

# job name | problem | generations
JOBS="bp2d-25 binpack2d 25
binpack1d-10 binpack1d 10
knapsack-10 knapsack 10
scheduling-10 scheduling 10
coloring-10 coloring 10
setcover-10 setcover 10
jobshop-10 jobshop 10
tsp-10 tsp 10
cvrp-10 cvrp 10"

echo "== preflight"
DRY=1 SMOKE=1 PUSH=0 bash scripts/run_meta.sh || { echo "preflight failed: fix the error above first" >&2; exit 3; }

publish() {   # copy one finished run into results/ and push it (retries a pull --rebase on a race)
  local name="$1" src="runs/jobs/$1"
  [ "$PUSH" = "1" ] || return 0
  mkdir -p "results/v3/$name" && cp -r "$src/." "results/v3/$name/"
  ( command -v flock >/dev/null && flock 9
    git add -f "results/v3/$name" && git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q \
      -m "Helix run $name: trace and results" || exit 0
    for i in 1 2 3; do git pull -q --rebase origin HEAD && git push -q origin HEAD && break; sleep 5; done
  ) 9> runs/.git.lock
}

one() {       # name problem gens: start, resume or skip
  local name="$1" prob="$2" gens="$3" dir="runs/jobs/$1"
  if [ -f "$dir/summary.json" ] && [ -f "results/v3/$name/summary.json" ]; then echo "== $name: done already"; return; fi
  if [ -f "$dir/checkpoint.json" ]; then
    echo "== $name: resuming"; "$PY" -m helix3.run --resume "$dir" -g "$gens" >> "$dir.log" 2>&1
  else
    echo "== $name: starting"; mkdir -p runs/jobs
    "$PY" -m helix3.run "$prob" -g "$gens" --out "$dir" --label "$name" > "$dir.log" 2>&1
  fi
  if [ -f "$dir/summary.json" ]; then
    echo "== $name: finished: $(grep -E '^done' "$dir.log" | tail -1)"; cp "$dir.log" "$dir/run.log"; publish "$name"
  else
    echo "== $name: did not finish (see $dir.log); run this script again to resume it" >&2
  fi
}
export -f one publish; export PY PUSH

mkdir -p runs/jobs
echo "$JOBS" | xargs -P "$PARALLEL" -L 1 bash -c 'one "$0" "$1" "$2"'

if [ "${SKIP_META:-0}" != "1" ]; then
  last="$(ls -d meta_runs/outer-* 2>/dev/null | tail -1)"
  if [ -n "$last" ] && grep -q '"running"' "$last/status.json" 2>/dev/null; then
    echo "== meta: resuming $last"; RESUME="$last" PUSH="$PUSH" bash scripts/run_meta.sh
  elif [ -z "$last" ] || [ "${NEW_META:-0}" = "1" ]; then
    echo "== meta: starting a $META_HOURS h run"; HOURS="$META_HOURS" SMOKE=0 PUSH="$PUSH" bash scripts/run_meta.sh
  else
    echo "== meta: $last is finished (NEW_META=1 starts another)"
  fi
fi
echo "== all jobs done"
