#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INTERVAL="${1:-900}"
nohup bash -lc 'while true; do /bin/bash "'$ROOT'/scripts/autopilot_cycle.sh"; sleep "'$INTERVAL'"; done' \
  > "$ROOT/data/autopilot_loop.log" 2>&1 &
echo $! > "$ROOT/data/autopilot.pid"
echo "started PID $(cat "$ROOT/data/autopilot.pid") interval=${INTERVAL}s"
