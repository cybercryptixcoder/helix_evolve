#!/usr/bin/env bash
# Run the META loop for a fixed number of hours, then commit and push the run to GitHub.
# Every setting is an environment variable, so you can change it per run:
#   HOURS=5 INNER_GENS=5 PARALLEL=4 scripts/run_meta.sh
# The Luminal key is read from the environment or from .env (gitignored). It is never written to the run folder.
set -uo pipefail
cd "$(dirname "$0")/.."

HOURS="${HOURS:-4}"                      # wall-clock budget (the generation in flight finishes: allow ~1 h extra)
OUTER_GENS="${OUTER_GENS:-99}"           # upper bound; the time budget normally ends the run first
INNER_GENS="${INNER_GENS:-5}"            # generations per inner Helix run
REPEATS="${REPEATS:-2}"                  # inner runs per problem per candidate (noise estimate)
DEEP="${DEEP:-2}"                        # Researcher candidates per outer generation
WIDE="${WIDE:-2}"                        # Mutator candidates per outer generation
PARALLEL="${PARALLEL:-4}"                # inner runs at the same time
PROBLEMS="${PROBLEMS:-binpack1d,knapsack,tsp,scheduling}"
HELD_OUT="${HELD_OUT:-coloring}"
PUSH="${PUSH:-1}"                        # 0 = keep the results local
GIT_NAME="${GIT_NAME:-cybercryptixcoder}"
GIT_EMAIL="${GIT_EMAIL:-official.shreyas28@gmail.com}"
NAME="${NAME:-outer-$(date +%Y%m%d-%H%M%S)}"
OUT="meta_runs/$NAME"

[ -f .env ] && set -a && . ./.env && set +a
if [ -z "${LUMINAL_API_KEYS:-}${LUMINAL_API_KEY:-}" ]; then
  echo "No Luminal key. Put LUMINAL_API_KEYS=lum_live_... in .env (see .env.example)." >&2; exit 2
fi
mkdir -p meta_runs

publish() {
  [ "$PUSH" = "1" ] || { echo "PUSH=0: results stay in $OUT"; return; }
  local dest="results/meta/$NAME"
  mkdir -p "$dest" && rsync -a --exclude '__pycache__' --exclude '*.pyc' "$OUT/" "$dest/" 2>/dev/null || cp -r "$OUT/." "$dest/"
  cp "$OUT.log" "$dest/run.log" 2>/dev/null
  git add -f "$dest" || return
  git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q \
      --author="$GIT_NAME <$GIT_EMAIL>" -m "Meta run $NAME: trace and report ($HOURS h budget)" \
    && git push origin HEAD && echo "pushed $dest" || echo "push failed: run 'git push' yourself; results are in $dest" >&2
}
trap publish EXIT                      # also runs on Ctrl-C or a stop from the dashboard

echo "meta run $NAME: $HOURS h, problems=$PROBLEMS held-out=$HELD_OUT inner=$INNER_GENS x$REPEATS parallel=$PARALLEL"
python -m meta.outer --hours "$HOURS" --outer-generations "$OUTER_GENS" --inner-generations "$INNER_GENS" \
  --repeats "$REPEATS" --deep "$DEEP" --wide "$WIDE" --parallel "$PARALLEL" \
  --problems "$PROBLEMS" --held-out "$HELD_OUT" --out "$OUT" 2>&1 | tee "$OUT.log"
