#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "heartbeat_status.json"
ITER_LOG = DATA / "iteration_log.json"

CHECK_FILES = [
    ROOT / "index.html",
    ROOT / "data" / "circle_layers.html",
    ROOT / "insights.html",
    ROOT / "daily_briefing.html",
    ROOT / "daily_progress.html",
    ROOT / "poster.html",
    ROOT / "contact.html",
    ROOT / "commercial.html",
    ROOT / "ops.html",
    ROOT / "data" / "profiles.json",
    ROOT / "data" / "daily_insights.json",
    ROOT / "data" / "daily_briefing.json",
    ROOT / "data" / "daily_progress.json",
]


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    build_code, build_out = run([sys.executable, str(ROOT / "scripts" / "generate_content_pages.py")])

    checks = []
    for f in CHECK_FILES:
      exists = f.exists()
      size = f.stat().st_size if exists else 0
      checks.append({"file": str(f.relative_to(ROOT)), "exists": exists, "size": size})

    missing = [c["file"] for c in checks if not c["exists"]]
    status = "ok" if build_code == 0 and not missing else "degraded"

    payload = {
        "generated_at": generated_at,
        "status": status,
        "build_result": "ok" if build_code == 0 else "failed",
        "build_log": build_out[-2000:],
        "missing": missing,
        "checks": checks,
        "duration_ms": int((time.time() - t0) * 1000),
        "iteration_note": "heartbeat rebuild + integrity checks",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Append visible iteration timeline for progress page.
    if ITER_LOG.exists():
        try:
            hist = json.loads(ITER_LOG.read_text(encoding="utf-8"))
            if not isinstance(hist, list):
                hist = []
        except Exception:
            hist = []
    else:
        hist = []
    hist.append(
        {
            "ts": generated_at,
            "status": status,
            "build_result": payload["build_result"],
            "duration_ms": payload["duration_ms"],
            "missing_count": len(missing),
            "checks_count": len(checks),
            "note": payload["iteration_note"],
        }
    )
    ITER_LOG.write_text(json.dumps(hist[-300:], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "missing": len(missing)}, ensure_ascii=False))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
