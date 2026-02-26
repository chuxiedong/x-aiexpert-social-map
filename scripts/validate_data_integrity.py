#!/usr/bin/env python3
"""Validate refreshed data artifacts before publishing."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

REQUIRED_FILES = [
    DATA / "mitbunny_graph.json",
    DATA / "top300.json",
    DATA / "profiles.json",
    DATA / "daily_insights.json",
    DATA / "daily_briefing.json",
    DATA / "daily_progress.json",
    DATA / "heartbeat_status.json",
    ROOT / "index.html",
    ROOT / "insights.html",
    ROOT / "daily_briefing.html",
    ROOT / "daily_progress.html",
    ROOT / "poster.html",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(ts: str) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def fail(msg: str) -> None:
    print(f"[validate] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def ensure_recent(label: str, raw_ts: str, max_age_hours: int = 72) -> None:
    ts = parse_iso(raw_ts)
    if ts is None:
        fail(f"{label} missing/invalid timestamp: {raw_ts!r}")
    age = dt.datetime.now(dt.timezone.utc) - ts.astimezone(dt.timezone.utc)
    if age.total_seconds() > max_age_hours * 3600:
        fail(f"{label} is stale: {raw_ts} (age>{max_age_hours}h)")


def main() -> int:
    for p in REQUIRED_FILES:
        if not p.exists() or p.stat().st_size <= 0:
            fail(f"missing or empty file: {p.relative_to(ROOT)}")

    graph = read_json(DATA / "mitbunny_graph.json")
    if int(graph.get("total_nodes", 0)) < 50:
        fail("mitbunny_graph total_nodes unexpectedly low")
    if int(graph.get("total_links", 0)) < 50:
        fail("mitbunny_graph total_links unexpectedly low")
    top300 = graph.get("top300") or []
    if len(top300) < 50:
        fail("mitbunny_graph top300 unexpectedly low")
    ensure_recent("mitbunny_graph.generated_at", str(graph.get("generated_at", "")))

    ranking = read_json(DATA / "top300.json")
    experts = ranking.get("experts") or []
    if len(experts) < 50:
        fail("top300 experts unexpectedly low")
    ensure_recent("top300.generated_at", str(ranking.get("generated_at", "")))

    profiles = read_json(DATA / "profiles.json")
    profile_items = profiles.get("items") or []
    if len(profile_items) < 50:
        fail("profiles items unexpectedly low")
    ensure_recent("profiles.updated_at", str(profiles.get("updated_at", "")))

    insights = read_json(DATA / "daily_insights.json")
    if len(insights.get("items") or []) < 10:
        fail("daily_insights items unexpectedly low")
    ensure_recent("daily_insights.updated_at", str(insights.get("updated_at", "")))

    briefing = read_json(DATA / "daily_briefing.json")
    if len(briefing.get("items") or []) < 10:
        fail("daily_briefing items unexpectedly low")
    ensure_recent("daily_briefing.updated_at", str(briefing.get("updated_at", "")))

    progress = read_json(DATA / "daily_progress.json")
    if not str(progress.get("summary_zh", "")).strip():
        fail("daily_progress summary_zh missing")
    if len(progress.get("topic_rank") or []) < 1:
        fail("daily_progress topic_rank missing")
    ensure_recent("daily_progress.updated_at", str(progress.get("updated_at", "")))

    heartbeat = read_json(DATA / "heartbeat_status.json")
    if heartbeat.get("status") != "ok":
        fail(f"heartbeat not ok: {heartbeat.get('status')}")

    print("[validate] OK: data integrity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
