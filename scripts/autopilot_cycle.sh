#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REFRESH_LIMIT="${XAI_AUTOPILOT_LIMIT:-50}"
ENABLE_REFRESH="${XAI_ENABLE_REFRESH:-1}"

if [[ "$ENABLE_REFRESH" == "1" ]]; then
  bash "$ROOT/scripts/refresh_site_data.sh" "$REFRESH_LIMIT" > data/autopilot_refresh.log 2>&1 || true
fi

python3 scripts/heartbeat.py > data/autopilot_last_run.log 2>&1 || true
python3 scripts/owner_iteration.py >> data/autopilot_last_run.log 2>&1 || true
