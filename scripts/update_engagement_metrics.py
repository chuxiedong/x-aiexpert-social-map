#!/usr/bin/env python3
"""Fetch X engagement metrics for handles and write engagement_metrics.json.

Requires:
  - X_BEARER_TOKEN environment variable (X API v2)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOP300 = ROOT / "data" / "top300.json"
DEFAULT_OUTPUT = ROOT / "data" / "engagement_metrics.json"


def api_get(url: str, bearer: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer}",
            "User-Agent": "x-ai-experts-viz/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def parse_reset_seconds(headers: dict) -> int:
    reset = headers.get("x-rate-limit-reset")
    if not reset:
        return 30
    try:
        reset_ts = int(reset)
    except Exception:
        return 30
    now = int(time.time())
    return max(5, reset_ts - now + 1)


def safe_api_get(url: str, bearer: str, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            return api_get(url, bearer)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = parse_reset_seconds(dict(e.headers.items()))
                time.sleep(wait)
                continue
            if i == retries - 1:
                raise
            time.sleep(2 + i)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 + i)
    raise RuntimeError("safe_api_get failed")


def load_handles(top300_path: Path, limit: int) -> list[str]:
    data = json.loads(top300_path.read_text(encoding="utf-8"))
    rows = data.get("experts") or data.get("top300") or []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        h = str(row.get("handle") or "").strip().lstrip("@")
        if not h:
            continue
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(h)
        if limit > 0 and len(out) >= limit:
            break
    return out


def lookup_user_id(handle: str, bearer: str) -> str | None:
    encoded = urllib.parse.quote(handle)
    url = f"https://api.twitter.com/2/users/by/username/{encoded}?user.fields=public_metrics"
    payload = safe_api_get(url, bearer)
    user = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        return None
    uid = user.get("id")
    return str(uid) if uid else None


def fetch_user_tweets_metrics(user_id: str, bearer: str, max_results: int) -> dict:
    url = (
        f"https://api.twitter.com/2/users/{user_id}/tweets"
        f"?max_results={max(5, min(100, max_results))}"
        "&exclude=replies,retweets"
        "&tweet.fields=public_metrics,created_at"
    )
    payload = safe_api_get(url, bearer)
    tweets = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(tweets, list):
        tweets = []
    posts_count = len(tweets)
    comments_count = 0
    likes_count = 0
    reposts_count = 0
    for tw in tweets:
        if not isinstance(tw, dict):
            continue
        pm = tw.get("public_metrics", {})
        if not isinstance(pm, dict):
            continue
        comments_count += int(pm.get("reply_count", 0) or 0)
        likes_count += int(pm.get("like_count", 0) or 0)
        reposts_count += int(pm.get("retweet_count", 0) or 0)
    return {
        "posts_count": posts_count,
        "comments_count": comments_count,
        "likes_count": likes_count,
        "reposts_count": reposts_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update engagement_metrics.json from X API")
    parser.add_argument("--top300", type=Path, default=DEFAULT_TOP300, help="top300 json path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="engagement output path")
    parser.add_argument("--limit", type=int, default=300, help="max handles")
    parser.add_argument("--tweets-per-user", type=int, default=50, help="max recent tweets per user")
    parser.add_argument("--sleep-ms", type=int, default=250, help="sleep between users in ms")
    args = parser.parse_args()

    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        raise SystemExit("Missing X_BEARER_TOKEN")

    handles = load_handles(args.top300, args.limit)
    if not handles:
        raise SystemExit("No handles found")

    metrics = []
    for i, handle in enumerate(handles, start=1):
        try:
            uid = lookup_user_id(handle, token)
            if not uid:
                row = {
                    "handle": handle,
                    "posts_count": 0,
                    "comments_count": 0,
                    "likes_count": 0,
                    "reposts_count": 0,
                    "window_days": 30,
                    "source": "x_api_v2",
                    "status": "user_not_found",
                }
            else:
                agg = fetch_user_tweets_metrics(uid, token, args.tweets_per_user)
                row = {
                    "handle": handle,
                    **agg,
                    "window_days": 30,
                    "source": "x_api_v2",
                    "status": "ok",
                }
        except Exception as e:  # pragma: no cover
            row = {
                "handle": handle,
                "posts_count": 0,
                "comments_count": 0,
                "likes_count": 0,
                "reposts_count": 0,
                "window_days": 30,
                "source": "x_api_v2",
                "status": f"error:{type(e).__name__}",
            }
        metrics.append(row)
        print(f"[{i}/{len(handles)}] {handle} -> {row['status']}")
        time.sleep(max(0, args.sleep_ms) / 1000.0)

    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "description": "X engagement metrics per account, used by quanzhong model",
        "source": "X API v2",
        "tweets_per_user": max(5, min(100, args.tweets_per_user)),
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

