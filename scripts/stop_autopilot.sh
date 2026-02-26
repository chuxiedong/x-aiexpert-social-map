#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/data/autopilot.pid"
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "stopped $PID"
  else
    echo "process not running: $PID"
  fi
else
  echo "autopilot pid not found"
fi
