#!/usr/bin/env python3
"""Generate commercial-ready influencer pages, insights, and daily briefing."""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "mitbunny_graph.json"
PROFILE_JSON = ROOT / "data" / "profiles.json"
INSIGHTS_JSON = ROOT / "data" / "daily_insights.json"
BRIEFING_JSON = ROOT / "data" / "daily_briefing.json"
DAILY_PROGRESS_JSON = ROOT / "data" / "daily_progress.json"
DOMAIN_CONFIG_PATH = ROOT / "data" / "domain_config.json"
DOMAIN_CONTEXT_JSON = ROOT / "data" / "domain_context.json"
TOPIC_CLOUD_JSON = ROOT / "data" / "topic_cloud.json"
PROFILES_DIR = ROOT / "profiles"
PROFILE_INDEX = PROFILES_DIR / "index.html"
INSIGHTS_PAGE = ROOT / "insights.html"
BRIEFING_PAGE = ROOT / "daily_briefing.html"
POSTER_PAGE = ROOT / "poster.html"
DAILY_PROGRESS_PAGE = ROOT / "daily_progress.html"
TOPICS_PAGE = ROOT / "topics.html"

DEFAULT_DOMAIN_CONFIG = {
    "slug": "ai",
    "site_title_zh": "领域社交影响力情报台",
    "site_title_en": "Domain Influence Intelligence",
    "domain_name_zh": "AI",
    "domain_name_en": "AI",
    "platform_name": "X",
    "entity_label_zh": "博主",
    "entity_label_en": "creators",
    "sample_pool_label_zh": "X 领域博主",
    "sample_pool_label_en": "X domain creators",
    "topics_page_zh": "热点词云",
    "topics_page_en": "Topic Cloud",
    "insights_page_zh": "最新分享",
    "insights_page_en": "Latest Shares",
    "progress_page_zh": "每日进展",
    "progress_page_en": "Daily Progress",
    "include_handles": [],
    "match_keywords": [],
    "exclude_keywords": [],
    "topic_taxonomy": [
        {"topic": "AI Agents", "keywords": ["agent", "agents", "assistant", "workflow", "tool use"]},
        {"topic": "Model Capability", "keywords": ["model", "reasoning", "multimodal", "inference", "benchmark"]},
        {"topic": "Productization", "keywords": ["product", "shipping", "deploy", "go to market", "distribution"]},
        {"topic": "AI Industry", "keywords": ["industry", "enterprise", "platform", "ecosystem", "market"]},
        {"topic": "Research Frontier", "keywords": ["research", "paper", "science", "arxiv", "breakthrough"]},
        {"topic": "OpenAI Ecosystem", "keywords": ["openai", "chatgpt", "gpt", "sora", "codex"]},
        {"topic": "Model Engineering", "keywords": ["pytorch", "training", "fine-tuning", "cuda", "weights"]},
        {"topic": "Robotics", "keywords": ["robot", "robots", "robotics", "physical ai"]},
        {"topic": "AI Infrastructure", "keywords": ["infra", "infrastructure", "gpu", "cluster", "compute"]},
        {"topic": "Safety & Alignment", "keywords": ["safety", "alignment", "governance", "policy", "risk"]},
    ],
    "default_topics": ["Industry", "Capability", "Productization"],
    "term_stopwords": [
        "about", "after", "again", "against", "also", "been", "being", "because", "between", "could", "every",
        "first", "from", "have", "into", "just", "latest", "looks", "like", "more", "most", "much", "over",
        "people", "really", "share", "their", "there", "these", "this", "today", "using", "very", "what",
        "when", "where", "with", "would", "your", "that", "than", "they", "them", "then", "were", "will",
        "open", "source", "just", "news", "thread", "check", "out", "here", "https", "http", "com",
    ],
}

LAYER_LABEL_ZH = {
    "core": "核心",
    "inner_core": "内核",
    "middle_core": "中间核",
    "outer_core": "外核",
    "surface": "表层",
}
LAYER_LABEL_EN = {
    "core": "Core",
    "inner_core": "Inner Core",
    "middle_core": "Middle Core",
    "outer_core": "Outer Core",
    "surface": "Surface",
}


def load_domain_config() -> dict:
    config = json.loads(json.dumps(DEFAULT_DOMAIN_CONFIG, ensure_ascii=False))
    if DOMAIN_CONFIG_PATH.exists():
        try:
            user_cfg = json.loads(DOMAIN_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            user_cfg = {}
        if isinstance(user_cfg, dict):
            for key, value in user_cfg.items():
                config[key] = value
    return config


def taxonomy_pairs(domain: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in domain.get("topic_taxonomy") or []:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        for keyword in item.get("keywords") or []:
            kw = str(keyword or "").strip().lower()
            if topic and kw:
                pairs.append((kw, topic))
    return pairs


def slugify(handle: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "-", handle.strip().lstrip("@"))
    return s.strip("-").lower() or "unknown"


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return clamp01((float(v) - lo) / (hi - lo))


def layer_by_rank(rank: int, total: int) -> str:
    if total <= 0:
        return "surface"
    pct = rank / total
    if pct <= 0.05:
        return "core"
    if pct <= 0.20:
        return "inner_core"
    if pct <= 0.50:
        return "middle_core"
    if pct <= 0.75:
        return "outer_core"
    return "surface"


def topic_from_text(text: str, domain: dict) -> list[str]:
    t = text.lower()
    topics = []
    pairs = taxonomy_pairs(domain)
    for k, v in pairs:
        if k in t and v not in topics:
            topics.append(v)
    if not topics:
        topics = list(domain.get("default_topics") or DEFAULT_DOMAIN_CONFIG["default_topics"])
    return topics[:3]


def tokenize_terms(text: str, stopwords: set[str]) -> list[str]:
    terms = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9\-\+#\.]{2,}", text or ""):
        low = token.lower().strip(".")
        if low in stopwords:
            continue
        if low.startswith("www") or low.endswith(".com"):
            continue
        terms.append(low)
    return terms


def normalize_term_text(text: str, aliases: dict[str, str]) -> str:
    normalized = (text or "").lower()
    for src, target in aliases.items():
        source = str(src or "").strip().lower()
        replacement = str(target or "").strip().lower()
        if not source or not replacement:
            continue
        normalized = normalized.replace(source, replacement)
    return normalized


def domain_context(domain: dict, total_count: int) -> dict:
    domain_zh = str(domain.get("domain_name_zh") or "该领域")
    domain_en = str(domain.get("domain_name_en") or "this domain")
    entity_zh = str(domain.get("entity_label_zh") or "博主")
    entity_en = str(domain.get("entity_label_en") or "creators")
    platform = str(domain.get("platform_name") or "X")
    sample_zh = str(domain.get("sample_pool_label_zh") or f"{platform} 领域{entity_zh}")
    sample_en = str(domain.get("sample_pool_label_en") or f"{platform} domain {entity_en}")
    return {
        "slug": str(domain.get("slug") or "domain"),
        "site_title_zh": str(domain.get("site_title_zh") or f"{domain_zh} 社交影响力情报台"),
        "site_title_en": str(domain.get("site_title_en") or f"{domain_en} Influence Intelligence"),
        "domain_name_zh": domain_zh,
        "domain_name_en": domain_en,
        "entity_label_zh": entity_zh,
        "entity_label_en": entity_en,
        "platform_name": platform,
        "sample_pool_label_zh": sample_zh,
        "sample_pool_label_en": sample_en,
        "topics_page_zh": str(domain.get("topics_page_zh") or "热点词云"),
        "topics_page_en": str(domain.get("topics_page_en") or "Topic Cloud"),
        "insights_page_zh": str(domain.get("insights_page_zh") or "最新分享"),
        "insights_page_en": str(domain.get("insights_page_en") or "Latest Shares"),
        "progress_page_zh": str(domain.get("progress_page_zh") or "每日进展"),
        "progress_page_en": str(domain.get("progress_page_en") or "Daily Progress"),
        "total_profiles": int(total_count),
        "filters": {
            "include_handles": list(domain.get("include_handles") or []),
            "match_keywords": list(domain.get("match_keywords") or []),
            "exclude_keywords": list(domain.get("exclude_keywords") or []),
        },
    }


def domain_matches(row: dict, node: dict, domain: dict) -> bool:
    include_handles = {str(x).strip().lstrip("@").lower() for x in (domain.get("include_handles") or []) if str(x).strip()}
    match_keywords = [str(x).strip().lower() for x in (domain.get("match_keywords") or []) if str(x).strip()]
    exclude_keywords = [str(x).strip().lower() for x in (domain.get("exclude_keywords") or []) if str(x).strip()]
    handle = str(row.get("handle") or row.get("id") or "").strip().lstrip("@").lower()
    haystack = " ".join(
        [
            handle,
            str(row.get("name") or ""),
            str(row.get("role") or ""),
            str(row.get("group") or ""),
            str(node.get("bio") or ""),
            str(node.get("role") or ""),
            str(node.get("group") or ""),
            str(row.get("latest_tweet_text") or ""),
        ]
    ).lower()
    if include_handles and handle in include_handles:
        return True
    if exclude_keywords and any(k in haystack for k in exclude_keywords):
        return False
    if match_keywords:
        return any(k in haystack for k in match_keywords)
    return True


def build_topic_cloud(profiles: list[dict], updated_at: str, built_at: str, domain: dict, ctx: dict) -> dict:
    stopwords = {str(x).strip().lower() for x in (domain.get("term_stopwords") or []) if str(x).strip()}
    stopwords |= {"rt", "amp", "the", "and", "for", "you", "are", "our", "its", "via"}
    aliases = {
        "hugging face": "huggingface",
        "open ai": "openai",
        "deep mind": "deepmind",
        "co founder": "cofounder",
        "fine tuning": "fine-tuning",
    }
    aliases.update({str(k).strip().lower(): str(v).strip().lower() for k, v in (domain.get("term_aliases") or {}).items() if str(k).strip() and str(v).strip()})
    blocklist = {
        "founder", "cofounder", "co-founder", "company", "researcher", "professor", "scientist",
        "ceo", "cto", "chief", "assistant", "media", "investor", "platform", "creator", "developer",
        "former", "partner", "host", "author", "team", "studio", "newsroom", "division", "center",
        "customer", "care", "university", "college", "school", "member", "leader", "lead",
        "built", "building", "me", "my", "but", "some", "has", "had", "want", "time", "long",
        "one", "know", "work", "works", "working", "slides", "slide", "talk", "talks", "lecture",
        "lectures", "docs", "doc", "use", "using", "used", "former", "latest", "share", "shares",
        "today", "news", "thread", "check", "here", "deep", "learning",
    }
    blocklist |= {str(x).strip().lower() for x in (domain.get("term_blocklist") or []) if str(x).strip()}
    allowlist = {str(x).strip().lower() for x in (domain.get("term_allowlist") or []) if str(x).strip()}
    min_count = max(1, int(domain.get("term_min_count") or 2))
    term_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    topic_people: dict[str, dict[str, dict]] = defaultdict(dict)
    term_people: dict[str, dict[str, dict]] = defaultdict(dict)

    for row in profiles:
        handle = str(row.get("handle") or "").strip()
        slug = str(row.get("slug") or "").strip()
        name = str(row.get("name") or handle).strip()
        texts = normalize_term_text(
            " ".join(
            [
                str(row.get("latest_tweet_text") or ""),
                str(row.get("today_hottest_tweet_text") or ""),
                " ".join(row.get("topics") or []),
            ]
            ),
            aliases,
        )
        for topic in row.get("topics") or []:
            topic_counter[topic] += 1
            if handle:
                topic_people[topic][handle.lower()] = {"handle": handle, "slug": slug, "name": name}
        for term in tokenize_terms(texts, stopwords):
            if term in blocklist:
                continue
            if allowlist and term not in allowlist:
                continue
            term_counter[term] += 1
            if handle:
                term_people[term][handle.lower()] = {"handle": handle, "slug": slug, "name": name}

    top_topics = [
        {
            "topic": topic,
            "count": count,
            "people": list((topic_people.get(topic) or {}).values())[:12],
        }
        for topic, count in topic_counter.most_common(18)
    ]
    top_terms = []
    max_count = max(term_counter.values()) if term_counter else 1
    visible_terms = [(term, count) for term, count in term_counter.most_common() if count >= min_count]
    for idx, (term, count) in enumerate(visible_terms[:48]):
        weight = 0.24 + 0.76 * (count / max_count)
        size = 16 + int(round(44 * weight))
        angle = (-9, -4, 0, 4, 9)[idx % 5]
        top_terms.append(
            {
                "term": term,
                "count": count,
                "weight": round(weight, 4),
                "font_size": size,
                "angle": angle,
                "people": list((term_people.get(term) or {}).values())[:16],
            }
        )

    lead = top_topics[0]["topic"] if top_topics else (ctx.get("domain_name_en") or "Domain")
    second = top_topics[1]["topic"] if len(top_topics) > 1 else lead
    summary_zh = f"当前热点集中在 {lead} 与 {second}，词云基于最近可用分享、人物标签和角色描述生成。"
    summary_en = f"Current hotspots cluster around {lead} and {second}, based on recent shares, creator tags, and role descriptions."

    return {
        "updated_at": updated_at,
        "built_at": built_at,
        "domain": ctx,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "topics": top_topics,
        "terms": top_terms,
    }


def zh_summary(row: dict, node: dict, layer_zh: str) -> str:
    role = row.get("role") or node.get("role") or "AI 从业者"
    bio = (node.get("bio") or "").strip()
    bio_cut = bio[:120] + ("..." if len(bio) > 120 else "")
    score = float(row.get("quanzhong_score") or 0)
    return (
        f"{row.get('name')} 属于{layer_zh}圈层，角色为 {role}。"
        f"综合影响力评分为 {score:.3f}。"
        f"公开信息显示其长期关注：{bio_cut or '大模型应用、工程落地与行业趋势'}。"
    )


def en_summary(row: dict, node: dict, layer_en: str) -> str:
    role = row.get("role") or node.get("role") or "AI practitioner"
    bio = (node.get("bio") or "").strip()
    bio_cut = bio[:180] + ("..." if len(bio) > 180 else "")
    score = float(row.get("quanzhong_score") or 0)
    return (
        f"{row.get('name')} is in the {layer_en} layer as a {role}. "
        f"Composite influence score: {score:.3f}. "
        f"Public profile signals focus on {bio_cut or 'LLM products, engineering execution, and ecosystem trends'}."
    )


def daily_essence_zh(row: dict, topics: list[str]) -> str:
    t1 = topics[0] if len(topics) > 0 else "AI 产业"
    t2 = topics[1] if len(topics) > 1 else t1
    return (
        f"今日精髓：围绕 {t1} 与 {t2}，强调“模型能力要进入可复用产品链路”，"
        f"并持续优化发布-反馈-迭代闭环（影响力分 {float(row.get('quanzhong_score') or 0):.3f}）。"
    )


def daily_essence_en(row: dict, topics: list[str]) -> str:
    t1 = topics[0] if len(topics) > 0 else "AI Industry"
    t2 = topics[1] if len(topics) > 1 else t1
    return (
        f"Daily essence: around {t1} and {t2}, the key point is turning model capability into reusable product loops, "
        f"then iterating with publish-feedback cycles (influence score {float(row.get('quanzhong_score') or 0):.3f})."
    )


def _clean_tweet_text(text: str) -> str:
    t = re.sub(r"https?://\\S+", "", text or "").strip()
    t = re.sub(r"\\s+", " ", t)
    return t[:240].strip()


def latest_viewpoint_zh(row: dict, topics: list[str]) -> str:
    txt = _clean_tweet_text(str(row.get("latest_tweet_text") or ""))
    if not txt:
        return ""
    t1 = topics[0] if topics else "AI"
    return f"最新观点：{txt}（主题：{t1}）"


def latest_viewpoint_en(row: dict, topics: list[str]) -> str:
    txt = _clean_tweet_text(str(row.get("latest_tweet_text") or ""))
    if not txt:
        return ""
    t1 = topics[0] if topics else "AI"
    return f"Latest view: {txt} (topic: {t1})"


def latest_share_zh(row: dict, topics: list[str]) -> str:
    txt = _clean_tweet_text(str(row.get("today_hottest_tweet_text") or ""))
    if txt:
        return txt
    txt2 = _clean_tweet_text(str(row.get("latest_tweet_text") or ""))
    if txt2:
        return txt2
    return ""


def latest_share_en(row: dict, topics: list[str]) -> str:
    txt = _clean_tweet_text(str(row.get("today_hottest_tweet_text") or ""))
    if txt:
        return txt
    txt2 = _clean_tweet_text(str(row.get("latest_tweet_text") or ""))
    if txt2:
        return txt2
    return ""


def _recency_days_from_row(row: dict) -> int:
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    raw = str(row.get("today_hottest_tweet_at") or row.get("latest_tweet_at") or "").strip()
    if not raw:
        return 999
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        diff = now - parsed.astimezone(dt.timezone.utc)
        return max(0, int(diff.total_seconds() // 86400))
    except Exception:
        return 999


def _sort_timestamp_from_row(row: dict) -> float:
    raw = str(row.get("today_hottest_tweet_at") or row.get("latest_tweet_at") or "").strip()
    if not raw:
        return 0.0
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except Exception:
        return 0.0


def _display_share_time(label: str, iso_ts: str) -> str:
    raw_label = str(label or "").strip()
    if raw_label:
        return raw_label
    raw_iso = str(iso_ts or "").strip()
    if not raw_iso:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(raw_iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return raw_iso


def compute_best_buddies(
    top_rows: list[dict],
    weighted_links: list[dict],
    id_to_profile: dict[str, dict],
) -> dict[str, list[dict]]:
    """Association-centrality style 'best interaction buddies' by edge intensity + engagement."""
    edge_map: dict[tuple[str, str], dict] = {}
    neighbors: dict[str, set[str]] = defaultdict(set)
    engagement_raw: dict[str, float] = {}

    for row in top_rows:
        nid = str(row.get("id") or row.get("handle") or "")
        engagement_raw[nid] = (
            float(row.get("posts_count") or 0)
            + float(row.get("comments_count") or 0)
            + float(row.get("likes_count") or 0)
            + float(row.get("reposts_count") or 0)
        )

    lo = min(engagement_raw.values()) if engagement_raw else 0.0
    hi = max(engagement_raw.values()) if engagement_raw else 1.0
    engagement_norm = {k: norm(v, lo, hi) for k, v in engagement_raw.items()}

    for lk in weighted_links:
        s = str(lk.get("source") or "")
        t = str(lk.get("target") or "")
        if not s or not t or s == t:
            continue
        edge_map[(s, t)] = lk
        neighbors[s].add(t)
        neighbors[t].add(s)

    out: dict[str, list[dict]] = {}
    for nid in id_to_profile:
        cands = []
        for oid in neighbors.get(nid, set()):
            forward = edge_map.get((nid, oid), {})
            backward = edge_map.get((oid, nid), {})
            if not forward and not backward:
                continue
            fw = float(forward.get("weight") or 0)
            bw = float(backward.get("weight") or 0)
            assoc = fw + bw
            reciprocal = 1.0 if (forward and backward) else float(forward.get("reciprocal") or backward.get("reciprocal") or 0)
            semantic = (float(forward.get("semantic_similarity") or 0) + float(backward.get("semantic_similarity") or 0)) / 2
            structural = (float(forward.get("structural") or 0) + float(backward.get("structural") or 0)) / 2

            # Proxy for interaction closeness using edge strength + counterpart engagement activity.
            engagement_proxy = assoc * (0.35 + 0.65 * float(engagement_norm.get(oid, 0)))
            buddy_score = 0.52 * assoc + 0.23 * engagement_proxy + 0.15 * reciprocal + 0.10 * (0.6 * structural + 0.4 * semantic)
            cands.append((oid, buddy_score, assoc, engagement_proxy, reciprocal))

        cands.sort(key=lambda x: x[1], reverse=True)
        best = []
        for oid, score, assoc, inter, reciprocal in cands[:5]:
            p = id_to_profile.get(oid)
            if not p:
                continue
            best.append(
                {
                    "id": oid,
                    "slug": p.get("slug"),
                    "name": p.get("name"),
                    "handle": p.get("handle"),
                    "layer": p.get("layer"),
                    "score": round(float(score), 6),
                    "association": round(float(assoc), 6),
                    "interaction_proxy": round(float(inter), 6),
                    "reciprocal": round(float(reciprocal), 3),
                }
            )
        out[nid] = best
    return out


def parse_iso_dt(value: str | None) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_content_updated_at(rows: list[dict], fallback: str) -> str:
    latest_dt = None
    for row in rows:
        for key in ("today_hottest_tweet_at", "latest_share_at", "updated_at"):
            parsed = parse_iso_dt(row.get(key))
            if parsed and (latest_dt is None or parsed > latest_dt):
                latest_dt = parsed
    return latest_dt.isoformat() if latest_dt else fallback


def build_daily_progress(profiles: list[dict], top10: list[dict], updated_at: str, built_at: str, ctx: dict) -> dict:
    top_topics = Counter()
    for p in profiles[:120]:
        top_topics.update(p.get("topics") or [])
    topic_rank = [{"topic": k, "count": v} for k, v in top_topics.most_common(6)]

    trend_rows = sorted(
        top10 if top10 else profiles,
        key=lambda p: (
            float(p.get("association_score") or 0) * 0.5
            + float(p.get("centrality_score") or 0) * 0.3
            + float(p.get("explainability", {}).get("interaction", 0)) * 0.2
        ),
        reverse=True,
    )
    trend_items = [
        {
            "name": r.get("name"),
            "handle": r.get("handle"),
            "slug": r.get("slug"),
            "score": round(float(r.get("score") or 0), 3),
            "topics": r.get("topics") or [],
            "daily_essence_zh": r.get("daily_essence_zh", ""),
            "daily_essence_en": r.get("daily_essence_en", ""),
            "latest_viewpoint_zh": r.get("latest_viewpoint_zh", ""),
            "latest_viewpoint_en": r.get("latest_viewpoint_en", ""),
            "latest_share_zh": r.get("latest_share_zh", ""),
            "latest_share_en": r.get("latest_share_en", ""),
            "latest_tweet_url": r.get("latest_tweet_url", ""),
            "today_hottest_tweet_url": r.get("today_hottest_tweet_url", ""),
        }
        for r in trend_rows
    ]

    lead_topic_zh = topic_rank[0]["topic"] if topic_rank else (ctx.get("domain_name_en") or "Domain")
    second_topic_zh = topic_rank[1]["topic"] if len(topic_rank) > 1 else lead_topic_zh
    domain_zh = str(ctx.get("domain_name_zh") or "该领域")
    domain_en = str(ctx.get("domain_name_en") or "this domain")
    summary_zh = (
        f"今日{domain_zh}进展：讨论重心集中在 {lead_topic_zh} 与 {second_topic_zh}。"
        f"Top10 关键人物仍在推动“模型能力产品化 + 发布反馈闭环”，"
        f"全网高影响博主均值分约 {sum(float(x.get('score') or 0) for x in top10) / max(1, len(top10)):.3f}。"
    )
    summary_en = (
        f"Daily {domain_en} progress: discussion centers on {lead_topic_zh} and {second_topic_zh}. "
        f"Top voices keep focusing on productizing model capability and iterating via publish-feedback loops."
    )

    return {
        "updated_at": updated_at,
        "built_at": built_at,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "topic_rank": topic_rank,
        "top10": [
            {
                "name": x.get("name"),
                "handle": x.get("handle"),
                "slug": x.get("slug"),
                "score": round(float(x.get("score") or 0), 3),
                "topics": x.get("topics") or [],
                "daily_essence_zh": x.get("daily_essence_zh", ""),
                "daily_essence_en": x.get("daily_essence_en", ""),
            }
            for x in top10
        ],
        "trend_items": trend_items,
    }


def profile_page(profile: dict, ctx: dict) -> str:
    name = html.escape(profile["name"])
    handle = html.escape(profile["handle"])
    zh = html.escape(profile["summary_zh"])
    en = html.escape(profile["summary_en"])
    tags = "".join(f"<span class='tag'>{html.escape(t)}</span>" for t in profile["topics"])
    de_zh = html.escape(profile["daily_essence_zh"])
    de_en = html.escape(profile["daily_essence_en"])
    layer_zh = html.escape(profile["layer_zh"])
    layer_en = html.escape(profile["layer_en"])
    score = float(profile.get("score") or 0)
    assoc = float(profile.get("association_score") or 0)
    centr = float(profile.get("centrality_score") or 0)
    rank = int(profile.get("rank") or 0)
    followers = int(profile.get("followers") or 0)
    posts = int(profile.get("posts_count") or 0)
    comments = int(profile.get("comments_count") or 0)
    likes = int(profile.get("likes_count") or 0)
    reposts = int(profile.get("reposts_count") or 0)
    e = profile.get("explainability", {})
    buddies = profile.get("best_buddies") or []
    buddies_html = "".join(
        (
            "<div class='kpi'>"
            f"<div class='k'><a class='btn' href='/profiles/{html.escape(str(b.get('slug') or ''))}.html'>"
            f"{html.escape(str(b.get('name') or ''))}</a> @{html.escape(str(b.get('handle') or ''))}</div>"
            f"<div class='v'>{float(b.get('score') or 0):.3f}</div>"
            f"<div class='k'>关联 {float(b.get('association') or 0):.3f} · 互动 {float(b.get('interaction_proxy') or 0):.3f}</div>"
            "</div>"
        )
        for b in buddies
    )
    recency_days = int(profile.get("recency_days") or 999)
    latest_share_time = _display_share_time(
        str(profile.get("latest_tweet_at_label") or ""),
        str(profile.get("latest_tweet_at") or ""),
    )
    freshness_note = (
        f"最近分享时间：{latest_share_time or '未知'}。最近内容距今 {recency_days} 天。若今天没有新帖，页面会展示最近一次可用分享，不伪装为当日观点。"
        if recency_days < 900
        else f"最近分享时间：{latest_share_time or '未知'}。当前未拿到可确认发布时间的原始帖子，页面仅展示最近一次可用抓取结果。"
    )

    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>{name} | {html.escape(str(ctx.get("site_title_en") or "Profile"))}</title>
<script src=\"../assets/metrics.js\" defer></script>
<script src=\"../assets/expert-limit.js\" defer></script>
<style>
:root{{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:920px;margin:0 auto;padding:16px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}}
.row{{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}}
.name{{font-size:24px;font-weight:800}} .handle{{color:var(--muted)}} .muted{{color:var(--muted)}}
.btn{{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}}
.tags{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}} .tag{{font-size:12px;border:1px solid rgba(255,255,255,.2);padding:5px 8px;border-radius:999px}}
.kpis{{margin-top:10px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}
.kpi{{border:1px solid var(--line);border-radius:10px;background:#0f1730;padding:9px}} .k{{font-size:12px;color:var(--muted)}} .v{{font-size:18px;font-weight:700;margin-top:2px}}
.sec{{margin-top:12px}} .sec h3{{margin:0 0 6px;font-size:16px}}
.bar{{height:8px;background:#0f1730;border:1px solid var(--line);border-radius:999px;overflow:hidden}} .bar > i{{display:block;height:100%;background:linear-gradient(90deg,#45d5ff,#2a6bff)}}
.notice{{margin-top:10px;padding:10px 12px;border-radius:12px;border:1px solid rgba(106,211,255,.28);background:rgba(106,211,255,.08);color:#d7e8ff;font-size:13px;line-height:1.6}}
@media (max-width:760px){{.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}} .name{{font-size:20px}}}}
</style></head><body><div class=\"wrap\"><div class=\"card\">
<div class=\"row\"><div><div class=\"name\">{name}</div><div class=\"handle\">@{handle}</div></div>
<div class=\"row\"><a class=\"btn\" href=\"https://x.com/{handle}\" target=\"_blank\">Open X</a><a class=\"btn\" href=\"./index.html\">Profiles</a><a class=\"btn\" href=\"../topics.html\">{html.escape(str(ctx.get("topics_page_zh") or "热点词云"))}</a><a class=\"btn\" href=\"../public_signals.html\">公共信号</a><a class=\"btn\" href=\"../poster.html?slug={profile['slug']}&mode=profile\">分享海报</a><a class=\"btn\" href=\"../commercial.html\">Commercial</a><a class=\"btn\" href=\"../contact.html\">Contact</a></div></div>
<div class=\"muted\" style=\"margin-top:6px\">Layer: {layer_en} / {layer_zh}</div>
<div class=\"notice\">{html.escape(freshness_note)}</div>
<div class=\"tags\">{tags}</div>
<div class=\"kpis\">
<div class=\"kpi\"><div class=\"k\">Rank</div><div class=\"v\">#{rank}</div></div>
<div class=\"kpi\"><div class=\"k\">Influence Score</div><div class=\"v\">{score:.3f}</div></div>
<div class=\"kpi\"><div class=\"k\">Followers</div><div class=\"v\">{followers:,}</div></div>
<div class=\"kpi\"><div class=\"k\">Association Score</div><div class=\"v\">{assoc:.3f}</div></div>
<div class=\"kpi\"><div class=\"k\">Centrality Score</div><div class=\"v\">{centr:.3f}</div></div>
<div class=\"kpi\"><div class=\"k\">Posts/Comments</div><div class=\"v\">{posts:,}/{comments:,}</div></div>
<div class=\"kpi\"><div class=\"k\">Likes/Reposts</div><div class=\"v\">{likes:,}/{reposts:,}</div></div>
</div>
<div class=\"sec\"><h3>评分可解释面板 / Explainability</h3>
<div class=\"muted\">关联度由交叉关注、互动强度、连接权重构成；核心度由PageRank、连接度、受众规模构成。</div>
<div style=\"margin-top:8px\">Association: {assoc:.3f}</div><div class=\"bar\"><i style=\"width:{assoc*100:.1f}%\"></i></div>
<div style=\"margin-top:8px\">Centrality: {centr:.3f}</div><div class=\"bar\"><i style=\"width:{centr*100:.1f}%\"></i></div>
<div class=\"muted\" style=\"margin-top:8px\">Cross-follow {float(e.get('cross_follow_ratio',0)):.3f} · Interaction {float(e.get('interaction',0)):.3f} · PageRank {float(e.get('pagerank',0)):.3f}</div>
</div>
<div class=\"sec\"><h3>最佳互动基友 Top5</h3>
<div class=\"muted\">按 association-centrality 关系强度 + 互动代理指标计算（关注/互动/转发语义综合）。</div>
<div class=\"kpis\">{buddies_html or '<div class="muted">暂无可计算关系</div>'}</div>
</div>
<div class=\"sec\"><h3>中文简介</h3><div>{zh}</div></div>
<div class=\"sec\"><h3>English Summary</h3><div>{en}</div></div>
<div class=\"sec\"><h3>今日观点精髓（中文）</h3><div class=\"muted\">{de_zh}</div></div>
<div class=\"sec\"><h3>Daily Insight (EN)</h3><div class=\"muted\">{de_en}</div></div>
</div></div></body></html>"""


def profiles_index(ctx: dict) -> str:
    return """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>X Influencer Profiles</title>
<script src=\"../assets/metrics.js\" defer></script>
<script src=\"../assets/expert-limit.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}
.tools{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}.tools input,.tools select{padding:8px 10px;border-radius:10px;border:1px solid rgba(255,255,255,.2);background:#111a34;color:#eaf0ff}
.grid{margin-top:12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}.item{background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:5px}
.name{font-weight:700}.muted{color:#9db0da;font-size:12px}.line{display:flex;justify-content:space-between;gap:8px}.tag{font-size:11px;border:1px solid rgba(255,255,255,.2);padding:3px 6px;border-radius:999px}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>X Influencer Profiles / 博主画像库</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"../index.html\">Home</a><a class=\"btn\" href=\"../insights.html\">Insights</a><a class=\"btn\" href=\"../daily_briefing.html\">Briefing</a><a class=\"btn\" href=\"../daily_progress.html\">每日进展</a><a class=\"btn\" href=\"../topics.html\">热点词云</a><a class=\"btn\" href=\"../public_signals.html\">公共信号</a><a class=\"btn\" href=\"../poster.html?mode=custom\">自选博主海报</a><a class=\"btn\" href=\"../commercial.html\">Commercial</a><a class=\"btn\" href=\"../contact.html\">Contact</a></div></div>
<div class=\"tools\"><input id=\"q\" placeholder=\"Search name/handle\"/><select id=\"layer\"><option value=\"all\">All Layers</option></select><select id=\"sort\"><option value=\"rank\">Sort by Rank</option><option value=\"score\">Sort by Score</option><option value=\"followers\">Sort by Followers</option></select></div>
<div id=\"grid\" class=\"grid\"></div></div>
<script>
const layerLabel={core:'Core/核心',inner_core:'Inner Core/内核',middle_core:'Middle Core/中间核',outer_core:'Outer Core/外核',surface:'Surface/表层'};
const q=document.getElementById('q'); const layer=document.getElementById('layer'); const sort=document.getElementById('sort'); const grid=document.getElementById('grid');
let rows=[];
function render(){
  const key=(q.value||'').toLowerCase().trim();
  const lv=layer.value; const sv=sort.value;
  let fs=rows.filter(r=>(!key||(`${r.name} ${r.handle}`).toLowerCase().includes(key)) && (lv==='all'||r.layer===lv));
  fs.sort((a,b)=>sv==='rank'?a.rank-b.rank:sv==='followers'?(b.followers-a.followers):(b.score-a.score));
  grid.innerHTML=fs.map(r=>`<div class=\"item\"><div class=\"line\"><div class=\"name\">${r.name}</div><div class=\"muted\">#${r.rank}</div></div><div class=\"muted\">@${r.handle}</div><div class=\"line\"><span class=\"tag\">${layerLabel[r.layer]||r.layer}</span><span class=\"muted\">score ${Number(r.score||0).toFixed(3)}</span></div><div class=\"line\"><a class=\"btn\" href=\"./${r.slug}.html\">Profile</a><a class=\"btn\" href=\"../poster.html?slug=${r.slug}&mode=profile\">海报</a><a class=\"btn\" href=\"https://x.com/${r.handle}\" target=\"_blank\">Open X</a></div></div>`).join('');
}
fetch('../data/profiles.json').then(r=>r.json()).then(d=>{
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  rows=(d.items||[]).slice(0, limit);
  const set=[...new Set(rows.map(x=>x.layer))];
  layer.innerHTML='<option value="all">All Layers</option>'+set.map(v=>`<option value="${v}">${layerLabel[v]||v}</option>`).join('');
  render();
});
q.addEventListener('input',render); layer.addEventListener('change',render); sort.addEventListener('change',render);
</script></body></html>"""


def insights_page(ctx: dict) -> str:
    return """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>Daily Insights</title>
<script src=\"./assets/metrics.js\" defer></script>
<script src=\"./assets/expert-limit.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}
.tools{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}.tools input,.tools select{padding:8px 10px;border-radius:10px;border:1px solid rgba(255,255,255,.2);background:#111a34;color:#eaf0ff}
.grid{margin-top:12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}.card{background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px}.muted{color:#9db0da;font-size:12px}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>Latest Shares / 最新分享</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./index.html\">Home</a><a class=\"btn\" href=\"./profiles/index.html\">Profiles</a><a class=\"btn\" href=\"./daily_briefing.html\">Top10</a><a class=\"btn\" href=\"./daily_progress.html\">每日进展</a><a class=\"btn\" href=\"./topics.html\">热点词云</a><a class=\"btn\" href=\"./public_signals.html\">公共信号</a><a class=\"btn\" href=\"./poster.html?mode=top10\">Top10海报</a><a class=\"btn\" href=\"./commercial.html\">Commercial</a><a class=\"btn\" href=\"./contact.html\">Contact</a></div></div>
<div class=\"tools\"><input id=\"q\" placeholder=\"Search name/handle\"/><select id=\"lang\"><option value=\"zh\">中文</option><option value=\"en\">English</option></select><select id=\"time\"><option value=\"1\">24h</option><option value=\"7\">7d</option><option value=\"30\" selected>30d</option></select><select id=\"topic\"><option value=\"all\">All Topics</option></select><select id=\"layer\"><option value=\"all\">All Layers</option></select></div>
<div class=\"card\" id=\"freshness\" style=\"margin-top:10px\"></div>
<div id=\"grid\" class=\"grid\"></div></div>
<script>
const q=document.getElementById('q'); const lang=document.getElementById('lang'); const layer=document.getElementById('layer'); const time=document.getElementById('time'); const topic=document.getElementById('topic'); const grid=document.getElementById('grid');
const freshness=document.getElementById('freshness');
const layerLabel={core:'Core/核心',inner_core:'Inner Core/内核',middle_core:'Middle Core/中间核',outer_core:'Outer Core/外核',surface:'Surface/表层'};
let rows=[];
function render(){
  const key=(q.value||'').toLowerCase().trim(), l=lang.value, lv=layer.value, tv=parseInt(time.value||'30',10), tp=topic.value;
  let fs=rows.filter(r=>{
    const hasKey=!key||(`${r.name} ${r.handle}`).toLowerCase().includes(key);
    const inLayer=lv==='all'||r.layer===lv;
    const recency=Number(r.recency_days ?? 999);
    const inTime=recency<=tv;
    const inTopic=tp==='all'||(r.topics||[]).includes(tp);
    return hasKey&&inLayer&&inTime&&inTopic;
  });
  fs.sort((a,b)=>{
    const ra=Number(a.recency_days ?? 999), rb=Number(b.recency_days ?? 999);
    if(ra!==rb) return ra-rb;
    const ta=Number(a.sort_ts ?? 0), tb=Number(b.sort_ts ?? 0);
    if(ta!==tb) return tb-ta;
    const sa=Number(a.score||0), sb=Number(b.score||0);
    if(sa!==sb) return sb-sa;
    return Number(a.rank||999999)-Number(b.rank||999999);
  });
  grid.innerHTML=fs.map(r=>{
    const buddy=((r.best_buddies||[])[0]||null);
    const buddyLine=buddy?`<div class=\"muted\">最佳互动基友：${buddy.name} @${buddy.handle}</div>`:'';
    const shareTime=r.latest_tweet_at_label||r.latest_tweet_at||'';
    return `<div class=\"card\"><div><b>${r.name}</b> <span class=\"muted\">@${r.handle}</span></div><div class=\"muted\">${layerLabel[r.layer]||r.layer} · score ${Number(r.score||0).toFixed(3)} · ${(r.topics||[]).join(' · ')}</div><p>${l==='zh'?'最新分享：':'Latest share: '}${l==='zh'?(r.latest_share_zh||r.latest_viewpoint_zh||''):(r.latest_share_en||r.latest_viewpoint_en||'')}</p>${buddyLine}<div class=\"muted\">${l==='zh'?'分享时间：':'Share time: '}${shareTime}</div><div class=\"muted\">Recency: ${r.recency_days}d</div><div style=\"display:flex;gap:8px;margin-top:8px\"><a class=\"btn\" href=\"./profiles/${r.slug}.html\">View Profile</a><a class=\"btn\" href=\"./poster.html?slug=${r.slug}&mode=insight&lang=${l}\">海报</a><a class=\"btn\" href=\"https://x.com/${r.handle}\" target=\"_blank\">Open X</a></div></div>`;
  }).join('');
}
Promise.all([
  fetch('./data/daily_insights.json').then(r=>r.json()).catch(()=>({items:[]})),
  fetch('./data/refresh_status.json').then(r=>r.json()).catch(()=>null)
]).then(([d,rs])=>{
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  rows=(d.items||[]).slice(0, limit);
  const modeMap={x_api_v2:'X API',rjina_fallback:'网页回退源'};
  const mode=rs ? (modeMap[rs.mode]||rs.mode||'未知') : '未知';
  freshness.innerHTML=`<div><b>内容时间：</b>${(d.updated_at||'-').replace('T',' ').slice(0,19)} <span class=\"muted\">· 页面生成 ${(d.built_at||'-').replace('T',' ').slice(0,19)} · 刷新来源 ${mode}</span></div><div class=\"muted\" style=\"margin-top:6px\">这里展示的是每位博主最近一次可用分享；如果当天没有可确认的新帖，不会伪装成“今日观点”。</div>`;
  const layerSet=[...new Set(rows.map(x=>x.layer))];
  layer.innerHTML='<option value="all">All Layers</option>'+layerSet.map(v=>`<option value="${v}">${layerLabel[v]||v}</option>`).join('');
  const topics=[...new Set(rows.flatMap(x=>x.topics||[]))];
  topic.innerHTML='<option value="all">All Topics</option>'+topics.map(v=>`<option value="${v}">${v}</option>`).join('');
  render();
});
[q,lang,layer,time,topic].forEach(el=>el.addEventListener(el.tagName==='INPUT'?'input':'change',render));
</script></body></html>"""


def briefing_page(ctx: dict) -> str:
    return """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>Daily Top10 Briefing</title>
<script src=\"./assets/metrics.js\" defer></script>
<script src=\"./assets/expert-limit.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}
.grid{margin-top:12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.card{position:relative;background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px}
.muted{color:#9db0da;font-size:12px}
.share{position:absolute;right:10px;top:10px}
.share summary{list-style:none;cursor:pointer;width:30px;height:30px;border-radius:999px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(125,177,255,.45);background:#16366d;color:#eaf2ff;font-size:14px}
.share summary::-webkit-details-marker{display:none}
.share-menu{position:absolute;right:0;top:36px;display:flex;flex-direction:column;gap:6px;background:#0f1933;border:1px solid rgba(255,255,255,.18);border-radius:10px;padding:8px;min-width:140px;z-index:20}
.share-menu button{cursor:pointer;border:1px solid rgba(125,177,255,.45);border-radius:8px;background:#17396f;color:#eaf2ff;padding:6px 8px;font-size:12px;text-align:left}
.share-menu button:hover{background:#1f4686}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>Top10 Briefing / 十大观点</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./index.html\">Home</a><a class=\"btn\" href=\"./insights.html\">Insights</a><a class=\"btn\" href=\"./daily_progress.html\">每日进展</a><a class=\"btn\" href=\"./topics.html\">热点词云</a><a class=\"btn\" href=\"./public_signals.html\">公共信号</a><a class=\"btn\" href=\"./poster.html?mode=top10\">Top10整合海报</a><a class=\"btn\" href=\"./poster.html?mode=custom\">自选博主海报</a><a class=\"btn\" href=\"./commercial.html\">Commercial</a><a class=\"btn\" href=\"./contact.html\">Contact</a></div></div>
<div class=\"card\" id=\"freshness\"></div>
<div id=\"grid\" class=\"grid\"></div></div>
<script>
function closeShareMenus(except){
  document.querySelectorAll('.share[open]').forEach(x=>{ if(x!==except) x.removeAttribute('open'); });
}
document.addEventListener('click',(e)=>{
  if(!e.target.closest('.share')) closeShareMenus(null);
});
function copyText(v){
  return navigator.clipboard.writeText(v);
}
fetch('./data/daily_briefing.json').then(r=>r.json()).then(d=>{
  fetch('./data/refresh_status.json').then(r=>r.json()).catch(()=>null).then(rs=>{
    const modeMap={x_api_v2:'X API',rjina_fallback:'网页回退源'};
    const mode=rs ? (modeMap[rs.mode]||rs.mode||'未知') : '未知';
    const stale = (d.updated_at||'').slice(0,10) !== new Date().toISOString().slice(0,10);
    const crawled = rs && rs.source_crawled_at ? ` · 最近抓取 ${String(rs.source_crawled_at).replace('T',' ').slice(0,19)}` : '';
    document.getElementById('freshness').innerHTML=`<div><b>内容时间：</b>${(d.updated_at||'-').replace('T',' ').slice(0,19)} <span class=\"muted\">· 页面生成 ${(d.built_at||'-').replace('T',' ').slice(0,19)} · 刷新来源 ${mode}${crawled}</span></div><div class=\"muted\" style=\"margin-top:6px\">${stale ? '当前展示的是最近一次可用内容，不代表所有账号今天都有新帖。' : '当前展示优先使用今天热度最高的内容。'}</div>`;
  });
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  const rows=(d.items||[]).slice(0, limit);
  if(!rows.length){
    document.getElementById('grid').innerHTML = `<div class=\"card\"><b>当前样本里暂时没有可展示内容</b><div class=\"muted\" style=\"margin-top:8px\">系统会优先展示当日热度最高的分享；如果没有当日内容，则回退到最近一次可用分享。当前返回为空，通常说明源数据还没有刷新成功。</div></div>`;
    return;
  }
  document.getElementById('grid').innerHTML=rows.map((r,i)=>{
    const shareLink = r.latest_tweet_url || `https://x.com/${r.handle}`;
    const profileLink = `${location.origin}${location.pathname.replace(/\\/[^/]*$/, '')}/profiles/${r.slug}.html`;
    return `<div class=\"card\">
      <details class=\"share\">
        <summary title=\"分享\">↗</summary>
        <div class=\"share-menu\">
          <button data-action=\"poster\" data-slug=\"${r.slug}\">下载海报</button>
          <button data-action=\"copy\" data-url=\"${shareLink}\" data-profile=\"${profileLink}\">复制链接</button>
          <button data-action=\"native\" data-url=\"${shareLink}\" data-title=\"${r.name}\">系统分享</button>
        </div>
      </details>
      <div><b>#${i+1} ${r.name}</b> <span class=\"muted\">@${r.handle}</span></div>
      <div class=\"muted\">score ${Number(r.score||0).toFixed(3)} · ${(r.topics||[]).join(' · ')}</div>
      <p><b>最新分享：</b>${r.latest_share_zh || r.latest_viewpoint_zh || r.daily_essence_zh || ''}</p>
      <div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./profiles/${r.slug}.html\">查看人物页</a><a class=\"btn\" href=\"https://x.com/${r.handle}\" target=\"_blank\">打开 X</a></div>
    </div>`;
  }).join('');

  document.querySelectorAll('.share').forEach(el=>{
    el.addEventListener('toggle',()=>{ if(el.open) closeShareMenus(el); });
  });
  document.querySelectorAll('.share-menu button').forEach(btn=>{
    btn.addEventListener('click', async (e)=>{
      e.preventDefault();
      const act = btn.dataset.action;
      const cardShare = btn.closest('.share');
      try{
        if(act==='poster'){
          const slug = btn.dataset.slug || '';
          location.href = `./poster.html?slug=${encodeURIComponent(slug)}&mode=briefing`;
          return;
        }
        if(act==='copy'){
          const url = btn.dataset.url || btn.dataset.profile || location.href;
          await copyText(url);
          alert('已复制链接');
          return;
        }
        if(act==='native'){
          const url = btn.dataset.url || location.href;
          const title = btn.dataset.title || 'Top10';
          if(navigator.share){
            await navigator.share({ title, url });
          }else{
            await copyText(url);
            alert('当前浏览器不支持系统分享，已复制链接');
          }
          return;
        }
      }catch(_err){
        alert('分享操作失败，请重试');
      }finally{
        if(cardShare) cardShare.removeAttribute('open');
      }
    });
  });
});
</script></body></html>"""


def daily_progress_page(ctx: dict) -> str:
    return """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>Daily Domain Progress</title>
<script src=\"./assets/metrics.js\" defer></script>
<script src=\"./assets/expert-limit.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}
.card{background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px;margin-top:10px}
.muted{color:#9db0da;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
.tag{display:inline-block;padding:4px 8px;border:1px solid rgba(255,255,255,.2);border-radius:999px;font-size:12px;margin-right:6px}
.quote{margin-top:8px;padding:8px 10px;border:1px solid rgba(106,211,255,.35);border-radius:10px;background:rgba(106,211,255,.08);line-height:1.5}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>Daily Domain Progress / 每日领域进展</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./index.html\">Home</a><a class=\"btn\" href=\"./insights.html\">Insights</a><a class=\"btn\" href=\"./daily_briefing.html\">Top10</a><a class=\"btn\" href=\"./topics.html\">热点词云</a><a class=\"btn\" href=\"./public_signals.html\">公共信号</a><a class=\"btn\" href=\"./poster.html?mode=top10\">Top10海报</a><a class=\"btn\" href=\"./commercial.html\">Commercial</a><a class=\"btn\" href=\"./contact.html\">Contact</a></div></div>
<div class=\"card\"><div id=\"sum_zh\" style=\"font-size:16px;font-weight:700\"></div><div id=\"sum_en\" class=\"muted\" style=\"margin-top:6px\"></div><div id=\"updated\" class=\"muted\" style=\"margin-top:8px\"></div></div>
<div class=\"card\" id=\"freshness\"></div>
<div class=\"card\"><h3 style=\"margin-top:0\">热门主题</h3><div id=\"topics\"></div></div>
<div class=\"card\"><h3 style=\"margin-top:0\">今日关键人物</h3><div id=\"trend\" class=\"grid\"></div></div>
</div>
<script>
fetch('./data/daily_progress.json').then(r=>r.json()).then(d=>{
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  document.getElementById('sum_zh').textContent=d.summary_zh||'';
  document.getElementById('sum_en').textContent=d.summary_en||'';
  const contentAt=((d.updated_at||'').slice(0,19).replace('T',' '));
  const builtAt=((d.built_at||'').slice(0,19).replace('T',' '));
  document.getElementById('updated').textContent='内容时间: '+contentAt+(builtAt?' · 页面生成: '+builtAt:'');
  fetch('./data/refresh_status.json').then(r=>r.json()).catch(()=>null).then(rs=>{
    const modeMap={x_api_v2:'X API',rjina_fallback:'网页回退源'};
    const mode=rs ? (modeMap[rs.mode]||rs.mode||'未知') : '未知';
    const stale = (d.updated_at||'').slice(0,10) !== new Date().toISOString().slice(0,10);
    const crawled = rs && rs.source_crawled_at ? ` · 最近抓取 ${String(rs.source_crawled_at).replace('T',' ').slice(0,19)}` : '';
    document.getElementById('freshness').innerHTML=`<div><b>数据说明：</b><span class=\"muted\">刷新来源 ${mode}${crawled} · 当前内容时间 ${contentAt||'-'}</span></div><div class=\"muted\" style=\"margin-top:6px\">${stale ? '本页总结基于最近一次可用抓取，不代表所有关键人物今天都有新分享。' : '本页总结基于今天抓到的分享内容生成。'}</div>`;
  });
  document.getElementById('topics').innerHTML=(d.topic_rank||[]).map(t=>`<span class=\"tag\">${t.topic} (${t.count})</span>`).join('');
  document.getElementById('trend').innerHTML=(d.trend_items||[]).slice(0, limit).map(r=>`<div class=\"card\" style=\"margin-top:0\"><div><b>${r.name}</b> <span class=\"muted\">@${r.handle}</span></div><div class=\"muted\">${(r.topics||[]).join(' · ')} · score ${Number(r.score||0).toFixed(3)}</div><div class=\"muted quote\">${r.latest_share_zh||r.latest_viewpoint_zh||r.daily_essence_zh||''}</div><div style=\"margin-top:8px;display:flex;gap:8px;flex-wrap:wrap\"><a class=\"btn\" href=\"./profiles/${r.slug}.html\">查看人物</a><a class=\"btn\" href=\"https://x.com/${r.handle}\" target=\"_blank\">打开 X</a><a class=\"btn\" href=\"./poster.html?slug=${r.slug}&mode=single\">海报</a></div></div>`).join('');
});
</script></body></html>"""


def poster_page(ctx: dict) -> str:
    return """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>Share Poster</title>
<script src=\"./assets/metrics.js\" defer></script>
<script src=\"./assets/expert-limit.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px;cursor:pointer}
.row{display:grid;grid-template-columns:minmax(320px,1fr) minmax(320px,1fr);gap:12px}
.card{background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px}
.styles,.modes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.chip{border:1px solid rgba(255,255,255,.25);padding:6px 10px;border-radius:999px;background:#0d1834;color:#d4e4ff;font-size:12px;cursor:pointer}
.chip.active{border-color:#6ad3ff;background:#123061}
.cfg{margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.cfg input{width:100%;background:#0f1a34;border:1px solid rgba(148,163,184,.35);color:#e2e8f0;border-radius:8px;padding:7px 8px;font-size:12px}
.meta{font-size:12px;color:var(--muted)} canvas{width:100%;max-width:460px;border-radius:12px;border:1px solid rgba(255,255,255,.2);background:#0a1022}
.picker{margin-top:10px;border:1px solid rgba(148,163,184,.25);border-radius:10px;padding:8px;max-height:300px;overflow:auto;background:#0f1832}
.picker .it{display:flex;justify-content:space-between;gap:8px;padding:5px 2px;font-size:12px;color:#d9e7ff}
@media(max-width:860px){.row{grid-template-columns:1fr}.cfg{grid-template-columns:1fr}}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>Share Poster / 一键转海报</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./index.html\">Home</a><a class=\"btn\" href=\"./insights.html\">Insights</a><a class=\"btn\" href=\"./daily_briefing.html\">Top10</a><a class=\"btn\" href=\"./daily_progress.html\">每日进展</a><a class=\"btn\" href=\"./topics.html\">热点词云</a><a class=\"btn\" href=\"./public_signals.html\">公共信号</a><a class=\"btn\" href=\"./commercial.html\">Commercial</a><a class=\"btn\" href=\"./contact.html\">Contact</a></div></div>
<div class=\"row\">
  <div class=\"card\">
    <div id=\"title\" style=\"font-size:22px;font-weight:800\">Loading...</div>
    <div id=\"desc\" class=\"meta\" style=\"margin-top:4px\"></div>
    <div id=\"essence\" style=\"margin-top:10px;line-height:1.6\"></div>
    <div class=\"modes\">
      <button class=\"chip\" data-mode=\"single\">单人海报</button>
      <button class=\"chip\" data-mode=\"top10\">Top10整合海报</button>
      <button class=\"chip\" data-mode=\"custom\">自选博主海报</button>
    </div>
    <div id=\"pickerWrap\" class=\"picker\" style=\"display:none\"></div>
    <div class=\"styles\">
      <button class=\"chip active\" data-style=\"clean\">简洁版</button>
      <button class=\"chip\" data-style=\"pro\">商务版</button>
      <button class=\"chip\" data-style=\"vivid\">活力版</button>
      <button class=\"chip\" data-style=\"brand\">品牌版</button>
    </div>
    <div class=\"cfg\">
      <input id=\"brandColor\" placeholder=\"品牌色，如 #2f7cff\" />
      <input id=\"brandSlogan\" placeholder=\"品牌标语，如 AI Influence Daily\" />
      <input id=\"brandLogo\" style=\"grid-column:1/-1\" placeholder=\"Logo URL（可选）\" />
    </div>
    <div class=\"meta\" style=\"margin-top:10px\">Poster size: 1080x1920 · single/top10/custom supported</div>
    <div style=\"display:flex;gap:8px;flex-wrap:wrap;margin-top:10px\">
      <button class=\"btn\" id=\"downloadBtn\">下载海报 PNG</button>
      <button class=\"btn\" id=\"copyBtn\">复制分享链接</button>
      <a class=\"btn\" id=\"openProfile\" href=\"#\">打开博主页</a>
      <a class=\"btn\" id=\"openX\" href=\"#\" target=\"_blank\">打开 X</a>
    </div>
  </div>
  <div class=\"card\" style=\"display:flex;justify-content:center;align-items:center\">
    <canvas id=\"poster\" width=\"1080\" height=\"1920\"></canvas>
  </div>
</div></div>
<script>
const params=new URLSearchParams(location.search);
const slug=params.get('slug')||'';
const modeFromUrl=(params.get('mode')||'single').toLowerCase();
const lang=params.get('lang')||'zh';
let styleKey=params.get('style')||'clean';
let posterMode = (modeFromUrl==='top10'||modeFromUrl==='custom') ? modeFromUrl : 'single';
const brandColorInput=document.getElementById('brandColor');
const brandSloganInput=document.getElementById('brandSlogan');
const brandLogoInput=document.getElementById('brandLogo');
const pickerWrap=document.getElementById('pickerWrap');
brandColorInput.value=params.get('brand')||'#2f7cff';
brandSloganInput.value=params.get('slogan')||'AI Influence Daily';
brandLogoInput.value=params.get('logo')||'';
const c=document.getElementById('poster');
const ctx=c.getContext('2d');
let rows=[]; let top10=[]; let currentItem=null;
let selectedSlugs=(params.get('slugs')||'').split(',').map(x=>x.trim()).filter(Boolean);

function wrapText(ctx,text,x,y,maxWidth,lineHeight,maxLines){
  const chars=(text||'').split('');
  let line=''; let lines=0;
  for(let i=0;i<chars.length;i++){
    const testLine=line+chars[i];
    if(ctx.measureText(testLine).width>maxWidth && line){
      ctx.fillText(line,x,y+lines*lineHeight); line=chars[i]; lines++;
      if(maxLines && lines>=maxLines){ return; }
    } else { line=testLine; }
  }
  if(!maxLines || lines<maxLines){ ctx.fillText(line,x,y+lines*lineHeight); }
}

function getTheme(){
  const brandColor=(brandColorInput.value||'#2f7cff').trim() || '#2f7cff';
  return {
    clean:{bg:['#0f2a5f','#0b1737','#0a1022'],panel:'rgba(255,255,255,0.08)',panelStroke:'rgba(255,255,255,0.16)',title:'#dff1ff',meta:'#9ec0f1',box:'rgba(106,211,255,.2)',boxStroke:'rgba(106,211,255,.5)'},
    pro:{bg:['#142018','#101e2a','#0a111b'],panel:'rgba(255,255,255,0.06)',panelStroke:'rgba(122,199,158,.26)',title:'#e8fff2',meta:'#9ad2b2',box:'rgba(73,214,166,.18)',boxStroke:'rgba(73,214,166,.45)'},
    vivid:{bg:['#45236e','#1b2f6d','#0a1022'],panel:'rgba(255,255,255,0.07)',panelStroke:'rgba(255,163,102,.28)',title:'#ffe9d6',meta:'#ffd0a8',box:'rgba(255,163,102,.20)',boxStroke:'rgba(255,163,102,.52)'},
    brand:{bg:[brandColor,'#1a2444','#0a1022'],panel:'rgba(255,255,255,0.08)',panelStroke:'rgba(255,255,255,.2)',title:'#ffffff',meta:'#dce8ff',box:'rgba(255,255,255,.14)',boxStroke:'rgba(255,255,255,.44)'}
  }[styleKey] || null;
}

function drawBackground(theme){
  const w=1080,h=1920;
  const g=ctx.createLinearGradient(0,0,w,h);
  g.addColorStop(0,theme.bg[0]); g.addColorStop(0.45,theme.bg[1]); g.addColorStop(1,theme.bg[2]);
  ctx.fillStyle=g; ctx.fillRect(0,0,w,h);
  ctx.fillStyle=theme.panel; ctx.fillRect(60,60,w-120,h-120);
  ctx.strokeStyle=theme.panelStroke; ctx.lineWidth=2; ctx.strokeRect(60,60,w-120,h-120);
}

function drawSingle(r){
  const theme=getTheme(); drawBackground(theme);
  const brandSlogan=(brandSloganInput.value||'AI Influence Daily').trim() || 'AI Influence Daily';
  const noTodayShare = !(r && (r.latest_share_zh || r.latest_share_en));
  const buddy = pickBestBuddyInScope(r);
  ctx.fillStyle=theme.title; ctx.font='700 58px \"IBM Plex Sans\",sans-serif'; ctx.fillText('AI Insight Poster',100,170);
  ctx.fillStyle=theme.meta; ctx.font='500 34px \"IBM Plex Sans\",sans-serif'; ctx.fillText(`@${r.handle} | score ${Number(r.score||0).toFixed(3)} | ${r.layer_en||r.layer||''}`,100,235);
  ctx.fillStyle='#ffffff'; ctx.font='800 70px \"IBM Plex Sans\",sans-serif'; wrapText(ctx,r.name||'',100,350,860,86,2);
  ctx.fillStyle='#bed6ff'; ctx.font='500 34px \"IBM Plex Sans\",sans-serif'; wrapText(ctx,(r.topics||[]).join(' · '),100,540,860,48,3);
  ctx.fillStyle='#eef5ff'; ctx.font='600 44px \"IBM Plex Sans\",sans-serif'; ctx.fillText(lang==='en'?'Latest Share':'最新分享',100,760);
  ctx.fillStyle='#d8e7ff'; ctx.font='500 38px \"IBM Plex Sans\",sans-serif';
  wrapText(
    ctx,
    noTodayShare
      ? (lang==='en' ? 'No share today. Please switch to another creator.' : '无分享，请换一个。')
      : (lang==='en' ? (r.latest_share_en||r.latest_viewpoint_en||r.daily_essence_en||'') : (r.latest_share_zh||r.latest_viewpoint_zh||r.daily_essence_zh||'')),
    100,835,880,54,10
  );
  ctx.fillStyle='#9ec0f1'; ctx.font='500 30px \"IBM Plex Sans\",sans-serif';
  ctx.fillText(buddy?`今日最佳基友: ${buddy.name} @${buddy.handle}`:'今日最佳基友: N/A',100,1448);
  ctx.fillStyle=theme.box; ctx.fillRect(100,1490,880,240); ctx.strokeStyle=theme.boxStroke; ctx.strokeRect(100,1490,880,240);
  ctx.fillStyle='#a9d7ff'; ctx.font='500 34px \"IBM Plex Sans\",sans-serif'; ctx.fillText(styleKey==='brand'?brandSlogan:'Association + Centrality',130,1560);
  ctx.fillStyle='#ecf5ff'; ctx.font='700 52px \"IBM Plex Sans\",sans-serif'; ctx.fillText(`A ${Number(r.association_score||0).toFixed(3)} / C ${Number(r.centrality_score||0).toFixed(3)}`,130,1640);
  ctx.fillStyle='#a9d7ff'; ctx.font='500 30px \"IBM Plex Sans\",sans-serif'; ctx.fillText('x-ai-experts-viz · shareable insight card',130,1710);
  ctx.fillStyle='#8ab5e8'; ctx.font='500 26px \"IBM Plex Sans\",sans-serif'; ctx.fillText(`https://x.com/${r.handle}`,100,1830);
}

function drawMulti(items){
  const theme=getTheme(); drawBackground(theme);
  ctx.fillStyle=theme.title; ctx.font='700 56px \"IBM Plex Sans\",sans-serif';
  ctx.fillText(posterMode==='top10'?'Top10 AI Views':'Custom AI Views',100,160);
  ctx.fillStyle=theme.meta; ctx.font='500 30px \"IBM Plex Sans\",sans-serif';
  ctx.fillText(`Count ${items.length} · ${new Date().toISOString().slice(0,10)}`,100,215);
  let y=290;
  items.slice(0,10).forEach((r,i)=>{
    ctx.fillStyle='rgba(255,255,255,.08)'; ctx.fillRect(90,y-46,900,145);
    ctx.strokeStyle='rgba(255,255,255,.15)'; ctx.strokeRect(90,y-46,900,145);
    ctx.fillStyle='#eaf4ff'; ctx.font='700 34px \"IBM Plex Sans\",sans-serif'; ctx.fillText(`#${i+1} ${r.name}`,120,y);
    ctx.fillStyle='#a9c8f3'; ctx.font='500 26px \"IBM Plex Sans\",sans-serif'; ctx.fillText(`@${r.handle} · score ${Number(r.score||0).toFixed(3)}`,120,y+42);
    ctx.fillStyle='#d6e5ff'; ctx.font='500 24px \"IBM Plex Sans\",sans-serif'; wrapText(ctx,(r.topics||[]).slice(0,2).join(' · ')||'AI Topic',120,y+78,760,34,1);
    y+=165;
  });
  ctx.fillStyle='rgba(255,255,255,.12)'; ctx.fillRect(90,1720,900,120);
  ctx.fillStyle='#dbe8ff'; ctx.font='600 30px \"IBM Plex Sans\",sans-serif';
  ctx.fillText((brandSloganInput.value||'AI Influence Daily').trim() || 'AI Influence Daily',120,1788);
}

function pickRows(){
  if(posterMode==='top10') return top10.slice(0,10);
  if(posterMode==='custom'){
    const picked=rows.filter(r=>selectedSlugs.includes(r.slug)).slice(0,10);
    return picked.length?picked:top10.slice(0,10);
  }
  return [currentItem || rows[0]].filter(Boolean);
}

function scopeSlugs(){
  if(posterMode==='custom'){
    return new Set((selectedSlugs||[]).filter(Boolean));
  }
  if(posterMode==='top10'){
    return new Set(top10.slice(0,10).map(x=>x.slug).filter(Boolean));
  }
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  return new Set(rows.slice(0, limit).map(x=>x.slug).filter(Boolean));
}

function pickBestBuddyInScope(r){
  const scope = scopeSlugs();
  const buddies = (r && r.best_buddies) ? r.best_buddies : [];
  if(!buddies.length) return null;
  const inScope = buddies.filter(b=>b && b.slug && scope.has(b.slug));
  return (inScope[0] || buddies[0] || null);
}

function setInfo(items){
  if(items.length===1){
    const r=items[0];
    const noTodayShare = !(r && (r.latest_share_zh || r.latest_share_en));
    const buddy = pickBestBuddyInScope(r);
    document.getElementById('title').textContent=`${r.name} @${r.handle}`;
    document.getElementById('desc').textContent=`Layer ${r.layer_en||r.layer} · score ${Number(r.score||0).toFixed(3)} · mode single${buddy?` · 今日最佳基友 ${buddy.name}`:''}`;
    document.getElementById('essence').textContent=noTodayShare
      ? '无分享，请换一个。'
      : (lang==='en'?(r.latest_share_en||r.latest_viewpoint_en||r.daily_essence_en||''):(r.latest_share_zh||r.latest_viewpoint_zh||r.daily_essence_zh||''));
    document.getElementById('openProfile').style.display='inline-block';
    document.getElementById('openX').style.display='inline-block';
    document.getElementById('openProfile').href=`./profiles/${r.slug}.html`;
    document.getElementById('openX').href=`https://x.com/${r.handle}`;
  }else{
    document.getElementById('title').textContent=`${posterMode==='top10'?'Top10':'自选'} 聚合海报`;
    document.getElementById('desc').textContent=`共 ${items.length} 位博主 · mode ${posterMode}`;
    document.getElementById('essence').textContent='可一键分享整页观点，适合日报、周报、社群分发。';
    document.getElementById('openProfile').style.display='none';
    document.getElementById('openX').style.display='none';
  }
}

function draw(){
  const items=pickRows(); if(!items.length) return;
  setInfo(items);
  if(items.length===1) drawSingle(items[0]); else drawMulti(items);
}

function renderPicker(){
  if(posterMode!=='custom'){ pickerWrap.style.display='none'; return; }
  pickerWrap.style.display='block';
  const list=rows.slice(0,80);
  pickerWrap.innerHTML=list.map(r=>`<label class=\"it\"><span>${r.name} @${r.handle}</span><input type=\"checkbox\" data-slug=\"${r.slug}\" ${selectedSlugs.includes(r.slug)?'checked':''}></label>`).join('');
  pickerWrap.querySelectorAll('input[type=\"checkbox\"]').forEach(cb=>{
    cb.addEventListener('change',()=>{
      const slug=cb.dataset.slug;
      if(cb.checked){ if(!selectedSlugs.includes(slug)) selectedSlugs.push(slug); }
      else{ selectedSlugs=selectedSlugs.filter(s=>s!==slug); }
      selectedSlugs=selectedSlugs.slice(0,10);
      draw();
    });
  });
}

document.getElementById('downloadBtn').addEventListener('click',()=>{
  const a=document.createElement('a');
  a.href=c.toDataURL('image/png');
  a.download=`${posterMode}-${styleKey}.png`;
  a.click();
});
document.getElementById('copyBtn').addEventListener('click',async()=>{
  const u=new URL(location.href);
  u.searchParams.set('mode', posterMode);
  u.searchParams.set('style',styleKey);
  u.searchParams.set('brand', brandColorInput.value || '#2f7cff');
  u.searchParams.set('slogan', brandSloganInput.value || 'AI Influence Daily');
  if(selectedSlugs.length) u.searchParams.set('slugs', selectedSlugs.join(','));
  else u.searchParams.delete('slugs');
  if((brandLogoInput.value||'').trim()) u.searchParams.set('logo', brandLogoInput.value.trim());
  else u.searchParams.delete('logo');
  const url=u.toString();
  try{ await navigator.clipboard.writeText(url); alert('已复制分享链接'); } catch(e){ prompt('复制这个链接:', url); }
});

document.querySelectorAll('[data-style]').forEach(btn=>{
  if(btn.dataset.style===styleKey) btn.classList.add('active');
  btn.addEventListener('click',()=>{
    styleKey=btn.dataset.style;
    document.querySelectorAll('[data-style]').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    draw();
  });
});
document.querySelectorAll('[data-mode]').forEach(btn=>{
  if(btn.dataset.mode===posterMode) btn.classList.add('active');
  btn.addEventListener('click',()=>{
    posterMode=btn.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    renderPicker();
    draw();
  });
});
[brandColorInput,brandSloganInput,brandLogoInput].forEach(el=>el.addEventListener('input',draw));

Promise.all([
  fetch('./data/profiles.json').then(r=>r.json()).catch(()=>({items:[]})),
  fetch('./data/daily_briefing.json').then(r=>r.json()).catch(()=>({items:[]}))
]).then(([p,b])=>{
  const limit = window.XAIExpertLimit ? window.XAIExpertLimit.getLimit(300) : 300;
  rows=(p.items||[]).slice(0, limit);
  top10=(b.items||[]).slice(0, limit);
  currentItem=rows.find(x=>x.slug===slug) || top10.find(x=>x.slug===slug) || rows[0] || null;
  if(!selectedSlugs.length) selectedSlugs=top10.slice(0,10).map(x=>x.slug).filter(Boolean);
  renderPicker();
  draw();
});
</script></body></html>"""


def topics_page(ctx: dict, topic_cloud: dict) -> str:
    page = """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>
<title>Topic Cloud</title>
<script src=\"./assets/metrics.js\" defer></script>
<style>
:root{--bg:#0a1022;--card:#121b36;--line:rgba(255,255,255,.14);--text:#edf3ff;--muted:#95a9d5;--brand:#6ad3ff}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 10% 0%, #19356d 0%, var(--bg) 44%);color:var(--text);font-family:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 12px;border-radius:10px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;text-decoration:none;font-size:13px}
.row{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(320px,.8fr);gap:12px}
.card{background:#111a34;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px}
.muted{color:#9db0da;font-size:12px}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}
.search{flex:1 1 260px;min-width:240px;padding:12px 14px;border-radius:12px;border:1px solid rgba(255,255,255,.14);background:rgba(8,14,28,.55);color:var(--text);outline:none;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.search:focus{border-color:rgba(106,211,255,.55);box-shadow:0 0 0 3px rgba(106,211,255,.12)}
.seg{display:inline-flex;gap:4px;padding:4px;border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(9,15,30,.65)}
.seg-btn,.ghost-btn,.mini{border:0;cursor:pointer;font:inherit}
.seg-btn{padding:8px 12px;border-radius:999px;background:transparent;color:#d7e6ff;font-size:12px}
.seg-btn.active{background:linear-gradient(135deg,#1d3f82,#143062);color:#fff}
.ghost-btn{padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);color:#dceaff}
.ghost-btn:hover{border-color:rgba(106,211,255,.45);background:rgba(106,211,255,.08)}
.meta-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.stat-pill{display:inline-flex;align-items:center;gap:6px;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.10);font-size:12px;color:#dce8ff}
.section{margin-top:14px}
.section-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}
.section-title{font-size:13px;font-weight:700;letter-spacing:.02em;color:#dfeaff}
.section.hidden{display:none}
.cloud{display:flex;flex-wrap:wrap;gap:10px;align-content:flex-start;min-height:420px;padding-top:4px}
.term{display:inline-flex;align-items:center;justify-content:center;padding:8px 12px;border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(106,211,255,.08);color:#eaf4ff;cursor:pointer;transform-origin:center;transition:transform .18s ease,border-color .18s ease,background .18s ease,box-shadow .18s ease;animation:floatIn .28s ease both}
.term:hover,.term.active{transform:translateY(-2px) scale(1.02);border-color:rgba(106,211,255,.55);background:rgba(106,211,255,.18);box-shadow:0 10px 26px rgba(16,31,73,.28)}
.pill{display:inline-flex;gap:6px;align-items:center;padding:7px 11px;border:1px solid rgba(255,255,255,.16);border-radius:999px;margin:0 8px 8px 0;font-size:12px;cursor:pointer;transition:transform .18s ease,border-color .18s ease,background .18s ease}
.pill:hover,.pill.active{transform:translateY(-1px);border-color:rgba(106,211,255,.55);background:rgba(106,211,255,.12)}
.panel-hero{padding:14px;border-radius:14px;background:linear-gradient(180deg,rgba(106,211,255,.14),rgba(106,211,255,.04));border:1px solid rgba(106,211,255,.20);margin-top:12px}
.hero-kicker{display:inline-flex;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);font-size:11px;letter-spacing:.03em;text-transform:uppercase;color:#c9defd}
.hero-title{margin:10px 0 4px;font-size:26px;line-height:1.1}
.hero-preview{margin-top:10px;color:#d8e6ff;font-size:13px;line-height:1.6}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}
.stat-card{padding:10px 12px;border-radius:12px;background:#0f1831;border:1px solid rgba(255,255,255,.12)}
.stat-card .k{font-size:11px;color:#90a5d2;text-transform:uppercase;letter-spacing:.04em}
.stat-card .v{margin-top:6px;font-size:18px;font-weight:700;color:#edf4ff}
.related-block{margin-top:14px}
.related-wrap{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.related-chip{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);cursor:pointer;color:#e6f1ff;transition:background .18s ease,border-color .18s ease}
.related-chip:hover{background:rgba(106,211,255,.10);border-color:rgba(106,211,255,.45)}
.list{display:grid;gap:8px;margin-top:12px}
.item{border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px;background:#0f1831;transition:transform .16s ease,border-color .16s ease,background .16s ease}
.item:hover{transform:translateY(-1px);border-color:rgba(106,211,255,.35);background:#122044}
.item-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.item-name{color:#eef4ff;text-decoration:none}
.item-name:hover{color:#6ad3ff}
.item-actions{display:flex;gap:6px;flex-wrap:wrap}
.mini{display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#dcebff;text-decoration:none;font-size:12px}
.mini:hover{border-color:rgba(106,211,255,.45);background:rgba(106,211,255,.10)}
.empty{padding:16px;border:1px dashed rgba(255,255,255,.16);border-radius:12px;color:#9db0da;background:rgba(255,255,255,.03)}
@keyframes floatIn{from{opacity:0;transform:translateY(6px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}
@media (max-width:860px){.row{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr 1fr}}
@media (max-width:620px){.stats{grid-template-columns:1fr}.toolbar{align-items:stretch}.seg{width:100%;justify-content:space-between}.ghost-btn{width:100%}}
</style></head><body><div class=\"wrap\">
<div class=\"top\"><h2>Topic Cloud / 热点词云</h2><div style=\"display:flex;gap:8px\"><a class=\"btn\" href=\"./index.html\">Home</a><a class=\"btn\" href=\"./insights.html\">Insights</a><a class=\"btn\" href=\"./daily_briefing.html\">Top10</a><a class=\"btn\" href=\"./daily_progress.html\">每日进展</a><a class=\"btn\" href=\"./profiles/index.html\">Profiles</a><a class=\"btn\" href=\"./public_signals.html\">公共信号</a><a class=\"btn\" href=\"./commercial.html\">Commercial</a><a class=\"btn\" href=\"./contact.html\">Contact</a></div></div>
<div class=\"card\" id=\"summary\" style=\"margin-top:10px\"></div>
<div class=\"row\" style=\"margin-top:12px\">
  <div class=\"card\">
    <div style=\"display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap\">
      <h3 id=\"cloudTitle\" style=\"margin:0\">热点词云</h3>
      <div class=\"muted\" id=\"cloudHint\">点击词或主题，查看对应人物</div>
    </div>
    <div class=\"toolbar\">
      <input id=\"searchInput\" class=\"search\" type=\"search\" placeholder=\"搜索主题、热词、博主名或 @handle\"/>
      <div class=\"seg\" id=\"viewSwitch\">
        <button class=\"seg-btn active\" data-view=\"all\">全部</button>
        <button class=\"seg-btn\" data-view=\"topics\">主题</button>
        <button class=\"seg-btn\" data-view=\"terms\">热词</button>
      </div>
      <button class=\"ghost-btn\" id=\"clearBtn\">清空选择</button>
    </div>
    <div id=\"topicsMeta\" class=\"meta-strip\"></div>
    <div id=\"topicsSection\" class=\"section\">
      <div class=\"section-head\">
        <div class=\"section-title\" id=\"topicHeading\">热门主题</div>
      </div>
      <div id=\"topics\"></div>
    </div>
    <div id=\"termsSection\" class=\"section\">
      <div class=\"section-head\">
        <div class=\"section-title\" id=\"termHeading\">高频热词</div>
      </div>
      <div id=\"cloud\" class=\"cloud\"></div>
    </div>
  </div>
  <div class=\"card\">
    <h3 id=\"detailTitle\" style=\"margin:0\">关联人物</h3>
    <div class=\"muted\" id=\"selectionNote\" style=\"margin-top:8px\">先选择一个话题或热词</div>
    <div id=\"selectionHero\" class=\"panel-hero\"></div>
    <div id=\"selectionStats\" class=\"stats\"></div>
    <div id=\"related\" class=\"related-block\"></div>
    <div id=\"list\" class=\"list\"></div>
  </div>
</div></div>
<script>
let topicRows=[]; let termRows=[]; let activeTopic=''; let activeTerm=''; let viewMode='all';
const fallbackTopicCloud=__TOPIC_CLOUD_FALLBACK__;
function escapeHtml(v){ return String(v||'').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[ch])); }
function currentLang(){ return (localStorage.getItem('xai_lang') || 'zh') === 'zh' ? 'zh' : 'en'; }
function t(zh,en){ return currentLang()==='zh' ? zh : en; }
function normalize(v){ return String(v||'').toLowerCase(); }
function personKey(p){ return normalize(p.slug || p.handle || p.name || ''); }
function uniquePeople(rows){
  const seen = new Set();
  return (rows || []).filter(p => {
    const key = personKey(p);
    if(!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function queryValue(){ return normalize((document.getElementById('searchInput') || {}).value || ''); }
function rowMatches(row, labelKey){
  const q = queryValue();
  if(!q) return true;
  const peopleText = (row.people || []).map(p => `${p.name || ''} ${p.handle || ''}`).join(' ');
  return normalize(`${row[labelKey] || ''} ${peopleText}`).includes(q);
}
function filteredTopics(){ return topicRows.filter(row => rowMatches(row, 'topic')); }
function filteredTerms(){ return termRows.filter(row => rowMatches(row, 'term')); }
function selectedLabel(){ return activeTerm || activeTopic || ''; }
function clearSelection(resetQuery){
  activeTopic=''; activeTerm='';
  if(resetQuery){
    const input = document.getElementById('searchInput');
    if(input) input.value='';
  }
  renderAll();
}
function overlapCount(sourcePeople, targetPeople){
  const source = new Set((sourcePeople || []).map(personKey));
  let count = 0;
  (targetPeople || []).forEach(p => { if(source.has(personKey(p))) count += 1; });
  return count;
}
function relatedRowsForPeople(people){
  if(!people.length) return { title: '', rows: [], kind: '' };
  if(activeTerm){
    const rows = topicRows
      .map(r => ({ name: r.topic, count: overlapCount(people, r.people || []), total: r.count, kind: 'topic' }))
      .filter(r => r.count > 0)
      .sort((a,b) => b.count - a.count || b.total - a.total)
      .slice(0, 6);
    return { title: t('相关主题', 'Related Topics'), rows, kind: 'topic' };
  }
  if(activeTopic){
    const rows = termRows
      .map(r => ({ name: r.term, count: overlapCount(people, r.people || []), total: r.count, kind: 'term' }))
      .filter(r => r.count > 0)
      .sort((a,b) => b.count - a.count || b.total - a.total)
      .slice(0, 8);
    return { title: t('相关热词', 'Related Terms'), rows, kind: 'term' };
  }
  return { title: '', rows: [], kind: '' };
}
function renderLocale(){
  document.documentElement.lang = currentLang()==='zh' ? 'zh-CN' : 'en';
  document.title = t('热点词云', 'Topic Cloud');
  const nav = [t('首页', 'Home'), t('最新分享', 'Latest Shares'), 'Top10', t('每日进展', 'Daily Progress'), t('人物库', 'Profiles'), t('公共信号', 'Public Signals'), t('商业化', 'Commercial'), t('联系', 'Contact')];
  document.querySelectorAll('.top .btn').forEach((btn, idx) => { if(nav[idx]) btn.textContent = nav[idx]; });
  const title = document.querySelector('.top h2'); if(title) title.textContent = t('热点词云', 'Topic Cloud');
  const hint = document.getElementById('cloudHint'); if(hint) hint.textContent = t('点击词或主题，查看对应人物', 'Click a topic or term to inspect linked creators');
  const cloudTitle = document.getElementById('cloudTitle'); if(cloudTitle) cloudTitle.textContent = t('热点词云', 'Topic Cloud');
  const topicHeading = document.getElementById('topicHeading'); if(topicHeading) topicHeading.textContent = t('热门主题', 'Top Topics');
  const termHeading = document.getElementById('termHeading'); if(termHeading) termHeading.textContent = t('高频热词', 'Top Terms');
  const detailTitle = document.getElementById('detailTitle'); if(detailTitle) detailTitle.textContent = t('关联人物', 'Linked Creators');
  const search = document.getElementById('searchInput'); if(search) search.placeholder = t('搜索主题、热词、博主名或 @handle', 'Search topics, terms, creator names, or @handle');
  const clearBtn = document.getElementById('clearBtn'); if(clearBtn) clearBtn.textContent = t('清空选择', 'Clear');
  document.querySelectorAll('[data-view]').forEach(btn => {
    const label = btn.dataset.view === 'all' ? t('全部', 'All') : btn.dataset.view === 'topics' ? t('主题', 'Topics') : t('热词', 'Terms');
    btn.textContent = label;
  });
}
function renderMeta(){
  const topics = filteredTopics();
  const terms = filteredTerms();
  const query = queryValue();
  const meta = document.getElementById('topicsMeta');
  if(!meta) return;
  meta.innerHTML = [
    `<span class=\"stat-pill\">${t('主题', 'Topics')} ${topics.length}/${topicRows.length}</span>`,
    `<span class=\"stat-pill\">${t('热词', 'Terms')} ${terms.length}/${termRows.length}</span>`,
    `<span class=\"stat-pill\">${t('模式', 'Mode')} ${viewMode==='all' ? t('全部', 'All') : viewMode==='topics' ? t('主题', 'Topics') : t('热词', 'Terms')}</span>`,
    query ? `<span class=\"stat-pill\">${t('搜索', 'Search')} “${escapeHtml(query)}”</span>` : ''
  ].join('');
}
function applyPayload(d){
  if(!d || ((!d.topics || !d.topics.length) && (!d.terms || !d.terms.length))) return false;
  topicRows=d.topics||[];
  termRows=d.terms||[];
  document.getElementById('summary').innerHTML=`<div><b>${escapeHtml((d.domain||{}).domain_name_en||'Domain')} Topic Cloud</b><span class=\"muted\"> · 内容时间 ${(d.updated_at||'-').replace('T',' ').slice(0,19)} · 页面生成 ${(d.built_at||'-').replace('T',' ').slice(0,19)}</span></div><div style=\"margin-top:8px\">${escapeHtml(d.summary_zh||'')}</div><div class=\"muted\" style=\"margin-top:6px\">${escapeHtml(d.summary_en||'')}</div>`;
  renderAll();
  return true;
}
function renderAll(){
  renderLocale();
  renderMeta();
  renderTopics();
  renderTerms();
  renderSelection();
}
function renderSelection(){
  const list=document.getElementById('list');
  const note=document.getElementById('selectionNote');
  const hero=document.getElementById('selectionHero');
  const stats=document.getElementById('selectionStats');
  const related=document.getElementById('related');
  const query=queryValue();
  let people=[];
  let label='';
  let kind='';
  if(activeTerm){
    const row=termRows.find(x=>x.term===activeTerm);
    people=row ? uniquePeople(row.people||[]) : [];
    label = activeTerm;
    kind = t('热词', 'Term');
    note.textContent=`热词：${activeTerm} · 关联 ${people.length} 位人物`;
  }else if(activeTopic){
    const row=topicRows.find(x=>x.topic===activeTopic);
    people=row ? uniquePeople(row.people||[]) : [];
    label = activeTopic;
    kind = t('主题', 'Topic');
    note.textContent=`主题：${activeTopic} · 关联 ${people.length} 位人物`;
  }else if(query){
    people = uniquePeople([
      ...filteredTopics().flatMap(r => r.people || []),
      ...filteredTerms().flatMap(r => r.people || [])
    ]).slice(0, 24);
    label = query;
    kind = t('搜索结果', 'Search Results');
    note.textContent = currentLang()==='zh' ? `搜索：${query} · 命中 ${people.length} 位人物` : `Search: ${query} · matched ${people.length} creators`;
  }else{
    note.textContent='先选择一个话题或热词';
  }
  const relatedInfo = relatedRowsForPeople(people);
  const preview = people.slice(0, 4).map(p => p.name || p.handle || '').filter(Boolean).join(' · ');
  hero.innerHTML = label ? `
    <div class=\"hero-kicker\">${escapeHtml(kind)}</div>
    <div class=\"hero-title\">${escapeHtml(label)}</div>
    <div class=\"muted\">${t('当前选中对象会同步过滤右侧人物与联动项。', 'The current selection drives the creator panel and related shortcuts.')}</div>
    <div class=\"hero-preview\">${preview ? escapeHtml(preview) : t('当前还没有足够的关联人物。', 'No linked creators yet for this selection.')}</div>
  ` : `
    <div class=\"hero-kicker\">${t('探索模式', 'Explore')}</div>
    <div class=\"hero-title\">${t('先从一个主题或热词开始', 'Start from a topic or term')}</div>
    <div class=\"hero-preview\">${t('左侧支持搜索、切换主题/热词视图，以及点击相关词继续钻取。', 'Use the left side to search, switch views, and keep drilling down through related words.')}</div>
  `;
  stats.innerHTML = [
    { k: t('当前类型', 'Type'), v: label ? kind : t('未选择', 'None') },
    { k: t('匹配人物', 'Creators'), v: String(people.length) },
    { k: relatedInfo.title || t('联动项', 'Related'), v: String((relatedInfo.rows || []).length) }
  ].map(card => `<div class=\"stat-card\"><div class=\"k\">${escapeHtml(card.k)}</div><div class=\"v\">${escapeHtml(card.v)}</div></div>`).join('');
  related.innerHTML = relatedInfo.rows.length ? `<div class=\"muted\">${escapeHtml(relatedInfo.title)}</div><div class=\"related-wrap\">${relatedInfo.rows.map(row => `<button class=\"related-chip\" data-related-kind=\"${row.kind}\" data-related-name=\"${escapeHtml(row.name)}\">${escapeHtml(row.name)} <span class=\"muted\">${t('重叠', 'Overlap')} ${row.count}</span></button>`).join('')}</div>` : '';
  related.querySelectorAll('[data-related-kind]').forEach(el => el.addEventListener('click', () => {
    if(el.dataset.relatedKind === 'topic'){
      activeTopic = el.dataset.relatedName || '';
      activeTerm = '';
      viewMode = 'topics';
    } else {
      activeTerm = el.dataset.relatedName || '';
      activeTopic = '';
      viewMode = 'terms';
    }
    renderAll();
  }));
  list.innerHTML=people.length ? people.map(p=>`<div class=\"item\"><div class=\"item-top\"><div><a class=\"item-name\" href=\"./profiles/${encodeURIComponent(p.slug||'')}.html\"><b>${escapeHtml(p.name||'')}</b></a><div class=\"muted\" style=\"margin-top:4px\">@${escapeHtml(p.handle||'')}</div></div><div class=\"item-actions\"><a class=\"mini\" href=\"./profiles/${encodeURIComponent(p.slug||'')}.html\">${t('画像', 'Profile')}</a><a class=\"mini\" target=\"_blank\" rel=\"noreferrer\" href=\"https://x.com/${encodeURIComponent(p.handle||'')}\">X</a></div></div></div>`).join('') : `<div class=\"empty\">${escapeHtml(label ? t('当前筛选下没有匹配人物，可以切换相关词继续查看。', 'No creators matched this selection. Try a related shortcut or clear the filters.') : t('暂无匹配人物', 'No linked creators'))}</div>`;
}
function renderTopics(){
  const wrap=document.getElementById('topics');
  const section = document.getElementById('topicsSection');
  const rows = filteredTopics();
  if(section) section.classList.toggle('hidden', viewMode==='terms');
  wrap.innerHTML=rows.length ? rows.map(r=>`<span class=\"pill ${activeTopic===r.topic?'active':''}\" data-topic=\"${escapeHtml(r.topic)}\">${escapeHtml(r.topic)} <span class=\"muted\">(${r.count})</span></span>`).join('') : `<div class=\"empty\">${escapeHtml(t('没有命中的主题，换个词试试。', 'No topics matched. Try another query.'))}</div>`;
  wrap.querySelectorAll('[data-topic]').forEach(el=>el.addEventListener('click',()=>{
    activeTopic = el.dataset.topic === activeTopic ? '' : el.dataset.topic;
    activeTerm = '';
    renderAll();
  }));
}
function renderTerms(){
  const cloud=document.getElementById('cloud');
  const section = document.getElementById('termsSection');
  const rows = filteredTerms();
  if(section) section.classList.toggle('hidden', viewMode==='topics');
  cloud.innerHTML=rows.length ? rows.map((r,idx)=>{
    const hue = 192 + (idx % 8) * 12;
    return `<span class=\"term ${activeTerm===r.term?'active':''}\" data-term=\"${escapeHtml(r.term)}\" style=\"font-size:${r.font_size}px;transform:rotate(${r.angle}deg);background:hsla(${hue},85%,68%,0.10);animation-delay:${Math.min(idx,18)*0.018}s\">${escapeHtml(r.term)}</span>`;
  }).join('') : `<div class=\"empty\">${escapeHtml(t('没有命中的热词，换个词试试。', 'No terms matched. Try another query.'))}</div>`;
  cloud.querySelectorAll('[data-term]').forEach(el=>el.addEventListener('click',()=>{
    activeTerm = el.dataset.term === activeTerm ? '' : el.dataset.term;
    activeTopic = '';
    renderAll();
  }));
}
document.getElementById('searchInput').addEventListener('input', () => renderAll());
document.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => {
  viewMode = btn.dataset.view || 'all';
  document.querySelectorAll('[data-view]').forEach(node => node.classList.toggle('active', node === btn));
  renderAll();
}));
document.getElementById('clearBtn').addEventListener('click', () => clearSelection(true));
const seeded = applyPayload(fallbackTopicCloud);
if(!seeded){
  document.getElementById('summary').innerHTML='<b>词云加载中</b><div class=\"muted\" style=\"margin-top:8px\">正在准备热点词云与关联人物。</div>';
}
fetch('./data/topic_cloud.json').then(r=>{
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}).then(d=>{
  applyPayload(d);
}).catch(()=>{
  if(!seeded){
    document.getElementById('summary').innerHTML='<b>词云数据暂不可用</b><div class=\"muted\" style=\"margin-top:8px\">当前未能加载数据，请稍后刷新重试。</div>';
    document.getElementById('topics').innerHTML='<div class=\"muted\">暂无话题数据</div>';
    document.getElementById('cloud').innerHTML='<div class=\"muted\">暂无热词数据</div>';
    document.getElementById('list').innerHTML='<div class=\"item muted\">暂无匹配人物</div>';
  }
});
</script></body></html>"""
    return page.replace("__TOPIC_CLOUD_FALLBACK__", json.dumps(topic_cloud, ensure_ascii=False))


def main() -> int:
    domain = load_domain_config()
    data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    raw_top = data.get("top300", [])
    nodes = {str(n.get("id") or n.get("handle") or ""): n for n in data.get("nodes", []) if isinstance(n, dict)}
    top = [
        row for row in raw_top
        if isinstance(row, dict) and domain_matches(row, nodes.get(str(row.get("id") or row.get("handle") or ""), {}), domain)
    ]
    if not top:
        top = list(raw_top)
    ctx = domain_context(domain, len(top))

    metrics = {
        "association_weight": [float(x.get("association_weight") or 0) for x in top],
        "cross_follow_ratio": [float(x.get("cross_follow_ratio") or 0) for x in top],
        "pagerank": [float(x.get("pagerank") or 0) for x in top],
        "followers": [float(x.get("followers") or 0) for x in top],
        "interactions": [
            float(x.get("posts_count") or 0)
            + float(x.get("comments_count") or 0)
            + float(x.get("likes_count") or 0)
            + float(x.get("reposts_count") or 0)
            for x in top
        ],
        "degree": [float(x.get("in_degree") or 0) + float(x.get("out_degree") or 0) for x in top],
    }
    bounds = {k: (min(v) if v else 0.0, max(v) if v else 1.0) for k, v in metrics.items()}

    profiles = []
    total = len(top)
    for row in top:
        nid = str(row.get("id") or row.get("handle") or "")
        node = nodes.get(nid, {})
        handle = str(row.get("handle") or nid).lstrip("@")
        rank = int(row.get("rank") or total)
        layer = layer_by_rank(rank, total)
        text_scope = " ".join(
            [
                str(node.get("bio") or ""),
                str(row.get("role") or ""),
                str(row.get("group") or ""),
                str(row.get("latest_tweet_text") or ""),
                str(row.get("today_hottest_tweet_text") or ""),
            ]
        )
        topics = topic_from_text(text_scope, domain)

        association_weight_n = norm(float(row.get("association_weight") or 0), *bounds["association_weight"])
        cross_follow_ratio_n = norm(float(row.get("cross_follow_ratio") or 0), *bounds["cross_follow_ratio"])
        interaction_n = norm(
            float(row.get("posts_count") or 0)
            + float(row.get("comments_count") or 0)
            + float(row.get("likes_count") or 0)
            + float(row.get("reposts_count") or 0),
            *bounds["interactions"],
        )
        pagerank_n = norm(float(row.get("pagerank") or 0), *bounds["pagerank"])
        degree_n = norm(float(row.get("in_degree") or 0) + float(row.get("out_degree") or 0), *bounds["degree"])
        followers_n = norm(float(row.get("followers") or 0), *bounds["followers"])

        association_score = 0.45 * association_weight_n + 0.25 * cross_follow_ratio_n + 0.30 * interaction_n
        centrality_score = 0.50 * pagerank_n + 0.25 * degree_n + 0.25 * followers_n
        influence = float(row.get("quanzhong_score") or (0.55 * association_score + 0.45 * centrality_score))

        recency_days = _recency_days_from_row(row)
        sort_ts = _sort_timestamp_from_row(row)
        hottest_text = _clean_tweet_text(str(row.get("today_hottest_tweet_text") or ""))
        latest_text = _clean_tweet_text(str(row.get("latest_tweet_text") or ""))
        has_today = bool(row.get("has_today_tweet")) and bool(hottest_text)

        p = {
            "slug": slugify(handle),
            "id": nid,
            "name": row.get("name") or handle,
            "handle": handle,
            "rank": rank,
            "score": influence,
            "association_score": association_score,
            "centrality_score": centrality_score,
            "layer": layer,
            "layer_zh": LAYER_LABEL_ZH[layer],
            "layer_en": LAYER_LABEL_EN[layer],
            "topics": topics,
            "summary_zh": zh_summary(row, node, LAYER_LABEL_ZH[layer]),
            "summary_en": en_summary(row, node, LAYER_LABEL_EN[layer]),
            "daily_essence_zh": daily_essence_zh(row, topics),
            "daily_essence_en": daily_essence_en(row, topics),
            "latest_viewpoint_zh": latest_viewpoint_zh(row, topics),
            "latest_viewpoint_en": latest_viewpoint_en(row, topics),
            "latest_share_zh": latest_share_zh(row, topics),
            "latest_share_en": latest_share_en(row, topics),
            "latest_tweet_text": str(row.get("latest_tweet_text") or ""),
            "latest_tweet_at": str(row.get("latest_tweet_at") or ""),
            "latest_tweet_at_label": str(row.get("latest_tweet_at_label") or ""),
            "latest_crawled_at": str(row.get("latest_crawled_at") or ""),
            "latest_tweet_url": str(row.get("latest_tweet_url") or ""),
            "has_today_tweet": has_today,
            "today_hottest_tweet_text": hottest_text,
            "today_hottest_tweet_at": str(row.get("today_hottest_tweet_at") or ""),
            "today_hottest_tweet_url": str(row.get("today_hottest_tweet_url") or ""),
            "today_hottest_tweet_heat": float(row.get("today_hottest_tweet_heat") or 0.0),
            "recency_days": recency_days,
            "sort_ts": sort_ts,
            "followers": int(row.get("followers") or 0),
            "posts_count": int(row.get("posts_count") or 0),
            "comments_count": int(row.get("comments_count") or 0),
            "likes_count": int(row.get("likes_count") or 0),
            "reposts_count": int(row.get("reposts_count") or 0),
            "association_weight": float(row.get("association_weight") or 0),
            "cross_follow_count": int(row.get("cross_follow_count") or 0),
            "cross_follow_ratio": float(row.get("cross_follow_ratio") or 0),
            "pagerank": float(row.get("pagerank") or 0),
            "grey_relation": float(row.get("grey_relation") or 0),
            "role": row.get("role") or node.get("role") or "",
            "group": row.get("group") or node.get("group") or "",
            "verified": bool(row.get("verified") or node.get("verified")),
            "website": row.get("website") or node.get("website") or "",
            "location": row.get("location") or node.get("location") or "",
            "explainability": {
                "cross_follow_ratio": cross_follow_ratio_n,
                "interaction": interaction_n,
                "pagerank": pagerank_n,
                "degree": degree_n,
                "followers": followers_n,
            },
        }
        profiles.append(p)

    profiles.sort(key=lambda x: x["rank"])
    id_to_profile = {str(p.get("id") or p.get("handle") or ""): p for p in profiles}
    best_buddies = compute_best_buddies(top, data.get("weighted_links") or [], id_to_profile)
    for p in profiles:
        p["best_buddies"] = best_buddies.get(str(p.get("id") or p.get("handle") or ""), [])

    daily_profiles = [
        x for x in profiles
        if bool(x.get("has_today_tweet")) and str(x.get("today_hottest_tweet_text") or "").strip()
    ]
    recent_profiles = [
        x for x in profiles
        if str(x.get("latest_share_zh") or "").strip() and str(x.get("latest_share_en") or "").strip()
    ]
    insights_rows = sorted(
        recent_profiles,
        key=lambda x: (
            int(x["recency_days"]) if x.get("recency_days") is not None else 999,
            -float(x["sort_ts"]) if x.get("sort_ts") is not None else 0.0,
            -float(x.get("score") or 0),
            int(x.get("rank") or 999999),
        ),
    )
    briefing_primary = sorted(
        daily_profiles,
        key=lambda x: (
            -float(x.get("today_hottest_tweet_heat") or 0),
            int(x["recency_days"]) if x.get("recency_days") is not None else 999,
            -float(x["sort_ts"]) if x.get("sort_ts") is not None else 0.0,
            -float(x.get("score") or 0),
            int(x.get("rank") or 999999),
        ),
    )
    if len(briefing_primary) < 10:
        seen = {str(x.get("handle") or "").lower() for x in briefing_primary}
        briefing_fallback = [
            x for x in insights_rows
            if str(x.get("handle") or "").lower() not in seen
        ]
        briefing_rows = briefing_primary + briefing_fallback
    else:
        briefing_rows = briefing_primary
    top10 = briefing_rows[:10]

    built_at = dt.datetime.utcnow().isoformat() + "Z"
    content_fallback_at = str(data.get("generated_at") or built_at)
    content_updated_at = compute_content_updated_at(profiles, content_fallback_at)
    payload = {"updated_at": content_updated_at, "built_at": built_at, "items": profiles}
    topic_cloud = build_topic_cloud(profiles, content_updated_at, built_at, domain, ctx)

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    for p in profiles:
        (PROFILES_DIR / f"{p['slug']}.html").write_text(profile_page(p, ctx), encoding="utf-8")

    PROFILE_INDEX.write_text(profiles_index(ctx), encoding="utf-8")
    INSIGHTS_PAGE.write_text(insights_page(ctx), encoding="utf-8")
    BRIEFING_PAGE.write_text(briefing_page(ctx), encoding="utf-8")
    DAILY_PROGRESS_PAGE.write_text(daily_progress_page(ctx), encoding="utf-8")
    POSTER_PAGE.write_text(poster_page(ctx), encoding="utf-8")
    TOPICS_PAGE.write_text(topics_page(ctx, topic_cloud), encoding="utf-8")
    PROFILE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    INSIGHTS_JSON.write_text(json.dumps({"updated_at": content_updated_at, "built_at": built_at, "items": insights_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    BRIEFING_JSON.write_text(json.dumps({"updated_at": content_updated_at, "built_at": built_at, "items": briefing_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    DAILY_PROGRESS_JSON.write_text(json.dumps(build_daily_progress(profiles, briefing_rows, content_updated_at, built_at, ctx), ensure_ascii=False, indent=2), encoding="utf-8")
    DOMAIN_CONTEXT_JSON.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    TOPIC_CLOUD_JSON.write_text(json.dumps(topic_cloud, ensure_ascii=False, indent=2), encoding="utf-8")
    fixer = ROOT / "scripts" / "fix_generated_i18n.py"
    if fixer.exists():
        subprocess.run(["python3", str(fixer)], check=True)
    print(f"Generated {len(profiles)} profile pages and Top10 briefing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
