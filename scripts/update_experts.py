#!/usr/bin/env python3
"""Fetch AI experts from Feedspot X influencer page and export JSON for visualization."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://x.feedspot.com/artificial_intelligence_twitter_influencers/"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "experts.json"
DEFAULT_MANUAL_INPUT = Path(__file__).resolve().parents[1] / "data" / "manual_experts.json"
DEFAULT_HISTORY_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "history.json"

ENTRY_PATTERN = re.compile(
    r'alt="(?P<name>[^"]+)"[^>]*data-handle="@(?P<handle>[^"]+)"\s+data-url="(?P<url>[^"]+)".*?'
    r'<strong>Bio</strong>\s*(?P<bio>.*?)\s*<strong>Twitter Handle\s*</strong>\s*'
    r'<a class="ins_dhl"[^>]*>\s*@[^<]+</a>\s*'
    r'<span class="eng-outer-wrapper[^>]*>\s*<span><strong>Twitter Followers\s*</strong>\s*(?P<followers>[^<]+)</span>',
    re.S,
)
TAG_PATTERN = re.compile(r"<[^>]+>")

KEYWORD_CATEGORY = [
    ("AI创业", ["openai", "founder", "startup", "ceo", "entrepreneur"]),
    ("AI研究", ["professor", "research", "scientist", "deepmind", "stanford", "mit", "meta ai"]),
    ("机器人/强化学习", ["robot", "robotics", "reinforcement", "rl"]),
    ("AI媒体/评论", ["podcast", "journalist", "writer", "newsletter", "media"]),
    ("AI工程", ["engineer", "developer", "coding", "llm", "build", "agent"]),
]


def parse_followers(text: str) -> int:
    s = text.strip().upper().replace(",", "")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)([KMB])?$", s)
    if not m:
        digits = re.sub(r"[^0-9]", "", s)
        return int(digits) if digits else 0

    value = float(m.group(1))
    suffix = m.group(2)
    if suffix == "K":
        value *= 1_000
    elif suffix == "M":
        value *= 1_000_000
    elif suffix == "B":
        value *= 1_000_000_000
    return int(value)


def normalize_text(raw_html: str) -> str:
    text = TAG_PATTERN.sub(" ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def pick_category(name: str, bio: str) -> str:
    blob = f"{name} {bio}".lower()
    for category, kws in KEYWORD_CATEGORY:
        if any(k in blob for k in kws):
            return category
    return "AI综合"


def pick_tags(name: str, bio: str, category: str) -> list[str]:
    blob = f"{name} {bio}".lower()
    tags = [category]
    for kw, label in [
        ("openai", "OpenAI"),
        ("deepmind", "DeepMind"),
        ("meta", "Meta"),
        ("stanford", "Stanford"),
        ("robot", "机器人"),
        ("podcast", "Podcast"),
        ("llm", "LLM"),
        ("agent", "Agent"),
    ]:
        if kw in blob and label not in tags:
            tags.append(label)
    return tags[:4]


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def extract(html_text: str, limit: int) -> list[dict]:
    rows: list[dict] = []
    for m in ENTRY_PATTERN.finditer(html_text):
        name = normalize_text(m.group("name"))
        handle = normalize_text(m.group("handle")).lstrip("@")
        url = normalize_text(m.group("url"))
        bio = normalize_text(m.group("bio"))
        followers_label = normalize_text(m.group("followers"))
        followers = parse_followers(followers_label)
        category = pick_category(name, bio)
        rows.append(
            {
                "name": name,
                "handle": handle,
                "followers": followers,
                "followers_label": followers_label,
                "category": category,
                "tags": pick_tags(name, bio, category),
                "url": url,
                "bio": bio,
            }
        )

    rows.sort(key=lambda x: x["followers"], reverse=True)
    rows = rows[:limit]
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def build_payload(experts: list[dict]) -> dict:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "generated_at": now,
        "source_name": "Feedspot Top AI Influencers on X",
        "source_url": SOURCE_URL,
        "manual_merge": False,
        "total_collected": len(experts),
        "experts": experts,
    }


def make_snapshot(payload: dict) -> dict:
    experts = payload.get("experts", [])
    top = experts[0] if experts else {}
    total_followers = sum(int(x.get("followers", 0)) for x in experts)
    generated_at = payload.get("generated_at")
    date_key = generated_at[:10] if isinstance(generated_at, str) and len(generated_at) >= 10 else ""
    rank_map = {}
    for i, item in enumerate(experts, start=1):
        handle = str(item.get("handle", "")).strip().lower()
        if handle:
            rank_map[handle] = i
    return {
        "date": date_key,
        "generated_at": generated_at,
        "total_experts": len(experts),
        "total_followers": total_followers,
        "top_handle": top.get("handle"),
        "top_followers": int(top.get("followers", 0)) if top else 0,
        "rank_map": rank_map,
    }


def load_history(path: Path) -> dict:
    if not path.exists():
        return {"updated_at": None, "snapshots": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "snapshots": []}
    if not isinstance(data, dict):
        return {"updated_at": None, "snapshots": []}
    snaps = data.get("snapshots", [])
    if not isinstance(snaps, list):
        snaps = []
    return {"updated_at": data.get("updated_at"), "snapshots": snaps}


def append_history(history: dict, snapshot: dict, keep: int) -> dict:
    snaps = list(history.get("snapshots", []))
    snaps.append(snapshot)
    # Deduplicate identical timestamps if script reruns in same second.
    dedup = {}
    for s in snaps:
        key = str(s.get("generated_at", ""))
        dedup[key] = s
    snaps = sorted(dedup.values(), key=lambda x: str(x.get("generated_at", "")))
    if keep > 0 and len(snaps) > keep:
        snaps = snaps[-keep:]
    return {
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "snapshots": snaps,
    }


def build_daily_history(snapshots: list[dict], days: int) -> list[dict]:
    by_day: dict[str, dict] = {}
    for snap in snapshots:
        day = str(snap.get("date", ""))
        if not day:
            continue
        # Keep latest snapshot for each day.
        prev = by_day.get(day)
        if not prev or str(snap.get("generated_at", "")) > str(prev.get("generated_at", "")):
            by_day[day] = {
                "date": day,
                "generated_at": snap.get("generated_at"),
                "total_experts": int(snap.get("total_experts", 0)),
                "total_followers": int(snap.get("total_followers", 0)),
                "top_handle": snap.get("top_handle"),
                "top_followers": int(snap.get("top_followers", 0)),
            }
    rows = [by_day[d] for d in sorted(by_day.keys())]
    return rows[-max(1, days) :]


def build_rank_changes(experts: list[dict], snapshots: list[dict], limit: int) -> list[dict]:
    if len(snapshots) < 2:
        return []
    prev = snapshots[-2]
    prev_map = prev.get("rank_map", {}) if isinstance(prev.get("rank_map", {}), dict) else {}
    if not prev_map:
        return []
    rows = []
    for cur in experts[: max(1, limit)]:
        handle = str(cur.get("handle", "")).strip().lower()
        if not handle:
            continue
        cur_rank = int(cur.get("rank", 0))
        prev_rank = prev_map.get(handle)
        if prev_rank is None:
            delta = None
        else:
            prev_rank = int(prev_rank)
            delta = prev_rank - cur_rank
        rows.append(
            {
                "handle": cur.get("handle"),
                "name": cur.get("name"),
                "current_rank": cur_rank,
                "previous_rank": prev_rank,
                "delta": delta,
                "followers": int(cur.get("followers", 0)),
            }
        )
    return rows


def normalize_manual_expert(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    handle = str(raw.get("handle", "")).strip().lstrip("@")
    url = str(raw.get("url", "")).strip() or (f"https://x.com/{handle}" if handle else "")
    if not name or not handle:
        return None
    followers = raw.get("followers", 0)
    try:
        followers = int(followers)
    except Exception:
        followers = 0
    category = str(raw.get("category", "")).strip() or "AI综合"
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else [category]
    tags = [str(t).strip() for t in tags if str(t).strip()][:4] or [category]
    bio = str(raw.get("bio", "")).strip()
    return {
        "name": name,
        "handle": handle,
        "followers": max(0, followers),
        "followers_label": raw.get("followers_label") or str(max(0, followers)),
        "category": category,
        "tags": tags,
        "url": url,
        "bio": bio,
    }


def load_manual_experts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        print(f"manual file parse error: {err}", file=sys.stderr)
        return []
    if isinstance(payload, dict):
        items = payload.get("experts", [])
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    normalized = []
    for item in items:
        row = normalize_manual_expert(item)
        if row:
            normalized.append(row)
    return normalized


def merge_manual(experts: list[dict], manual: list[dict]) -> tuple[list[dict], int]:
    if not manual:
        return experts, 0
    by_handle = {x["handle"].lower(): dict(x) for x in experts}
    merged = 0
    for item in manual:
        key = item["handle"].lower()
        if key in by_handle:
            by_handle[key].update(item)
            merged += 1
        else:
            by_handle[key] = item
            merged += 1
    rows = sorted(by_handle.values(), key=lambda x: x["followers"], reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows, merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Update experts.json for X AI influencer visualization")
    parser.add_argument("--limit", type=int, default=300, help="Number of experts to export")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL_INPUT, help="Manual experts json path")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_OUTPUT, help="History json path")
    parser.add_argument("--history-keep", type=int, default=180, help="Max snapshots to keep in history")
    parser.add_argument("--history-tail", type=int, default=30, help="Tail snapshots embedded into experts json")
    parser.add_argument("--history-days", type=int, default=60, help="Daily aggregated history points")
    parser.add_argument("--rank-change-limit", type=int, default=15, help="How many top experts include rank change")
    args = parser.parse_args()

    html_text = fetch_html(SOURCE_URL)
    experts = extract(html_text, max(1, args.limit))
    if not experts:
        print("No experts parsed from source page.", file=sys.stderr)
        return 2

    manual_experts = load_manual_experts(args.manual)
    experts, merged_count = merge_manual(experts, manual_experts)
    experts = experts[: max(1, args.limit)]
    payload = build_payload(experts)
    payload["manual_merge"] = merged_count > 0
    payload["manual_source"] = str(args.manual) if merged_count > 0 else None
    payload["manual_merged_count"] = merged_count

    snapshot = make_snapshot(payload)
    history = load_history(args.history)
    history = append_history(history, snapshot, max(1, args.history_keep))
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    tail = history.get("snapshots", [])[-max(1, args.history_tail) :]
    payload["history_tail"] = tail
    payload["history_daily"] = build_daily_history(history.get("snapshots", []), max(1, args.history_days))
    payload["history_total_points"] = len(history.get("snapshots", []))
    payload["history_file"] = str(args.history)
    payload["rank_changes"] = build_rank_changes(
        experts,
        history.get("snapshots", []),
        max(1, args.rank_change_limit),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {args.output} with {len(experts)} experts.")
    print(f"Manual merged: {merged_count}")
    print(f"History points: {payload['history_total_points']}")
    print(f"Top: @{experts[0]['handle']} ({experts[0]['followers_label']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
