#!/usr/bin/env bash
# Start the Helix keeper at login, so interrupted runs (inner Helix runs and meta runs) resume by themselves after
# a restart, a crash or a closed terminal. The keeper checks every few minutes for runs whose process is gone and
# continues them from their last checkpoint. Runs you stopped on purpose are left alone.
#
#   scripts/install_keeper.sh            # install and start it (macOS: a LaunchAgent; Linux: a crontab @reboot line)
#   scripts/install_keeper.sh --remove   # uninstall
#   INTERVAL=120 scripts/install_keeper.sh   # check every 2 minutes (default 300 s)
#
# What it can't do: run while the computer is off or asleep. A run picks up where it left off when the computer
# is back. scripts/run_meta.sh keeps a Mac awake while a meta run goes (caffeinate), but closing the lid on battery
# still sleeps it.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
PY="${PYTHON:-$(command -v python3 || command -v python)}"
INTERVAL="${INTERVAL:-300}"
mkdir -p "$REPO/runs"
LOG="$REPO/runs/keeper.log"

case "$REPO" in
  "$HOME/Downloads"*|"$HOME/Documents"*|"$HOME/Desktop"*)
    if [ "$(uname)" = "Darwin" ]; then
      echo "Note: the repo is in a folder macOS protects ($REPO)."
      echo "A background agent may be refused access there. If $LOG shows 'Operation not permitted', either move"
      echo "the repo (for example to ~/code/helix_evolve) and run this again, or give $PY Full Disk Access"
      echo "(System Settings > Privacy & Security > Full Disk Access)."
    fi ;;
esac

if [ "$(uname)" = "Darwin" ]; then
  PL="$HOME/Library/LaunchAgents/com.helix.keeper.plist"
  if [ "${1:-}" = "--remove" ]; then
    launchctl unload "$PL" 2>/dev/null || true
    rm -f "$PL"
    echo "removed the keeper LaunchAgent"
    exit 0
  fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.helix.keeper</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>-m</string><string>helix3.keeper</string><string>--watch</string><string>$INTERVAL</string></array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$PATH</string></dict>
</dict>
</plist>
EOF
  launchctl unload "$PL" 2>/dev/null || true
  launchctl load -w "$PL"
  echo "installed: the keeper starts at login and checks every $INTERVAL s (log: $LOG)"
else
  if [ "${1:-}" = "--remove" ]; then
    (crontab -l 2>/dev/null | grep -v "helix3.keeper") | crontab - || true
    pkill -f "^$PY -m helix3.keeper" 2>/dev/null || true
    echo "removed the keeper from crontab"
    exit 0
  fi
  LINE="@reboot cd $REPO && $PY -m helix3.keeper --watch $INTERVAL >> $LOG 2>&1"
  (crontab -l 2>/dev/null | grep -v "helix3.keeper"; echo "$LINE") | crontab -
  nohup "$PY" -m helix3.keeper --watch "$INTERVAL" >> "$LOG" 2>&1 < /dev/null &
  echo "installed: the keeper starts at boot (crontab @reboot) and is running now (log: $LOG)"
fi
"$PY" -m helix3.keeper --list || true
