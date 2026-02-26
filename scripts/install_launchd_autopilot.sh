#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/ops/com.xai.experts.autopilot.plist"
DST="$HOME/Library/LaunchAgents/com.xai.experts.autopilot.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"
launchctl unload "$DST" >/dev/null 2>&1 || true
launchctl load "$DST"
launchctl list | grep com.xai.experts.autopilot || true
echo "installed: $DST"
