#!/usr/bin/env bash
# The offload job (docs/OFFLOAD.md): everything Helix keeps on the VM goes to GitHub, losslessly, so the VM can be
# cleared. Nothing on the VM is changed or deleted; deleting is a separate step, by Shreyas, after the check.
#
#   cd /home/ubuntu/helix_v5_run && git pull && setsid nohup bash scripts/offload_vm.sh > offload.log 2>&1 < /dev/null &
#
# The stages:
#   0. refuses to start while a Helix job is running (it never stops anything); one copy at a time (a lock);
#   1. preflight: Python, disk, GitHub access (it creates the release archive-index), the private repo;
#   2. the inventory (read-only): every folder in the home folder, every run folder and whether GitHub has its state,
#      every release;
#   3. the constructions of the v10.2 runs as releases (helix9/vault.py), the format the warm starts read
#      (v10.2's job script didn't upload them);
#   4. the archives (tools/offload.py): one release archive-<unit> per folder under runs/ (runs/vault, a copy of
#      releases already on GitHub, is left out), one for the checkout's untracked files and runs/'s loose files
#      (.env never), each a byte-for-byte tar split into parts, with every file's SHA-256; scanned first for the
#      keys in .env and the lines of .offload_forbid; anything about the private routing problem (helix_vrp,
#      vrp_work, vrp files) goes only to the private repo PRIVATE_REPO, which must exist and be private;
#   5. the check: every archive's parts on GitHub against their SHA-256; the report (OFFLOAD_REPORT.md, the
#      inventory, every unit's result) uploaded to the release archive-index.
# Last line: "== offload complete: every unit verified" or "== offload NOT complete: ...; run this script again".
#
# Robust: started again after any stop, it rebuilds each archive (deterministic) and re-sends only the parts GitHub
# lacks; it installs no cron job or timer, and stops nothing.
# Estimated: about 10-20 minutes per 10 GB (compression on one core, then upload). Disk: one part at a time (up to
# PART_MB, default 1900 MB) in runs/.offload_tmp. Memory: under 200 MB.
#
# Settings: PRIVATE_REPO [cybercryptixcoder/helix_evolve_private]  HOME_DIR [/home/ubuntu]  PART_MB [1900]  VAULT_V102 [1]
#   EXTRA_PUBLIC [""] (more folders to archive publicly, space-separated)  FAKE [0]
#
#   FAKE=1 bash scripts/offload_vm.sh     # a test: GitHub replaced by runs/.offload_fake
set -uo pipefail
cd "$(dirname "$0")/.." || exit 3
if [ -z "${OFFLOAD_SNAPSHOT:-}" ]; then
  mkdir -p runs && cp "$0" "runs/.offload_job_snapshot.sh.$$" && mv -f "runs/.offload_job_snapshot.sh.$$" "runs/.offload_job_snapshot.sh" \
    && OFFLOAD_SNAPSHOT=1 exec bash "runs/.offload_job_snapshot.sh" "$@"
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"
CHECKOUT="$(pwd)"
HOME_DIR="${HOME_DIR:-/home/ubuntu}"
PRIVATE_REPO="${PRIVATE_REPO:-cybercryptixcoder/helix_evolve_private}"
PART_MB="${PART_MB:-1900}"
VAULT_V102="${VAULT_V102:-1}"
EXTRA_PUBLIC="${EXTRA_PUBLIC:-}"
FAKE="${FAKE:-0}"
OUT="runs/.offload_report"
T="$CHECKOUT/tools/offload.py"
export OFFLOAD_TMP="$CHECKOUT/runs/.offload_tmp" OFFLOAD_PART_MB="$PART_MB"
[ "$FAKE" = "1" ] && export OFFLOAD_FAKE_DIR="$CHECKOUT/runs/.offload_fake" OFFLOAD_FAKE_PRIVATE=1

exec 8> "runs/.offload.lock"
flock -n 8 || { echo "== the offload is already running; nothing changed"; exit 0; }

echo "== Helix offload job, $(date -u +%Y-%m-%dT%H:%MZ), from $CHECKOUT"
# ------------------------------------------------------------------ 0. no Helix job may be running
busy="$( { pgrep -a -f 'snapshot' | awk '$2 ~ /bash$/ && $3 ~ /runs\/\.[^ ]*snapshot[^ ]*\.sh$/ && $3 !~ /offload_job_snapshot/'
           pgrep -a -f 'helix' | awk '$2 ~ /python/ && $3 == "-m" && $4 ~ /^helix[0-9]*\.(run|job)$/'; } || true)"
if [ -n "$busy" ]; then
  echo "preflight: a Helix job is still running, so nothing was archived (this job never stops anything):"
  echo "$busy" | sed 's/^/   /'
  exit 3
fi
# ------------------------------------------------------------------ 1. preflight
"$PY" -c "import numpy, tarfile, gzip, json" 2>/dev/null || { echo "preflight: Python with numpy is needed ($PY)"; exit 3; }
free_mb=$(( $(df -Pk "$CHECKOUT" | awk 'NR==2 {print $4}') / 1024 ))
if [ "$free_mb" -lt $(( PART_MB + 800 )) ]; then
  PART_MB=$(( (free_mb - 800) / 2 )); export OFFLOAD_PART_MB="$PART_MB"
  [ "$PART_MB" -lt 200 ] && { echo "preflight: only $free_mb MB free on disk; at least 1,200 MB is needed"; exit 3; }
  echo "   (disk: $free_mb MB free, so parts of $PART_MB MB)"
fi
mkdir -p "$OUT" "$OFFLOAD_TMP"
"$PY" - <<'EOF' || exit 3
import sys; sys.path.insert(0, "tools")
import offload
slug = offload.origin_slug()
gh = offload.hub(slug)
try:
    repo = gh.repo()
    rel = gh.release("archive-index", create=True, note="The offload's report (tools/offload.py, docs/OFFLOAD.md).")
    assert rel is not None and repo is not None
    # a real upload, checked and removed: proves the whole path before hours are committed
    import hashlib, os, pathlib
    p = pathlib.Path(os.environ["OFFLOAD_TMP"]) / "preflight.bin"
    p.write_bytes(os.urandom(300_000))
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    offload.put(gh, rel, gh.assets(rel), p, "preflight.bin", sha, p.stat().st_size)
    a = gh.assets(rel).get("preflight.bin")
    assert a and a["size"] == 300_000 and (a.get("digest") in (None, f"sha256:{sha}")), f"uploaded file came back as {a}"
    assert offload.same_bytes(gh, a, sha), "the uploaded file downloads with a different SHA-256"
    gh.delete(a)
    p.unlink()
except Exception as e:
    print(f"preflight: no write access to GitHub releases of {slug}: {str(e)[-300:]}"); sys.exit(3)
print(f"   GitHub: can write releases of {slug}")
EOF
PRIVATE_OK=0
if "$PY" - "$PRIVATE_REPO" <<'EOF'
import sys; sys.path.insert(0, "tools")
import offload
slug = sys.argv[1]
try:
    r = offload.hub(slug).repo()
except Exception as e:
    r = None
if not r:
    print(f"   private repo {slug}: not found, so the private routing files are NOT archived (create it, private, and run again)"); sys.exit(1)
if not r.get("private"):
    print(f"   private repo {slug} is PUBLIC: the private routing files are NOT archived there"); sys.exit(1)
print(f"   private repo {slug}: exists and is private")
EOF
then PRIVATE_OK=1; fi
[ -f .offload_forbid ] && echo "   forbidden strings: .offload_forbid ($(wc -l < .offload_forbid) lines), plus the keys in .env"
echo "   preflight passed"

# ------------------------------------------------------------------ 2. inventory
"$PY" "$T" inventory --out "$OUT" --home "$HOME_DIR" || echo "   (the inventory failed; the archives go ahead)"

: > "$OUT/results.jsonl"
run_unit() {   # unit repo args...
  local unit="$1" repo="$2"; shift 2
  local log="$OUT/unit_$unit.log"
  ionice -c 3 nice -n 10 "$PY" -u "$T" archive --unit "$unit" --repo "$repo" "$@" 2>&1 | tee "$log" \
    | grep --line-buffered -v '^RESULT ' | sed -u 's/^/   /'
  if grep -q '^RESULT ' "$log"; then grep '^RESULT ' "$log" | tail -1 | sed 's/^RESULT //' >> "$OUT/results.jsonl"
  else echo "{\"unit\": \"$unit\", \"status\": \"failed: $(tail -1 "$log" | tr -d '"\\' | cut -c1-200)\"}" >> "$OUT/results.jsonl"; fi
}
SLUG="$("$PY" -c "import sys; sys.path.insert(0,'tools'); import offload; print(offload.origin_slug())")"

# ------------------------------------------------------------------ 3. v10.2's constructions, as vault releases
if [ "$VAULT_V102" = "1" ] && [ "$FAKE" != "1" ]; then
  for d in runs/v102/v102-*; do
    [ -d "$d/constructions" ] || continue
    name="$(basename "$d")"
    if "$PY" -m helix9.vault exists --tag "constructions-$name" > /dev/null 2>&1; then
      echo "== constructions-$name: on GitHub already"
    else
      echo "== constructions-$name: uploading (each construction verified by re-scoring)"
      ionice -c 3 nice -n 10 "$PY" -m helix9.vault upload --run "$d" --folder "$d/constructions" --tag "constructions-$name" \
        2>&1 | grep -E '^vault:' | tail -2 | sed 's/^/   /'
    fi
  done
fi

# ------------------------------------------------------------------ 4. the archives
is_private() { case "$1" in *vrp*|*VRP*) return 0 ;; *) return 1 ;; esac; }
for d in runs/*/; do
  d="${d%/}"; name="$(basename "$d")"
  case "$name" in vault|.offload_tmp|.offload_report|.offload_fake) continue ;; esac
  if is_private "$name"; then
    [ "$PRIVATE_OK" = "1" ] && run_unit "private-runs-$name" "$PRIVATE_REPO" --src "$d" \
      || echo "{\"unit\": \"private-runs-$name\", \"status\": \"not archived: no private repo\"}" >> "$OUT/results.jsonl"
    continue
  fi
  run_unit "runs-$name" "$SLUG" --src "$d"
done
# the checkout's untracked files outside runs/, and runs/'s loose files (never .env, the forbid list, the offload's own)
git ls-files -o -z | tr '\0' '\n' \
  | grep -v -E '^runs/[^/]+/|^runs/\.offload|(^|/)\.env|\.offload_forbid$|(^|/)__pycache__/|\.pyc$|^offload\.log$' \
  | grep -v -i 'vrp' > "$OUT/extras.txt" || true
run_unit "checkout-extras" "$SLUG" --files-from "$OUT/extras.txt"
for x in $EXTRA_PUBLIC; do run_unit "extra-$(basename "$x")" "$SLUG" --src "$x"; done
# the private routing problem: its package, its work folder and its files in the home folder
ls -d "$HOME_DIR"/*vrp* "$HOME_DIR"/*VRP* 2>/dev/null | grep -v -E '/(helix_vrp|vrp_work)$' > "$OUT/private_files.txt" || true
git ls-files -o | grep -v -E '^runs/[^/]+/|^runs/\.offload|(^|/)\.env' | grep -i vrp | sed "s|^|$CHECKOUT/|" >> "$OUT/private_files.txt" || true
for d in "$HOME_DIR/helix_vrp" "$HOME_DIR/vrp_work"; do
  [ -e "$d" ] || continue
  if [ "$PRIVATE_OK" = "1" ]; then run_unit "private-$(basename "$d")" "$PRIVATE_REPO" --src "$d"
  else echo "{\"unit\": \"private-$(basename "$d")\", \"status\": \"not archived: no private repo\"}" >> "$OUT/results.jsonl"; fi
done
if [ -s "$OUT/private_files.txt" ]; then
  if [ "$PRIVATE_OK" = "1" ]; then run_unit "private-files" "$PRIVATE_REPO" --files-from "$OUT/private_files.txt"
  else echo "{\"unit\": \"private-files\", \"status\": \"not archived: no private repo\"}" >> "$OUT/results.jsonl"; fi
fi

# ------------------------------------------------------------------ 5. the check and the report
"$PY" - "$OUT" <<'EOF'
import json, sys
out = sys.argv[1]
rows = [json.loads(l) for l in open(f"{out}/results.jsonl") if l.strip()]
ok = [r for r in rows if r.get("status") in ("verified", "empty")]
bad = [r for r in rows if r not in ok]
L = ["# Offload report", "", f"{len(ok)} of {len(rows)} units verified on GitHub.", "",
     "| Unit | Status | Files | GB | Parts | Compressed GB | From |", "|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['unit']} | {r['status']} | {r.get('files', '')} | {r.get('bytes', 0) / 1e9:.2f} | "
             f"{r.get('parts', '')} | {r.get('compressed', 0) / 1e9:.2f} | {', '.join(r.get('sources', []))} |")
    if r.get("blocked_files"):
        L.append(f"|  | blocked by: {', '.join(r['blocked_files'][:20])} |  |  |  |  |  |")
L += ["", "Restore any unit: `python3 tools/offload.py restore --unit <unit> --out <dir>` (add `--repo` for the private one).",
      "The inventory of the machine: INVENTORY.md and inventory.json (same release)."]
open(f"{out}/OFFLOAD_REPORT.md", "w").write("\n".join(L) + "\n")
print("\n".join(L[4:]))
open(f"{out}/.status", "w").write("ok" if not bad else "; ".join(f"{r['unit']}: {r['status']}" for r in bad))
EOF
rm -f "$OUT/units.log.tmp"
"$PY" "$T" publish-index --dir "$OUT" --repo "$SLUG" 2>&1 | tail -1
status="$(cat "$OUT/.status")"
if [ "$status" = "ok" ]; then echo "== offload complete: every unit verified"
else echo "== offload NOT complete: $status; run this script again"; fi
