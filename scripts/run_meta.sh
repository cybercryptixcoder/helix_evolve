#!/usr/bin/env bash
# Run the META loop for a fixed number of hours, then commit and push the run to GitHub.
# Every setting is an environment variable, so you can change it per run:
#   HOURS=5 INNER_GENS=5 PARALLEL=4 scripts/run_meta.sh
#   RESUME=meta_runs/outer-20261017-120556 scripts/run_meta.sh     # continue an interrupted run (its own settings)
#   DRY=1 scripts/run_meta.sh                                       # only the preflight checks
# The Luminal key is read from the environment or from .env (gitignored). It is never written to the run folder.
#
# Guards, so a long run doesn't fail silently or lose work:
#   - preflight (about 2 minutes): dependencies, every Luminal key answers, and a one-generation crash test of
#     Helix and the meta loop; any failure stops here, before the hours start (SMOKE=0 skips the crash test)
#   - the run is resumable at any point: inner runs checkpoint every generation, the outer loop keeps each
#     generation's candidates, and the time budget counts only time spent. After a shutdown, the keeper resumes it
#     (scripts/install_keeper.sh makes the keeper start at login), or run with RESUME=<folder> yourself
#   - on macOS the Mac is kept awake while the run goes (caffeinate); closing the lid on battery still sleeps it
#   - if every inner run of the starting strategy crashes, the run stops at once with the reason (status: failed)
set -uo pipefail
cd "$(dirname "$0")/.."

RESUME="${RESUME:-}"
if [ -n "$RESUME" ]; then
  RESUME="${RESUME%/}"
  NAME="$(basename "$RESUME")"
  OUT="meta_runs/$NAME"
  [ -d "$OUT" ] || { echo "no run folder $OUT" >&2; exit 2; }
  # the run's own settings; anything set on the command line wins
  [ -f "$OUT/launch.env" ] && while IFS='=' read -r k v; do [ -n "$k" ] && [ -z "${!k:-}" ] && export "$k=$v"; done < "$OUT/launch.env"
fi

HOURS="${HOURS:-4}"                      # budget of time actually spent (the generation in flight finishes: allow ~1 h extra)
OUTER_GENS="${OUTER_GENS:-99}"           # upper bound; the time budget normally ends the run first
INNER_GENS="${INNER_GENS:-5}"            # generations per inner Helix run
REPEATS="${REPEATS:-2}"                  # inner runs per problem per candidate (noise estimate)
DEEP="${DEEP:-2}"                        # Researcher candidates per outer generation
WIDE="${WIDE:-2}"                        # Mutator candidates per outer generation
PARALLEL="${PARALLEL:-4}"                # inner runs at the same time
PROBLEMS="${PROBLEMS:-binpack1d,knapsack,tsp,scheduling}"
HELD_OUT="${HELD_OUT:-coloring}"
PUSH="${PUSH:-1}"                        # 0 = keep the results local
SMOKE="${SMOKE:-1}"                      # 0 = skip the one-generation crash test in the preflight
GIT_NAME="${GIT_NAME:-cybercryptixcoder}"
GIT_EMAIL="${GIT_EMAIL:-official.shreyas28@gmail.com}"
NAME="${NAME:-outer-$(date +%Y%m%d-%H%M%S)}"
OUT="meta_runs/$NAME"
PY="${PYTHON:-$(command -v python3 || command -v python)}"

[ -f .env ] && set -a && . ./.env && set +a
if [ -z "${LUMINAL_API_KEYS:-}${LUMINAL_API_KEY:-}" ]; then
  echo "No Luminal key. Put LUMINAL_API_KEYS=lum_live_... in .env (see .env.example)." >&2; exit 2
fi
mkdir -p meta_runs

# ------------------------------------------------------------------ preflight
echo "preflight: dependencies"
"$PY" - <<'PY' || "$PY" -m pip install -q -r helix3/requirements.txt || { echo "could not install helix3/requirements.txt" >&2; exit 3; }
import numpy, cma, certifi
PY
"$PY" -c "import helix3.engine, meta.outer" || { echo "Helix doesn't import: see the error above" >&2; exit 3; }
echo "preflight: Luminal keys"
"$PY" - <<'PY' || { echo "no Luminal key answers: fix .env before a long run" >&2; exit 3; }
from helix3.llm import LLM
llm = LLM()
bad = []
for k in llm._keys:
    one = LLM(keys=[k.key])
    try:
        one.chat("preflight", "Reply with OK.", "OK?", max_tokens=8, tries=2)
    except Exception as e:  # noqa: BLE001
        bad.append(f"...{k.key[-6:]}: {str(e)[:120]}")
print(f"  {len(llm._keys) - len(bad)} of {len(llm._keys)} keys answer" + ("".join("\n  " + b for b in bad)))
raise SystemExit(1 if bad and len(bad) == len(llm._keys) else 0)
PY
if [ -z "$RESUME" ] && [ "$SMOKE" = "1" ]; then
  echo "preflight: one-generation crash test (Helix with no model calls, then one outer generation)"
  SM="$(mktemp -d)"
  "$PY" -m helix3.run binpack1d -g 1 --fake --out "$SM/inner" > "$SM/inner.log" 2>&1 \
    || { echo "Helix crashed in the crash test:" >&2; tail -20 "$SM/inner.log" >&2; exit 4; }
  "$PY" -m meta.outer --fake-inner --outer-generations 1 --inner-generations 1 --repeats 1 --deep 1 --wide 1 \
      --problems binpack1d --held-out knapsack --parallel 2 --out "$SM/outer" > "$SM/outer.log" 2>&1 \
    || { echo "the meta loop crashed in the crash test:" >&2; tail -30 "$SM/outer.log" >&2; exit 4; }
  rm -rf "$SM"
  echo "  ok"
fi

[ "${DRY:-0}" = "1" ] && { echo "preflight passed (DRY=1: not starting the run)"; exit 0; }

# ------------------------------------------------------------------ the run
mkdir -p "$OUT"
if [ -z "$RESUME" ]; then                # the settings a resume reuses (no secrets here)
  printf '%s\n' "HOURS=$HOURS" "OUTER_GENS=$OUTER_GENS" "INNER_GENS=$INNER_GENS" "REPEATS=$REPEATS" "DEEP=$DEEP" \
    "WIDE=$WIDE" "PARALLEL=$PARALLEL" "PROBLEMS=$PROBLEMS" "HELD_OUT=$HELD_OUT" "PUSH=$PUSH" \
    "GIT_NAME=$GIT_NAME" "GIT_EMAIL=$GIT_EMAIL" > "$OUT/launch.env"
fi

publish() {
  [ "$PUSH" = "1" ] || { echo "PUSH=0: results stay in $OUT"; return; }
  local state; state="$("$PY" -c "import json;print(json.load(open('$OUT/status.json')).get('state',''))" 2>/dev/null)"
  local dest="results/meta/$NAME"
  mkdir -p "$dest" && rsync -a --exclude '__pycache__' --exclude '*.pyc' "$OUT/" "$dest/" 2>/dev/null || cp -r "$OUT/." "$dest/"
  cp "$OUT.log" "$dest/run.log" 2>/dev/null
  git add -f "$dest" || return
  git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q \
      --author="$GIT_NAME <$GIT_EMAIL>" -m "Meta run $NAME: trace and report ($HOURS h budget, ${state:-unknown})" \
    && git push origin HEAD && echo "pushed $dest" || echo "push failed: run 'git push' yourself; results are in $dest" >&2
}
trap publish EXIT                      # also runs on Ctrl-C or a stop from the dashboard

AWAKE=()
command -v caffeinate >/dev/null && AWAKE=(caffeinate -ims)      # macOS: no idle or system sleep while running
if [ -n "$RESUME" ]; then
  echo "resuming meta run $NAME ($HOURS h budget of time spent)" | tee -a "$OUT.log"
  ${AWAKE[@]+"${AWAKE[@]}"} "$PY" -m meta.outer --resume "$OUT" --hours "$HOURS" 2>&1 | tee -a "$OUT.log"
else
  echo "meta run $NAME: $HOURS h, problems=$PROBLEMS held-out=$HELD_OUT inner=$INNER_GENS x$REPEATS parallel=$PARALLEL"
  ${AWAKE[@]+"${AWAKE[@]}"} "$PY" -m meta.outer --hours "$HOURS" --outer-generations "$OUTER_GENS" --inner-generations "$INNER_GENS" \
    --repeats "$REPEATS" --deep "$DEEP" --wide "$WIDE" --parallel "$PARALLEL" \
    --problems "$PROBLEMS" --held-out "$HELD_OUT" --out "$OUT" 2>&1 | tee "$OUT.log"
fi
