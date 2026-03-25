#!/usr/bin/env python3
"""Build public signal fallback data for the Public Signals page."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOPIC_CLOUD = DATA / "topic_cloud.json"
DOMAIN_CONTEXT = DATA / "domain_context.json"
DOMAIN_CONFIG = DATA / "domain_config.json"
OUTPUT = DATA / "public_signals.json"


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if part) or "topic"


def taxonomy_map(domain: dict) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for item in domain.get("topic_taxonomy") or []:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        keywords = [str(x).strip() for x in item.get("keywords") or [] if str(x).strip()]
        if topic:
            mapping[topic] = keywords
    return mapping


def build_github_query(topic: str, keywords: list[str], domain_name: str) -> str:
    terms = keywords[:3] if keywords else topic.split()[:3]
    quoted = [f'"{term}"' for term in terms if term]
    core = " OR ".join(quoted) if quoted else f'"{topic}"'
    if domain_name and domain_name.lower() not in topic.lower():
        core = f"({core}) \"{domain_name}\""
    return f"{core} stars:>50"


def fetch_github_preview(query: str, per_page: int = 3) -> dict:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": str(per_page),
        }
    )
    url = f"https://api.github.com/search/repositories?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "x-ai-experts-viz/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl.create_default_context()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items = []
        for item in (payload.get("items") or [])[:per_page]:
            items.append(
                {
                    "full_name": str(item.get("full_name") or ""),
                    "url": str(item.get("html_url") or ""),
                    "stars": int(item.get("stargazers_count") or 0),
                    "description": str(item.get("description") or "").strip(),
                    "updated_at": str(item.get("pushed_at") or item.get("updated_at") or ""),
                }
            )
        return {
            "status": "ok",
            "queried_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repo_count": int(payload.get("total_count") or 0),
            "items": items,
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "queried_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repo_count": 0,
            "items": [],
            "error": str(exc),
        }


def build_payload(max_topics: int) -> dict:
    topic_cloud = read_json(TOPIC_CLOUD, {})
    ctx = read_json(DOMAIN_CONTEXT, {})
    domain = read_json(DOMAIN_CONFIG, {})
    taxonomy = taxonomy_map(domain)
    topic_rows = (topic_cloud.get("topics") or [])[:max_topics]
    max_count = max([int(row.get("count") or 0) for row in topic_rows] + [1])
    domain_name_en = str(ctx.get("domain_name_en") or domain.get("domain_name_en") or "AI")
    domain_name_zh = str(ctx.get("domain_name_zh") or domain.get("domain_name_zh") or "AI")
    sample_pool = str(ctx.get("sample_pool_label_zh") or "X 领域博主")

    topics = []
    for index, row in enumerate(topic_rows, start=1):
        label = str(row.get("topic") or "").strip()
        if not label:
            continue
        keywords = taxonomy.get(label) or label.split()
        query = build_github_query(label, keywords, domain_name_en)
        github = fetch_github_preview(query)
        people = row.get("people") or []
        count = int(row.get("count") or 0)
        creator_count = len(people)
        topics.append(
            {
                "id": slugify(label),
                "rank": index,
                "label": label,
                "count": count,
                "creator_count": creator_count,
                "people": people[:8],
                "keywords": keywords[:6],
                "x_signal_score": round(count / max_count, 4),
                "local_summary_zh": f"在当前 {sample_pool} 中，{label} 相关讨论出现 {count} 次，关联人物 {creator_count} 位。",
                "local_summary_en": f"Within the current {ctx.get('sample_pool_label_en') or 'domain creator pool'}, {label} appears {count} times across {creator_count} linked creators.",
                "github": {
                    "query": query,
                    **github,
                },
                "live_sources": {
                    "github": "browser_and_build",
                    "hackernews": "browser_live",
                    "wikipedia": "browser_live",
                },
            }
        )

    return {
        "updated_at": str(topic_cloud.get("updated_at") or ""),
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "domain": {
            "slug": str(ctx.get("slug") or "ai"),
            "domain_name_zh": domain_name_zh,
            "domain_name_en": domain_name_en,
            "site_title_zh": str(ctx.get("site_title_zh") or "领域社交影响力情报台"),
            "site_title_en": str(ctx.get("site_title_en") or "Domain Influence Intelligence"),
            "platform_name": str(ctx.get("platform_name") or "X"),
        },
        "summary_zh": f"这页把 {domain_name_zh} 领域在 X 上的热点，叠加到开源社区、跨平台讨论和百科解释层，帮助你判断哪些话题只是站内热，哪些已经外溢成公共信号。",
        "summary_en": f"This page layers open-source momentum, cross-platform discussion, and public explainers onto the hottest {domain_name_en} topics on X so you can spot what is only hot inside X versus what is turning into a broader signal.",
        "source_catalog": [
            {
                "name": "GitHub Search API",
                "role_zh": "开源动向",
                "role_en": "Open-source momentum",
                "mode": "build_optional + browser_live",
            },
            {
                "name": "Hacker News API",
                "role_zh": "跨平台讨论",
                "role_en": "Cross-platform discussion",
                "mode": "browser_live",
            },
            {
                "name": "Wikipedia Search API",
                "role_zh": "热点解释",
                "role_en": "Topic explainers",
                "mode": "browser_live",
            },
        ],
        "topics": topics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-topics", type=int, default=6)
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    payload = build_payload(max_topics=max(3, min(args.max_topics, 12)))
    out = Path(args.output)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"built public signals -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
