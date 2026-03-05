#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS=(8765 8876)

kill_port() {
  local p="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti "tcp:${p}" 2>/dev/null || true)
    if [[ -n "${pids:-}" ]]; then
      echo "$pids" | xargs -n 1 kill >/dev/null 2>&1 || true
      sleep 1
    fi
  fi
}

start_port() {
  local p="$1"
  (
    cd "$ROOT"
    nohup python3 -m http.server "$p" >"$ROOT/data/web_${p}.log" 2>&1 &
    echo $! > "$ROOT/data/web_${p}.pid"
  )
}

for p in "${PORTS[@]}"; do
  kill_port "$p"
  start_port "$p"
  sleep 1
  curl -fsS --max-time 3 "http://127.0.0.1:${p}/index.html" >/dev/null
  curl -fsS --max-time 3 "http://127.0.0.1:${p}/progress.html" >/dev/null
  echo "[OK] web started on ${p} (pid $(cat "$ROOT/data/web_${p}.pid"))"
done
