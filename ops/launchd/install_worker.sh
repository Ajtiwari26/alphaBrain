#!/bin/zsh
set -euo pipefail

# Install AlphaBrain worker as per-user background launchd service after production preflight.
PROJECT_DIR="${1:?usage: install_worker.sh /absolute/path/to/alphaBrain}"
PLIST_TEMPLATE="$PROJECT_DIR/ops/launchd/com.deploymate.alphabrain.worker.plist.template"
LABEL="com.deploymate.alphabrain.worker"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

[[ "$PROJECT_DIR" = /* ]] || { echo "project path must be absolute" >&2; exit 2; }
[[ -x "$PROJECT_DIR/.venv/bin/python" ]] || { echo "missing project virtualenv" >&2; exit 2; }
[[ -f "$PLIST_TEMPLATE" ]] || { echo "missing launchd template" >&2; exit 2; }
[[ "${ENV:-development}" = production ]] || { echo "ENV=production required" >&2; exit 2; }
[[ "${WORKER_USE_KEYCHAIN:-false}" = true ]] || { echo "WORKER_USE_KEYCHAIN=true required" >&2; exit 2; }
[[ "${WORKER_ALLOW_LOCAL_DB:-true}" = false ]] || { echo "WORKER_ALLOW_LOCAL_DB=false required" >&2; exit 2; }

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/AlphaBrain"
sed -e "s#^  <string>/ABSOLUTE/PATH/TO/alphaBrain/.venv/bin/python</string>#  <string>$PROJECT_DIR/.venv/bin/python</string>#" \
    -e "s#^  <key>WorkingDirectory</key><string>/ABSOLUTE/PATH/TO/alphaBrain</string>#  <key>WorkingDirectory</key><string>$PROJECT_DIR</string>#" \
    -e "s#WORKER_USER#$USER#g" "$PLIST_TEMPLATE" > "$TARGET"
chmod 600 "$TARGET"

# Validate plist before asking launchd to load it.
plutil -lint "$TARGET"
# Replace only this worker's per-user service, preserving unrelated launch agents.
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
echo "installed $LABEL"
