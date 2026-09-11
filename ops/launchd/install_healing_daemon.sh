#!/bin/zsh
set -euo pipefail

# Install AlphaBrain CI/CD healing daemon & supervisor as per-user background launchd service.
PROJECT_DIR="${1:?usage: install_healing_daemon.sh /absolute/path/to/alphaBrain}"
PLIST_TEMPLATE="$PROJECT_DIR/ops/launchd/com.alphabrain.healing.plist.template"
LABEL="com.alphabrain.healing"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON_EXEC="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
CURRENT_USER="${USER:-$(id -un)}"

[[ "$PROJECT_DIR" = /* ]] || { echo "project path must be absolute" >&2; exit 2; }
[[ -x "$PYTHON_EXEC" ]] || { echo "missing project virtualenv at $PYTHON_EXEC" >&2; exit 2; }
[[ -f "$PLIST_TEMPLATE" ]] || { echo "missing launchd template at $PLIST_TEMPLATE" >&2; exit 2; }

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/AlphaBrain"
sed -e "s#^[[:space:]]*<string>/ABSOLUTE/PATH/TO/alphaBrain/.venv/bin/python</string>#    <string>$PYTHON_EXEC</string>#" \
    -e "s#^[[:space:]]*<key>WorkingDirectory</key><string>/ABSOLUTE/PATH/TO/alphaBrain</string>#  <key>WorkingDirectory</key><string>$PROJECT_DIR</string>#" \
    -e "s#WORKER_USER#$CURRENT_USER#g" "$PLIST_TEMPLATE" > "$TARGET"
chmod 600 "$TARGET"

# Validate plist before asking launchd to load it.
plutil -lint "$TARGET"

# Replace only this healing supervisor per-user service, preserving unrelated launch agents.
if [[ "${DRY_RUN:-false}" != "true" ]]; then
    launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$TARGET"
    launchctl kickstart -k "gui/$(id -u)/$LABEL"
    echo "installed $LABEL"
else
    echo "dry run completed for $LABEL"
fi
