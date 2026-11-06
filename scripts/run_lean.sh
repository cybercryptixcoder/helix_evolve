#!/usr/bin/env bash
# One lean Helix experiment on the VM, end to end (lean/README.md, docs/LEAN_PLAN.md).
#
#   cd /home/ubuntu/helix_v5_run && git pull && SPEC=experiments/lean/e3_core_ac2.json \
#     setsid nohup bash scripts/run_lean.sh > lean_e3.log 2>&1 < /dev/null &
#
# 1. preflight: Python with numpy and scipy, a crash test with a fake model, one real model call, GitHub
# 2. the experiment (python -m lean.bench SPEC): every run resumes from its files, so starting this script again
#    after any stop continues where it left off; a run that fails is retried
# 3. every PUSH_EVERY seconds, and at the end: lean.publish copies the runs to results/lean/<name>/ and pushes
#
# One copy per experiment (a lock). No cron, no timers. A stop signal stops the runs (each loses at most the round
# in progress) and pushes what is done. Settings: SPEC [required]  PUSH [1]  PUSH_EVERY [1800]  EVAL_SLOTS [2]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 3
SPEC="${SPEC:?set SPEC=experiments/lean/<name>.json}"
NAME="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['name'])" "$SPEC")" || exit 3
PUSH="${PUSH:-1}"; PUSH_EVERY="${PUSH_EVERY:-1800}"
export HELIX_EVAL_SLOTS="${EVAL_SLOTS:-2}" HELIX_SLOTS_DIR="$(pwd)/runs/.slots"
GIT_NAME="Shreyas Naik"; GIT_EMAIL="119774329+cybercryptixcoder@users.noreply.github.com"
mkdir -p runs/lean
exec 8> "runs/lean/.$NAME.lock"
flock -n 8 || { echo "== $NAME is already running; this copy exits"; exit 0; }
echo "== lean experiment $NAME ($SPEC), started $(date '+%F %T %Z'), commit $(git rev-parse --short HEAD)"

echo "== preflight"
python3 -c "import numpy, scipy" || { echo "needs numpy and scipy"; exit 3; }
T="$(mktemp -d)"
HELIX_SLOTS_DIR="$T/slots" python3 -m lean.run --out "$T/c" --rounds 2 --budget 2 --fake > "$T/log" 2>&1 \
  && HELIX_SLOTS_DIR="$T/slots" python3 -m lean.run --problem ac2 --out "$T/a" --rounds 1 --budget 2 --fake >> "$T/log" 2>&1 \
  || { echo "crash test failed:"; tail -20 "$T/log"; exit 3; }
rm -rf "$T"
python3 -c "from lean.llm import LLM; print('   model:', LLM().chat('preflight', 'One word.', 'Say OK.', max_tokens=20))" \
  || { echo "the model can't be reached (.env with LUMINAL_API_KEYS?)"; exit 3; }
[ "$PUSH" = "1" ] && { git push --dry-run -q origin HEAD || { echo "can't push to GitHub"; exit 3; }; }

push() {
  [ "$PUSH" = "1" ] || return 0
  python3 -m lean.publish "$SPEC" > /dev/null 2>&1 || echo "   (publish failed; the runs are fine)"
  ( flock 9
    git add -f "results/lean/$NAME" 2>/dev/null
    git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q -m "lean $NAME: $1" || exit 0
    for i in 1 2 3; do git pull -q --rebase --autostash origin HEAD && git push -q origin HEAD && exit 0; sleep 20; done
    echo "   (push failed; the next push sends it)" ) 9> runs/.git.lock
}

python3 -m lean.bench "$SPEC" &
BENCH=$!
trap 'echo "== stop requested"; pkill -TERM -P $BENCH 2>/dev/null; kill -TERM $BENCH 2>/dev/null' TERM INT HUP
while kill -0 $BENCH 2>/dev/null; do
  for _ in $(seq 1 $((PUSH_EVERY / 10))); do kill -0 $BENCH 2>/dev/null || break; sleep 10; done
  kill -0 $BENCH 2>/dev/null && push "progress at $(date -u +%H:%M) UTC"
done
wait $BENCH
push "finished"
cat "results/lean/$NAME/report.md" 2>/dev/null | head -40
echo "== done: $NAME"
