#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8765}"
BASE="http://127.0.0.1:${PORT}"

ok(){ printf "[OK] %s\n" "$1"; }
warn(){ printf "[WARN] %s\n" "$1"; }

cd "$ROOT"

if [[ -f "$ROOT/data/heartbeat_status.json" ]]; then
  ok "heartbeat_status.json exists"
else
  warn "heartbeat_status.json missing"
fi

if [[ -f "$ROOT/data/iteration_log.json" ]]; then
  ok "iteration_log.json exists"
else
  warn "iteration_log.json missing"
fi

if curl -fsS --max-time 2 "$BASE/index.html" >/dev/null 2>&1; then
  ok "web server reachable: $BASE"
else
  warn "web server not reachable: $BASE"
fi

if curl -fsS --max-time 2 "$BASE/progress.html" >/dev/null 2>&1; then
  ok "progress page reachable"
else
  warn "progress page not reachable"
fi

if [[ -f "$ROOT/data/web_8765.pid" ]]; then
  PID=$(cat "$ROOT/data/web_8765.pid" || true)
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    ok "web pid alive: $PID"
  else
    if curl -fsS --max-time 2 "$BASE/index.html" >/dev/null 2>&1; then
      ok "web reachable (pid file stale)"
    else
      warn "web pid file exists but process not alive"
    fi
  fi
else
  warn "web pid file missing"
fi

if [[ -f "$ROOT/data/autopilot.pid" ]]; then
  PID=$(cat "$ROOT/data/autopilot.pid" || true)
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    ok "autopilot pid alive: $PID"
  else
    warn "autopilot pid file exists but process not alive"
  fi
else
  warn "autopilot pid file missing"
fi
