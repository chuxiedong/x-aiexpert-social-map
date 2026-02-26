#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8765}"
BASE="http://127.0.0.1:${PORT}"

cd "$ROOT"
mkdir -p "$ROOT/data"

start_web() {
  nohup python3 -m http.server "$PORT" >"$ROOT/data/web_${PORT}.log" 2>&1 &
  echo $! > "$ROOT/data/web_${PORT}.pid"
}

start_autopilot() {
  nohup bash -lc 'cd "$0" && while true; do /bin/bash scripts/autopilot_cycle.sh; sleep 900; done' "$ROOT" >"$ROOT/data/autopilot_loop.log" 2>&1 &
  echo $! > "$ROOT/data/autopilot.pid"
}

WEB_OK=0
if curl -fsS --max-time 2 "$BASE/index.html" >/dev/null 2>&1; then
  WEB_OK=1
fi

if [[ "$WEB_OK" -eq 0 ]]; then
  start_web
  sleep 1
fi

AP_OK=0
if [[ -f "$ROOT/data/autopilot.pid" ]]; then
  APID=$(cat "$ROOT/data/autopilot.pid" || true)
  if [[ -n "${APID:-}" ]] && kill -0 "$APID" 2>/dev/null; then
    AP_OK=1
  fi
fi
if [[ "$AP_OK" -eq 0 ]]; then
  start_autopilot
  sleep 1
fi

"$ROOT/scripts/preflight_status.sh" "$PORT"
