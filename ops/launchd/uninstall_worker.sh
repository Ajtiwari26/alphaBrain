#!/bin/zsh
set -euo pipefail

# Remove only AlphaBrain worker launchd service and its user-owned plist.
LABEL="com.deploymate.alphabrain.worker"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
if [[ -f "$TARGET" ]]; then
  mv "$TARGET" "$TARGET.removed.$(date +%Y%m%d%H%M%S)"
fi
echo "removed $LABEL; prior plist retained with timestamp suffix"
