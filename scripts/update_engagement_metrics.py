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
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOP300 = ROOT / "data" / "top300.json"
DEFAULT_OUTPUT = ROOT / "data" / "engagement_metrics.json"
R_JINA_PREFIX = "https://r.jina.ai/http://x.com/"


def _clean_line(s: str) -> str:
    s = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _pick_latest_share_from_markdown(md: str, handle: str) -> str:
    text = md or ""
    key = f"{handle}’s posts"
    idx = text.find(key)
    if idx == -1:
        idx = text.find("posts\n--------------")
    body = text[idx:] if idx != -1 else text
    lines = [_clean_line(x) for x in body.splitlines()]
    ban = {
        "",
        "Pinned",
        "Posts",
        "post",
        "posts",
        "Open X",
    }
    for ln in lines:
        lower = ln.lower()
        if ln in ban:
            continue
        if set(ln) <= {"-"}:
            continue
        if (
            lower.startswith("title:")
            or lower.startswith("url source:")
            or lower.startswith("published time:")
            or lower.startswith("markdown content:")
        ):
            continue
        if lower.endswith("/ x"):
            continue
        if lower.startswith("image ") or lower.startswith("![image"):
            continue
        if "don’t miss what’s happening" in lower or "don't miss what’s happening" in lower:
            continue
        if "people on x are the first to know" in lower:
            continue
        if "warning: this page maybe not yet fully loaded" in lower:
            continue
        if lower.startswith("click to follow "):
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}", ln):
            continue
        if ln.startswith("@"):
            continue
        if len(ln) < 24:
            continue
        return ln[:400]
    return ""


def fetch_latest_by_rjina(handle: str) -> dict:
    url = f"{R_JINA_PREFIX}{urllib.parse.quote(handle)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "x-ai-experts-viz/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        md = resp.read().decode("utf-8", "ignore")
    latest = _pick_latest_share_from_markdown(md, handle)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "posts_count": 1 if latest else 0,
        "comments_count": 0,
        "likes_count": 0,
        "reposts_count": 0,
        "quote_count": 0,
        "latest_tweet_id": "",
        "latest_tweet_text": latest,
        "latest_tweet_at": now,
        "has_today_tweet": bool(latest),
        "today_hottest_tweet_id": "",
        "today_hottest_tweet_text": latest,
        "today_hottest_tweet_at": now,
        "today_hottest_tweet_heat": 1.0 if latest else 0.0,
        "today_hottest_likes": 0,
        "today_hottest_reposts": 0,
        "today_hottest_replies": 0,
        "today_hottest_quotes": 0,
        "daily_tz": os.getenv("XAI_DAILY_TZ", "Asia/Shanghai"),
        "latest_tweet_url": f"https://x.com/{handle}",
        "today_hottest_tweet_url": f"https://x.com/{handle}",
    }


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
        "&tweet.fields=public_metrics,created_at,text"
    )
    payload = safe_api_get(url, bearer)
    tweets = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(tweets, list):
        tweets = []
    posts_count = len(tweets)
    comments_count = 0
    likes_count = 0
    reposts_count = 0
    quote_count = 0
    latest_tweet_id = ""
    latest_tweet_text = ""
    latest_tweet_at = ""
    daily_tz_name = os.getenv("XAI_DAILY_TZ", "Asia/Shanghai")
    try:
        daily_tz = ZoneInfo(daily_tz_name)
    except Exception:
        daily_tz = dt.timezone.utc
    now_local_date = dt.datetime.now(daily_tz).date()
    hottest_today: dict | None = None
    hottest_today_heat = -1.0
    for tw in tweets:
        if not isinstance(tw, dict):
            continue
        if not latest_tweet_id:
            latest_tweet_id = str(tw.get("id") or "")
            latest_tweet_text = str(tw.get("text") or "").strip()
            latest_tweet_at = str(tw.get("created_at") or "")
        pm = tw.get("public_metrics", {})
        if not isinstance(pm, dict):
            continue
        replies = int(pm.get("reply_count", 0) or 0)
        likes = int(pm.get("like_count", 0) or 0)
        reposts = int(pm.get("retweet_count", 0) or 0)
        quotes = int(pm.get("quote_count", 0) or 0)
        comments_count += replies
        likes_count += likes
        reposts_count += reposts
        quote_count += quotes

        created_raw = str(tw.get("created_at") or "")
        created_dt = None
        if created_raw:
            try:
                created_dt = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00")).astimezone(daily_tz)
            except Exception:
                created_dt = None
        if created_dt and created_dt.date() == now_local_date:
            heat = likes + reposts * 2.0 + replies * 1.2 + quotes * 1.5
            if heat > hottest_today_heat:
                hottest_today_heat = heat
                hottest_today = {
                    "id": str(tw.get("id") or ""),
                    "text": str(tw.get("text") or "").strip(),
                    "created_at": created_raw,
                    "heat": heat,
                    "likes": likes,
                    "reposts": reposts,
                    "replies": replies,
                    "quotes": quotes,
                }
    return {
        "posts_count": posts_count,
        "comments_count": comments_count,
        "likes_count": likes_count,
        "reposts_count": reposts_count,
        "quote_count": quote_count,
        "latest_tweet_id": latest_tweet_id,
        "latest_tweet_text": latest_tweet_text,
        "latest_tweet_at": latest_tweet_at,
        "has_today_tweet": bool(hottest_today),
        "today_hottest_tweet_id": str((hottest_today or {}).get("id") or ""),
        "today_hottest_tweet_text": str((hottest_today or {}).get("text") or ""),
        "today_hottest_tweet_at": str((hottest_today or {}).get("created_at") or ""),
        "today_hottest_tweet_heat": float((hottest_today or {}).get("heat") or 0.0),
        "today_hottest_likes": int((hottest_today or {}).get("likes") or 0),
        "today_hottest_reposts": int((hottest_today or {}).get("reposts") or 0),
        "today_hottest_replies": int((hottest_today or {}).get("replies") or 0),
        "today_hottest_quotes": int((hottest_today or {}).get("quotes") or 0),
        "daily_tz": daily_tz_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update engagement_metrics.json from X API")
    parser.add_argument("--top300", type=Path, default=DEFAULT_TOP300, help="top300 json path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="engagement output path")
    parser.add_argument("--limit", type=int, default=300, help="max handles")
    parser.add_argument("--tweets-per-user", type=int, default=50, help="max recent tweets per user")
    parser.add_argument("--sleep-ms", type=int, default=250, help="sleep between users in ms")
    parser.add_argument(
        "--fallback-rjina",
        action="store_true",
        help="fallback to r.jina.ai X page extraction when X API fails",
    )
    args = parser.parse_args()

    token = urllib.parse.unquote(os.getenv("X_BEARER_TOKEN", "").strip())
    if not token and not args.fallback_rjina:
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
                    "latest_tweet_url": f"https://x.com/{handle}/status/{agg.get('latest_tweet_id')}" if agg.get("latest_tweet_id") else "",
                    "today_hottest_tweet_url": f"https://x.com/{handle}/status/{agg.get('today_hottest_tweet_id')}" if agg.get("today_hottest_tweet_id") else "",
                    "window_days": 30,
                    "source": "x_api_v2",
                    "status": "ok",
                }
        except Exception as e:  # pragma: no cover
            if args.fallback_rjina:
                try:
                    agg = fetch_latest_by_rjina(handle)
                    row = {
                        "handle": handle,
                        **agg,
                        "window_days": 1,
                        "source": "x_web_rjina",
                        "status": "ok_fallback",
                    }
                except Exception as e2:  # pragma: no cover
                    row = {
                        "handle": handle,
                        "posts_count": 0,
                        "comments_count": 0,
                        "likes_count": 0,
                        "reposts_count": 0,
                        "window_days": 30,
                        "source": "x_web_rjina",
                        "status": f"error_fallback:{type(e2).__name__}",
                    }
            else:
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
        "source": "X API v2" if not args.fallback_rjina else "X API v2 + x.com realtime fallback via r.jina.ai",
        "tweets_per_user": max(5, min(100, args.tweets_per_user)),
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
