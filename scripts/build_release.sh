#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LIMIT="${1:-300}"

echo "[build] checking X API access"
python3 "$ROOT/scripts/check_x_api_access.py" --output "$ROOT/data/x_api_access.json"

echo "[build] refreshing site data with limit=${LIMIT}"
bash "$ROOT/scripts/refresh_site_data.sh" "$LIMIT"

echo "[build] regenerating pages"
python3 "$ROOT/scripts/generate_content_pages.py"

echo "[build] rebuilding public signals"
python3 "$ROOT/scripts/update_public_signals.py"

echo "[build] validating artifacts"
python3 "$ROOT/scripts/validate_data_integrity.py"

echo "[build] done"
