#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/heartbeat.py > data/autopilot_last_run.log 2>&1 || true
python3 scripts/owner_iteration.py >> data/autopilot_last_run.log 2>&1 || true
