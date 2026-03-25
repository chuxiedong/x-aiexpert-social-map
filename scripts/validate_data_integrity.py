#!/usr/bin/env python3
"""Validate refreshed data artifacts before publishing."""

from __future__ import annotations

import datetime as dt
import json
import re
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
    DATA / "domain_context.json",
    DATA / "topic_cloud.json",
    DATA / "public_signals.json",
    DATA / "heartbeat_status.json",
    ROOT / "index.html",
    ROOT / "insights.html",
    ROOT / "daily_briefing.html",
    ROOT / "daily_progress.html",
    ROOT / "poster.html",
    ROOT / "topics.html",
    ROOT / "public_signals.html",
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


def warn(msg: str) -> None:
    print(f"[validate] WARN: {msg}")


def ensure_recent(label: str, raw_ts: str, max_age_hours: int = 72) -> None:
    ts = parse_iso(raw_ts)
    if ts is None:
        fail(f"{label} missing/invalid timestamp: {raw_ts!r}")
    age = dt.datetime.now(dt.timezone.utc) - ts.astimezone(dt.timezone.utc)
    if age.total_seconds() > max_age_hours * 3600:
        fail(f"{label} is stale: {raw_ts} (age>{max_age_hours}h)")


def ensure_present_timestamp(label: str, raw_ts: str) -> None:
    ts = parse_iso(raw_ts)
    if ts is None:
        fail(f"{label} missing/invalid timestamp: {raw_ts!r}")


def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def find_dupes(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in values:
        key = normalize_text(raw)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return {k: v for k, v in counts.items() if v > 1}


def link_endpoint(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("handle") or "").strip().lower()
    return str(value or "").strip().lower()


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
    top_handles = [str(x.get("handle") or "").strip().lower() for x in experts]
    if any(not h for h in top_handles):
        fail("top300 contains empty handle")
    if len(set(top_handles)) != len(top_handles):
        fail("top300 contains duplicate handles")

    profiles = read_json(DATA / "profiles.json")
    profile_items = profiles.get("items") or []
    if len(profile_items) < 50:
        fail("profiles items unexpectedly low")
    ensure_present_timestamp("profiles.updated_at", str(profiles.get("updated_at", "")))
    ensure_recent("profiles.built_at", str(profiles.get("built_at", "")))
    profile_handles = [str(x.get("handle") or "").strip().lower() for x in profile_items]
    if any(not h for h in profile_handles):
        fail("profiles contains empty handle")
    if len(set(profile_handles)) != len(profile_handles):
        fail("profiles contains duplicate handles")

    insights = read_json(DATA / "daily_insights.json")
    insight_items = insights.get("items") or []
    if len(insight_items) < 1:
        fail("daily_insights items unexpectedly low")
    if len(insight_items) < 10:
        warn(f"daily_insights items low: {len(insight_items)}")
    ensure_present_timestamp("daily_insights.updated_at", str(insights.get("updated_at", "")))
    ensure_recent("daily_insights.built_at", str(insights.get("built_at", "")))
    generic_prefix = ("今日精髓：围绕", "today essence:")
    latest_zh = []
    for item in insight_items:
        handle = str(item.get("handle") or "").strip()
        if not handle:
            fail("daily_insights item missing handle")
        share_zh = str(item.get("latest_share_zh") or "").strip()
        share_en = str(item.get("latest_share_en") or "").strip()
        if not share_zh or not share_en:
            fail(f"daily_insights item missing latest_share text: @{handle}")
        if normalize_text(share_zh).startswith(generic_prefix[0]) or normalize_text(share_en).startswith(generic_prefix[1]):
            fail(f"daily_insights contains templated generic share text: @{handle}")
        if bool(item.get("has_today_tweet")):
            hottest = str(item.get("today_hottest_tweet_text") or "").strip()
            if not hottest:
                fail(f"daily_insights has_today_tweet=true but today_hottest_tweet_text missing: @{handle}")
        latest_zh.append(share_zh)
    dupes = find_dupes(latest_zh)
    if dupes:
        fail(f"daily_insights duplicate latest_share_zh detected: {len(dupes)} duplicated texts")

    briefing = read_json(DATA / "daily_briefing.json")
    briefing_items = briefing.get("items") or []
    briefing_count = len(briefing_items)
    if briefing_count < 1:
        warn("daily_briefing has 0 items (likely no same-day posts in current window)")
    elif briefing_count < 10:
        warn(f"daily_briefing items low: {briefing_count}")
    ensure_present_timestamp("daily_briefing.updated_at", str(briefing.get("updated_at", "")))
    ensure_recent("daily_briefing.built_at", str(briefing.get("built_at", "")))
    briefing_handles = [str(x.get("handle") or "").strip().lower() for x in briefing_items]
    if any(not h for h in briefing_handles):
        fail("daily_briefing contains empty handle")
    if len(set(briefing_handles)) != len(briefing_handles):
        fail("daily_briefing contains duplicate handles")

    progress = read_json(DATA / "daily_progress.json")
    if not str(progress.get("summary_zh", "")).strip():
        fail("daily_progress summary_zh missing")
    if len(progress.get("topic_rank") or []) < 1:
        fail("daily_progress topic_rank missing")
    ensure_present_timestamp("daily_progress.updated_at", str(progress.get("updated_at", "")))
    ensure_recent("daily_progress.built_at", str(progress.get("built_at", "")))

    domain_context = read_json(DATA / "domain_context.json")
    if not str(domain_context.get("domain_name_zh", "")).strip():
        fail("domain_context domain_name_zh missing")
    if not str(domain_context.get("site_title_en", "")).strip():
        fail("domain_context site_title_en missing")

    topic_cloud = read_json(DATA / "topic_cloud.json")
    ensure_present_timestamp("topic_cloud.updated_at", str(topic_cloud.get("updated_at", "")))
    ensure_recent("topic_cloud.built_at", str(topic_cloud.get("built_at", "")))
    if len(topic_cloud.get("topics") or []) < 1:
        fail("topic_cloud topics unexpectedly low")
    if len(topic_cloud.get("terms") or []) < 5:
        fail("topic_cloud terms unexpectedly low")

    public_signals = read_json(DATA / "public_signals.json")
    ensure_present_timestamp("public_signals.updated_at", str(public_signals.get("updated_at", "")))
    ensure_recent("public_signals.built_at", str(public_signals.get("built_at", "")))
    signal_topics = public_signals.get("topics") or []
    if len(signal_topics) < 3:
        fail("public_signals topics unexpectedly low")
    for item in signal_topics:
        if not str(item.get("id") or "").strip():
            fail("public_signals topic missing id")
        if not str(item.get("label") or "").strip():
            fail("public_signals topic missing label")
        if not isinstance(item.get("keywords") or [], list):
            fail("public_signals topic keywords invalid")

    heartbeat = read_json(DATA / "heartbeat_status.json")
    if heartbeat.get("status") != "ok":
        fail(f"heartbeat not ok: {heartbeat.get('status')}")

    graph_node_handles = {
        str(n.get("id") or "").strip().lower()
        for n in (graph.get("nodes") or [])
        if str(n.get("id") or "").strip()
    }
    graph_node_handles |= {
        str(n.get("handle") or "").strip().lower()
        for n in (graph.get("nodes") or [])
        if str(n.get("handle") or "").strip()
    }
    bad_links = 0
    for link in (graph.get("links") or []):
        s = link_endpoint(link.get("source"))
        t = link_endpoint(link.get("target"))
        if not s or not t or s not in graph_node_handles or t not in graph_node_handles:
            bad_links += 1
    if bad_links:
        fail(f"mitbunny_graph contains unresolved links: {bad_links}")

    print("[validate] OK: data integrity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
