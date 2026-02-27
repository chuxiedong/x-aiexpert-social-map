#!/usr/bin/env python3
"""Fetch AI experts from X API and export experts.json for visualization."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOP300_INPUT = DEFAULT_ROOT / "data" / "top300.json"
DEFAULT_GRAPH_INPUT = DEFAULT_ROOT / "data" / "mitbunny_graph.json"
DEFAULT_OUTPUT = DEFAULT_ROOT / "data" / "experts.json"
DEFAULT_MANUAL_INPUT = DEFAULT_ROOT / "data" / "manual_experts.json"
DEFAULT_HISTORY_OUTPUT = DEFAULT_ROOT / "data" / "history.json"

SOURCE_URL = "https://developer.x.com/en/docs/twitter-api/users/lookup/api-reference/get-users-by"

KEYWORD_CATEGORY = [
    ("AI创业", ["founder", "startup", "ceo", "builder", "product"]),
    ("AI研究", ["research", "scientist", "professor", "lab", "phd", "deepmind"]),
    ("机器人/强化学习", ["robot", "robotics", "reinforcement", "rl"]),
    ("AI媒体/评论", ["podcast", "journalist", "writer", "newsletter", "media"]),
    ("AI工程", ["engineer", "developer", "llm", "agent", "infra", "open source"]),
]


def safe_api_get(url: str, bearer: str, retries: int = 4) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer}",
            "User-Agent": "x-ai-experts-viz/1.0",
        },
    )
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset = e.headers.get("x-rate-limit-reset")
                wait = 30
                if reset:
                    try:
                        wait = max(5, int(reset) - int(time.time()) + 1)
                    except Exception:
                        wait = 30
                time.sleep(wait)
                continue
            if i == retries - 1:
                raise
            time.sleep(2 + i)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 + i)
    raise RuntimeError("x api request failed")


def normalize_handle(raw: str) -> str:
    return str(raw or "").strip().lstrip("@")


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
        ("anthropic", "Anthropic"),
        ("nvidia", "NVIDIA"),
        ("robot", "机器人"),
        ("podcast", "Podcast"),
        ("llm", "LLM"),
        ("agent", "Agent"),
    ]:
        if kw in blob and label not in tags:
            tags.append(label)
    return tags[:6]


def followers_label(n: int) -> str:
    n = int(max(0, n))
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def load_handles_from_top300(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("experts") or data.get("top300") or []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        h = normalize_handle(row.get("handle") if isinstance(row, dict) else "")
        if not h:
            continue
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def load_handles_from_graph(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("top300") or data.get("nodes") or []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        h = normalize_handle(row.get("handle") or row.get("id"))
        if not h:
            continue
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def lookup_users_batch(handles: list[str], bearer: str) -> dict[str, dict]:
    if not handles:
        return {}
    qs = ",".join(urllib.parse.quote(h) for h in handles)
    url = (
        "https://api.twitter.com/2/users/by"
        f"?usernames={qs}"
        "&user.fields=description,profile_image_url,public_metrics,verified,location,url,created_at"
    )
    payload = safe_api_get(url, bearer)
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data if isinstance(data, list) else []
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        u = normalize_handle(row.get("username"))
        if not u:
            continue
        out[u.lower()] = row
    return out


def build_experts(handles: list[str], bearer: str, sleep_ms: int) -> list[dict]:
    rows: list[dict] = []
    chunk = 100
    for i in range(0, len(handles), chunk):
        batch = handles[i : i + chunk]
        data_map = lookup_users_batch(batch, bearer)
        for h in batch:
            row = data_map.get(h.lower(), {})
            name = str(row.get("name") or h)
            bio = str(row.get("description") or "").strip()
            pm = row.get("public_metrics", {}) if isinstance(row.get("public_metrics"), dict) else {}
            followers = int(pm.get("followers_count", 0) or 0)
            category = pick_category(name, bio)
            rows.append(
                {
                    "name": name,
                    "handle": h,
                    "followers": followers,
                    "followers_label": followers_label(followers),
                    "category": category,
                    "tags": pick_tags(name, bio, category),
                    "url": f"https://x.com/{h}",
                    "bio": bio,
                    "verified": bool(row.get("verified", False)),
                    "location": str(row.get("location") or ""),
                    "profile_image_url": str(row.get("profile_image_url") or ""),
                    "source": "x_api_v2",
                    "status": "ok" if row else "user_not_found",
                }
            )
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
    rows.sort(key=lambda x: int(x.get("followers", 0)), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def normalize_manual_expert(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    handle = normalize_handle(raw.get("handle", ""))
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
    tags = [str(t).strip() for t in tags if str(t).strip()][:6] or [category]
    bio = str(raw.get("bio", "")).strip()
    return {
        "name": name,
        "handle": handle,
        "followers": max(0, followers),
        "followers_label": raw.get("followers_label") or followers_label(max(0, followers)),
        "category": category,
        "tags": tags,
        "url": url,
        "bio": bio,
        "source": "manual",
        "status": "ok",
    }


def load_manual_experts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("experts", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        row = normalize_manual_expert(item)
        if row:
            out.append(row)
    return out


def merge_manual(experts: list[dict], manual: list[dict]) -> tuple[list[dict], int]:
    if not manual:
        return experts, 0
    by_handle = {str(x.get("handle", "")).lower(): dict(x) for x in experts}
    merged = 0
    for item in manual:
        key = str(item.get("handle", "")).lower()
        if not key:
            continue
        if key in by_handle:
            by_handle[key].update(item)
            merged += 1
        else:
            by_handle[key] = item
            merged += 1
    rows = sorted(by_handle.values(), key=lambda x: int(x.get("followers", 0)), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows, merged


def build_payload(experts: list[dict], input_handles: int) -> dict:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "generated_at": now,
        "source_name": "X API v2 users lookup",
        "source_url": SOURCE_URL,
        "manual_merge": False,
        "total_requested_handles": input_handles,
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
        delta = None if prev_rank is None else (int(prev_rank) - cur_rank)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Update experts.json from X API users lookup")
    parser.add_argument("--limit", type=int, default=300, help="max experts")
    parser.add_argument("--top300-input", type=Path, default=DEFAULT_TOP300_INPUT, help="top300.json path")
    parser.add_argument("--graph-input", type=Path, default=DEFAULT_GRAPH_INPUT, help="mitbunny_graph.json path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output path")
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL_INPUT, help="manual experts path")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_OUTPUT, help="history path")
    parser.add_argument("--history-keep", type=int, default=180, help="max snapshots to keep")
    parser.add_argument("--history-tail", type=int, default=30, help="tail snapshots embedded into experts.json")
    parser.add_argument("--history-days", type=int, default=60, help="daily aggregated history points")
    parser.add_argument("--rank-change-limit", type=int, default=15, help="top rank change count")
    parser.add_argument("--sleep-ms", type=int, default=250, help="sleep between API batches")
    args = parser.parse_args()

    token = urllib.parse.unquote(os.getenv("X_BEARER_TOKEN", "").strip())
    if not token:
        raise SystemExit("Missing X_BEARER_TOKEN: update_experts.py only supports X API source")

    limit = max(1, args.limit)
    handles = load_handles_from_top300(args.top300_input, limit)
    if not handles:
        handles = load_handles_from_graph(args.graph_input, limit)
    if not handles:
        raise SystemExit("No handles found from top300.json/mitbunny_graph.json")

    experts = build_experts(handles, token, max(0, args.sleep_ms))
    manual_experts = load_manual_experts(args.manual)
    experts, merged_count = merge_manual(experts, manual_experts)
    experts = experts[:limit]

    payload = build_payload(experts, input_handles=len(handles))
    payload["manual_merge"] = merged_count > 0
    payload["manual_source"] = str(args.manual) if merged_count > 0 else None
    payload["manual_merged_count"] = merged_count

    snapshot = make_snapshot(payload)
    history = load_history(args.history)
    history = append_history(history, snapshot, max(1, args.history_keep))
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    payload["history_tail"] = history.get("snapshots", [])[-max(1, args.history_tail) :]
    payload["history_daily"] = build_daily_history(history.get("snapshots", []), max(1, args.history_days))
    payload["history_total_points"] = len(history.get("snapshots", []))
    payload["history_file"] = str(args.history)
    payload["rank_changes"] = build_rank_changes(
        experts, history.get("snapshots", []), max(1, args.rank_change_limit)
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {args.output} with {len(experts)} experts (X API source).")
    print(f"Manual merged: {merged_count}")
    print(f"History points: {payload['history_total_points']}")
    if experts:
        print(f"Top: @{experts[0]['handle']} ({experts[0]['followers_label']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
