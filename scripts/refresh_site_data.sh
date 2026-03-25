#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for env_file in "$ROOT/.env.local" "$ROOT/.env"; do
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    source "$env_file"
  fi
done

LIMIT="${1:-300}"
SLEEP_MS="${XAI_REFRESH_SLEEP_MS:-250}"
RJINA_WORKERS="${XAI_RJINA_WORKERS:-8}"
LOG_DIR="$ROOT/data"
STATUS_JSON="$ROOT/data/refresh_status.json"
X_API_CHECK_JSON="$ROOT/data/x_api_access.json"
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
    "x_realtime_mode": "unknown",
    "x_realtime_rows": 0,
    "x_fallback_rows": 0,
    "x_error_rows": 0,
    "x_realtime_verified": False,
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
        realtime_rows = 0
        fallback_rows = 0
        error_rows = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            source = str(row.get("source") or "")
            if source == "x_api_v2" and status == "ok":
                realtime_rows += 1
            elif source == "x_web_rjina" and status.startswith("ok"):
                fallback_rows += 1
            elif status and not status.startswith("ok"):
                error_rows += 1
        total = realtime_rows + fallback_rows + error_rows
        if total:
            if realtime_rows == total:
                payload["x_realtime_mode"] = "x_api_v2"
            elif fallback_rows == total:
                payload["x_realtime_mode"] = "fallback_only"
            elif realtime_rows and fallback_rows:
                payload["x_realtime_mode"] = "mixed"
            else:
                payload["x_realtime_mode"] = "partial"
        payload["x_realtime_rows"] = realtime_rows
        payload["x_fallback_rows"] = fallback_rows
        payload["x_error_rows"] = error_rows
        payload["x_realtime_verified"] = bool(total and realtime_rows == total)
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
X_API_STATUS="missing_token"
X_API_OK="false"
X_API_DETAIL="X_BEARER_TOKEN is not configured."

step "preflight X API access"
if [[ -n "$TOKEN" ]]; then
  run python3 "$ROOT/scripts/check_x_api_access.py" --output "$X_API_CHECK_JSON"
  X_API_STATUS="$(python3 - <<'PY' "$X_API_CHECK_JSON"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
print(str(data.get("status") or "unknown"))
PY
)"
  X_API_OK="$(python3 - <<'PY' "$X_API_CHECK_JSON"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
print("true" if bool(data.get("ok")) else "false")
PY
)"
  X_API_DETAIL="$(python3 - <<'PY' "$X_API_CHECK_JSON"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
print(str(data.get("detail") or "").replace("\n", " ")[:400])
PY
)"
else
  run python3 "$ROOT/scripts/check_x_api_access.py" --output "$X_API_CHECK_JSON"
fi

step "refresh graph scaffold"
run python3 "$ROOT/scripts/update_mitbunny_graph.py"

step "refresh engagement metrics"
if [[ -n "$TOKEN" && "$X_API_OK" == "true" ]]; then
  MODE="x_api_v2"
  run python3 "$ROOT/scripts/update_engagement_metrics.py" \
    --limit "$LIMIT" \
    --tweets-per-user 50 \
    --sleep-ms "$SLEEP_MS"
else
  MODE="rjina_fallback"
  printf "[refresh] X API unavailable (%s), using r.jina fallback without fake freshness\n" "$X_API_STATUS"
  run python3 -u "$ROOT/scripts/update_engagement_metrics.py" \
    --limit "$LIMIT" \
    --fallback-rjina \
    --workers "$RJINA_WORKERS" \
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

step "build public signals layer"
run python3 "$ROOT/scripts/update_public_signals.py"

step "validate build artifacts"
run python3 "$ROOT/scripts/validate_data_integrity.py"

write_status "ok" "$LIMIT" "$MODE" "$LIMIT" "refresh completed"

step "verify X realtime mode"
run python3 "$ROOT/scripts/verify_x_realtime.py" \
  --engagement "$ROOT/data/engagement_metrics.json" \
  --refresh-status "$ROOT/data/refresh_status.json" \
  --output "$ROOT/data/x_realtime_status.json"

step "attach X API preflight to refresh status"
python3 - <<'PY' "$STATUS_JSON" "$X_API_CHECK_JSON"
import json, sys
from pathlib import Path
status_path = Path(sys.argv[1])
check_path = Path(sys.argv[2])
status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
check = json.loads(check_path.read_text(encoding="utf-8")) if check_path.exists() else {}
status["x_api_access_status"] = str(check.get("status") or "unknown")
status["x_api_access_ok"] = bool(check.get("ok"))
status["x_api_access_detail"] = str(check.get("detail") or "")
if check.get("probe_user_id"):
    status["x_api_probe_user_id"] = str(check.get("probe_user_id") or "")
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
PY

printf "\n[refresh] done\n"
