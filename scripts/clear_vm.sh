#!/usr/bin/env bash
# Clear Helix from the VM, after the offload (docs/OFFLOAD.md). By Shreyas's order only.
#
#   bash /home/ubuntu/helix_v5_run/scripts/clear_vm.sh > /home/ubuntu/clear_vm.log 2>&1
#
# Each folder or file is deleted only if every archive that holds it is verified on GitHub at that moment (every part
# present with its SHA-256; tools/offload.py verify). The checkout is deleted only if it has no unpushed commits and no
# stash. Anything not verified is kept and reported. It runs from a copy of itself in /tmp, since it deletes the
# checkout it came from. Nothing else on the machine is touched: other projects, caches, Aether's own folders.
# KEEP_ALSO [""]: more paths (space-separated) to keep even though they are archived.
set -uo pipefail
H="${HOME_DIR:-/home/ubuntu}"
if [ -z "${CLEAR_COPY:-}" ]; then
  T="$(mktemp -d /tmp/helix_clear.XXXX)"
  cp "$0" "$T/clear_vm.sh" && cp "$(dirname "$0")/../tools/offload.py" "$T/offload.py" || { echo "clear: can't copy the tools"; exit 3; }
  ( cd "$(dirname "$0")/.." && git config --get remote.origin.url ) > "$T/origin" 2>/dev/null
  cd "$T" && CLEAR_COPY=1 exec bash "$T/clear_vm.sh" "$@"
fi
PY="$(command -v python3)"
PUB="cybercryptixcoder/helix_evolve"
PRIV="cybercryptixcoder/helix_evolve_private"
KEEP_ALSO="${KEEP_ALSO:-}"
echo "== clearing Helix from $H, $(date -u +%Y-%m-%dT%H:%MZ)"
df -h / | tail -1 | sed 's/^/   disk before: /'

busy="$( { pgrep -a -f 'snapshot' | awk '$2 ~ /bash$/ && $3 ~ /runs\/\.[^ ]*snapshot[^ ]*\.sh$/'
           pgrep -a -f 'helix' | awk '$2 ~ /python/ && $3 == "-m" && $4 ~ /^helix[0-9]*\.(run|job)$/'; } || true)"
[ -n "$busy" ] && { echo "clear: a Helix or offload job is running; nothing deleted:"; echo "$busy"; exit 3; }

verified() {   # repo unit...  -> 0 if every unit is verified on GitHub now
  local repo="$1"; shift
  for u in "$@"; do
    "$PY" offload.py verify --unit "$u" --repo "$repo" > "v_$u.json" 2>&1 || { echo "   $u: NOT verified ($(tail -c 200 "v_$u.json"))"; return 1; }
  done
}
kept=0; gone=0
clear() {   # path repo unit...
  local p="$1"; shift
  [ -e "$p" ] || { echo "   $p: not here (nothing to do)"; return; }
  for k in $KEEP_ALSO; do [ "$p" = "$k" ] && { echo "   $p: kept (KEEP_ALSO)"; kept=$((kept+1)); return; }; done
  if verified "$@"; then rm -rf -- "$p" && echo "   $p: deleted (archives verified: ${*:2})" && gone=$((gone+1)); else echo "   $p: KEPT"; kept=$((kept+1)); fi
}

# the checkout: only with nothing unpushed
C="$H/helix_v5_run"
if [ -d "$C/.git" ]; then
  ( cd "$C" && git fetch -q origin )
  unpushed="$(cd "$C" && git log --oneline origin/main..HEAD | wc -l)"; stash="$(cd "$C" && git stash list | wc -l)"
  if [ "$unpushed" != "0" ] || [ "$stash" != "0" ]; then echo "   $C: KEPT ($unpushed unpushed commits, $stash stashes)"; kept=$((kept+1))
  else clear "$C" "$PUB" runs-field runs-v10 runs-v101 runs-v102 runs-v4 runs-v47 runs-v47warm runs-v4cont runs-v5 runs-v6 \
         runs-v7warm runs-v8warm runs-v9warm checkout-extras
  fi
fi
# the private routing problem
clear "$H/helix_vrp" "$PRIV" private-helix_vrp
clear "$H/vrp_work" "$PRIV" private-vrp_work
for f in "$H"/helix_vrp.zip "$H"/vrp_*; do [ -f "$f" ] && clear "$f" "$PRIV" private-files; done
# the other Helix folders
for d in helix_v4_run helix_evolve helix_open_suite helix_evolve_run helix-speed-copy helix-work helix-chart warmstart_exp \
         runview runview.bak-20261027 milp_job2; do
  clear "$H/$d" "$PRIV" "private-extra-$d"
done
echo "== done: $gone deleted, $kept kept"
df -h / | tail -1 | sed 's/^/   disk after: /'
echo "   left on purpose: helix-exploit-docs, luminal-knowledge, luminal-probe-round4, helix-job-guard.*, the incident"
echo "   report and aether-context-dump.md (all archived), and everything that isn't Helix"
