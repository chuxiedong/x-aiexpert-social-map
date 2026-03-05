#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8765}"

echo "[mather] project: $ROOT"
echo "[mather] step1: ensure runtime"
"$ROOT/scripts/ensure_runtime.sh" "$PORT"

echo "[mather] step2: integrity validation"
python3 "$ROOT/scripts/validate_data_integrity.py"

echo "[mather] step3: preflight summary"
"$ROOT/scripts/preflight_status.sh" "$PORT"

echo "[mather] done"
