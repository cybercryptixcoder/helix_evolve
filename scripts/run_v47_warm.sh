#!/usr/bin/env bash
# The v4.7 warm-start job (docs/V47_WARM.md): two v4.7 runs on the second autocorrelation inequality, both starting
# from the best construction of the 150-generation v4 run (0.940795), for 40 more generations at 60 s per program:
#   v47-s1  continues that run as generation 151 under v4.7: every program, construction and finding kept;
#   v47-s2  starts from the best program and its construction alone, with a fresh Atlas.
# Their difference answers whether the old Atlas helps or hurts.
#
#   nohup bash scripts/run_v47_warm.sh > v47_warm.log 2>&1 &
#
# SRC=/path/to/the/v4/run   the 150-generation run folder (with constructions/); found automatically if not given,
#                           falling back to results/v4cont/atlas-s1 in the repo (programs and best.npy only).
# Everything else is scripts/run_v47_jobs.sh (waiting for other jobs, preflight, the deadline, pushing results).
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$(command -v python3 || command -v python)}"
ROOT="${ROOT_RUNS:-runs/v47warm}"
mkdir -p "$ROOT"
if [ -z "${SRC:-}" ]; then
  SRC="$("$PY" - <<'PY'
import json, os
from pathlib import Path
best, n_best = None, -1
roots = [Path.home(), Path.cwd()]
seen = set()
for root in roots:
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - str(root).count(os.sep) > 5 or "/." in dirpath or "node_modules" in dirpath:
            dirnames[:] = []
            continue
        if "state.json" in filenames and "programs.jsonl" in filenames and dirpath not in seen:
            seen.add(dirpath)
            try:
                st = json.load(open(os.path.join(dirpath, "state.json")))
            except Exception:
                continue
            if st.get("gen_done") == 150 and st.get("config", {}).get("problem", "ac2") == "ac2" and "warm" not in st:
                n = len(list(Path(dirpath, "constructions").glob("*.npy"))) if Path(dirpath, "constructions").is_dir() else 0
                if n > n_best:
                    best, n_best = dirpath, n
print(best or "results/v4cont/atlas-s1")
PY
)"
fi
echo "== warm start from $SRC ($(ls "$SRC/constructions" 2>/dev/null | wc -l) constructions)"
[ -f "$SRC/programs.jsonl" ] && [ -f "$SRC/best.npy" ] || { echo "warm start: $SRC has no programs.jsonl or best.npy" >&2; exit 3; }
"$PY" -m helix47.warm --src "$SRC" --out "$ROOT/v47-s1" --mode continue --seed 1 --budget "${BUDGET:-60}" || exit 3
"$PY" -m helix47.warm --src "$SRC" --out "$ROOT/v47-s2" --mode best --seed 2 --budget "${BUDGET:-60}" || exit 3
ROOT_RUNS="$ROOT" RESULTS="${RESULTS:-results/v47warm}" CONDITIONS="v47" SEEDS="1 2" GENS="${GENS:-190}" \
  HOURS="${HOURS:-10}" exec bash scripts/run_v47_jobs.sh "$@"
