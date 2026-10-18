#!/usr/bin/env bash
# The open-suite job list (docs/OPEN_SUITE.md): invented problems with no reference and no ceiling, plus a
# thinking-mode ablation. Meant for an unattended cloud machine. Safe to re-run at any time: finished jobs are
# skipped, unfinished ones resume from their last generation. Each finished job is copied to results/open/<job>/
# and pushed (commits as Shreyas Naik).
#
#   scripts/run_open_jobs.sh                 # everything below, gently (one run at a time)
#   PARALLEL=2 WORKERS=2 scripts/run_open_jobs.sh   # faster, on a machine with room to spare
#
# Gentle on a small shared machine by default: one run at a time (PARALLEL=1), one fitting worker (WORKERS=1),
# low CPU and IO priority (nice/ionice), a small feature-value cache (HELIX_CACHE_MB), and a memory guard: a run
# starts only when at least MIN_FREE_MB of memory is available (it waits otherwise).
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$(command -v python3 || command -v python)}"
PARALLEL="${PARALLEL:-1}"
WORKERS="${WORKERS:-1}"
GENS="${GENS:-12}"
MIN_FREE_MB="${MIN_FREE_MB:-1500}"
export HELIX_CACHE_MB="${HELIX_CACHE_MB:-96}"
NICE_CMD="nice -n 10"
command -v ionice >/dev/null && NICE_CMD="ionice -c 3 nice -n 10"
PUSH="${PUSH:-1}"
FAKE="${FAKE:-0}"                         # 1 = no model calls (tests this script end to end)
export GIT_NAME="${GIT_NAME:-Shreyas Naik}" GIT_EMAIL="${GIT_EMAIL:-119774329+cybercryptixcoder@users.noreply.github.com}"

# job name | problem | strategy variant
#   low-bt  : Researcher thinks at low, a high-effort breakthrough every 5th generation (the default)
#   none    : no hidden thinking anywhere
#   low     : Researcher at low, no breakthrough generations
#   high    : Researcher and Navigator always at high
JOBS="forage forage low-bt
thermal thermal low-bt
backtrack backtrack low-bt
duel duel low-bt
fairshare fairshare low-bt
stacker stacker low-bt
runner runner low-bt
repair repair low-bt
progression progression low-bt
forage-none forage none
forage-low forage low
forage-high forage high
duel-none duel none
duel-low duel low
duel-high duel high"

echo "== preflight"
DRY=1 SMOKE=0 PUSH=0 bash scripts/run_meta.sh || { echo "preflight failed: fix the error above first" >&2; exit 3; }
"$PY" -m helix3.run binpack1d -g 1 --fake --workers 1 --out "$(mktemp -d)/smoke" > /dev/null 2>&1 \
  || { echo "preflight: Helix's crash test failed (python -m helix3.run binpack1d -g 1 --fake)" >&2; exit 3; }
for p in forage thermal backtrack duel fairshare stacker runner repair progression; do
  HELIX_CHECK_SLOW_OK=1 "$PY" -m suite.check "$p" > /dev/null 2>&1 || { echo "problem $p fails its check: python -m suite.check $p" >&2; exit 3; }
done

echo "== strategy variants"
"$PY" - <<'PY'
import json, shutil
from pathlib import Path
base = Path("helix3/strategy")
variants = {
    "low-bt": {},
    "none": {"researcher": {"effort": "none"}, "navigator": {"effort": "none"}, "breakthrough": {"every": 0}},
    "low": {"researcher": {"effort": "low"}, "navigator": {"effort": "none"}, "breakthrough": {"every": 0}},
    "high": {"researcher": {"effort": "high"}, "navigator": {"effort": "high"}, "breakthrough": {"every": 0}},
}
for name, over in variants.items():
    d = Path("runs/variants") / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(base, d, ignore=shutil.ignore_patterns("__pycache__"))
    cfg = json.loads((d / "config.json").read_text())
    cfg.setdefault("diagnostics", {})["show_reference"] = False      # no hints about what good looks like
    for k, v in over.items():
        cfg.setdefault(k, {}).update(v)
    (d / "config.json").write_text(json.dumps(cfg, indent=1))
    print("  ", name, {k: cfg[k].get("effort", cfg[k]) for k in ("researcher", "navigator")}, "breakthrough", cfg["breakthrough"].get("every"))
PY

publish() {
  local name="$1" src="runs/open/$1"
  [ "$PUSH" = "1" ] || return 0
  mkdir -p "results/open/$name" && cp -r "$src/." "results/open/$name/"
  ( command -v flock >/dev/null && flock 9
    git add -f "results/open/$name" && git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q \
      -m "Open-suite run $name: trace and results" || exit 0
    for i in 1 2 3; do git pull -q --rebase origin HEAD && git push -q origin HEAD && break; sleep 5; done
  ) 9> runs/.git.lock
}

wait_for_memory() {   # don't start a run while the machine is short of memory
  while [ -r /proc/meminfo ]; do
    local free; free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    [ "${free:-0}" -ge "$MIN_FREE_MB" ] && return
    echo "   (waiting: ${free} MB available, need $MIN_FREE_MB)"; sleep 120
  done
}

one() {       # name problem variant
  local name="$1" prob="$2" var="$3" dir="runs/open/$1"
  if [ -f "$dir/summary.json" ] && [ -f "results/open/$name/summary.json" ]; then echo "== $name: done already"; return; fi
  wait_for_memory
  if [ -f "$dir/checkpoint.json" ]; then
    echo "== $name: resuming"; $NICE_CMD "$PY" -m helix3.run --resume "$dir" -g "$GENS" --workers "$WORKERS" >> "$dir.log" 2>&1
  else
    echo "== $name: starting ($prob, $var)"; mkdir -p runs/open
    $NICE_CMD "$PY" -m helix3.run "$prob" -g "$GENS" --strategy "runs/variants/$var" --out "$dir" --label "$name" --workers "$WORKERS" \
      $([ "$FAKE" = "1" ] && echo --fake) > "$dir.log" 2>&1
  fi
  if [ -f "$dir/summary.json" ]; then
    echo "== $name: finished: $(grep -E '^done' "$dir.log" | tail -1)"; cp "$dir.log" "$dir/run.log"; publish "$name"
  else
    echo "== $name: did not finish (see $dir.log); run this script again to resume it" >&2
  fi
}
export -f one publish wait_for_memory; export PY PUSH GENS FAKE WORKERS MIN_FREE_MB NICE_CMD

mkdir -p runs/open
echo "$JOBS" | xargs -P "$PARALLEL" -L 1 bash -c 'one "$0" "$1" "$2"'
echo "== all jobs done"
