#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LIMIT="${1:-300}"
SLEEP_MS="${XAI_REFRESH_SLEEP_MS:-250}"
LOG_DIR="$ROOT/data"
STATUS_JSON="$ROOT/data/refresh_status.json"
mkdir -p "$LOG_DIR"

write_status() {
  python3 - "$STATUS_JSON" "$1" "$2" "$3" "$4" "$5" <<'PY'
import json, sys, datetime as dt
from pathlib import Path
path = Path(sys.argv[1])
payload = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "status": sys.argv[2],
    "limit": int(sys.argv[3]),
    "mode": sys.argv[4],
    "refreshed_handles": int(sys.argv[5]),
    "note": sys.argv[6],
    "content_updated_at": "",
    "source_crawled_at": "",
    "built_at": "",
}
daily = path.parent / "daily_progress.json"
eng = path.parent / "engagement_metrics.json"
if daily.exists():
    try:
        data = json.loads(daily.read_text(encoding="utf-8"))
        payload["content_updated_at"] = str(data.get("updated_at") or "")
        payload["built_at"] = str(data.get("built_at") or "")
    except Exception:
        pass
if eng.exists():
    try:
        data = json.loads(eng.read_text(encoding="utf-8"))
        rows = data.get("metrics") or []
        vals = [str(x.get("latest_crawled_at") or "").strip() for x in rows if isinstance(x, dict)]
        vals = [v for v in vals if v]
        payload["source_crawled_at"] = max(vals) if vals else str(data.get("updated_at") or "")
    except Exception:
        pass
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

step() {
  printf "\n[refresh] %s\n" "$1"
}

run() {
  printf "[refresh] cmd: %s\n" "$*"
  "$@"
}

TOKEN="${X_BEARER_TOKEN:-}"

step "refresh graph scaffold"
run python3 "$ROOT/scripts/update_mitbunny_graph.py"

step "refresh engagement metrics"
if [[ -n "$TOKEN" ]]; then
  MODE="x_api_v2"
  run python3 "$ROOT/scripts/update_engagement_metrics.py" \
    --limit "$LIMIT" \
    --tweets-per-user 50 \
    --sleep-ms "$SLEEP_MS"
else
  MODE="rjina_fallback"
  printf "[refresh] no X_BEARER_TOKEN found, using r.jina fallback without fake freshness\n"
  run python3 "$ROOT/scripts/update_engagement_metrics.py" \
    --limit "$LIMIT" \
    --fallback-rjina \
    --sleep-ms 0
fi

step "rebuild ranking with latest engagement map"
run python3 "$ROOT/scripts/update_mitbunny_graph.py"

step "refresh expert profiles"
if [[ -n "$TOKEN" ]]; then
  run python3 "$ROOT/scripts/update_experts.py" \
    --limit "$LIMIT" \
    --sleep-ms "$SLEEP_MS"
else
  printf "[refresh] no X_BEARER_TOKEN found, skip update_experts.py and keep existing experts.json\n"
fi

step "generate content pages"
run python3 "$ROOT/scripts/generate_content_pages.py"

step "validate build artifacts"
run python3 "$ROOT/scripts/validate_data_integrity.py"

write_status "ok" "$LIMIT" "$MODE" "$LIMIT" "refresh completed"
printf "\n[refresh] done\n"
