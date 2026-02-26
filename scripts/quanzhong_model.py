#!/usr/bin/env python3
"""Quanzhong model: semantic-network association + grey relational ranking."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from statistics import fmean, pstdev

AI_KEYWORDS = {
    "ai",
    "artificial",
    "intelligence",
    "llm",
    "agent",
    "agents",
    "model",
    "models",
    "openai",
    "anthropic",
    "deepmind",
    "gemini",
    "gpt",
    "transformer",
    "research",
    "researcher",
    "scientist",
    "machine",
    "learning",
    "ml",
    "pytorch",
    "langchain",
    "inference",
    "token",
    "alignment",
    "reasoning",
    "robot",
    "robotics",
    "创业",
    "大模型",
    "智能",
    "算法",
    "机器学习",
    "人工智能",
}


def endpoint(value: object) -> str:
    if isinstance(value, dict):
        for k in ("id", "handle", "name"):
            v = value.get(k)
            if v:
                return str(v).strip()
        return ""
    return str(value or "").strip()


def to_int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        pass
    text = str(value or "").strip().upper().replace(",", "")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)([KMB])?$", text)
    if not m:
        digits = re.sub(r"[^0-9]", "", text)
        return int(digits) if digits else 0
    number = float(m.group(1))
    suffix = m.group(2)
    if suffix == "K":
        number *= 1_000
    elif suffix == "M":
        number *= 1_000_000
    elif suffix == "B":
        number *= 1_000_000_000
    return int(number)


def _tokenize(*items: object) -> set[str]:
    blob = " ".join(str(x or "") for x in items).lower()
    parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", blob)
    return {p for p in parts if len(p) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _pagerank(
    node_ids: list[str],
    out_map: dict[str, set[str]],
    damping: float = 0.85,
    iterations: int = 30,
) -> dict[str, float]:
    n = len(node_ids)
    if n == 0:
        return {}
    base = (1.0 - damping) / n
    pr = {nid: 1.0 / n for nid in node_ids}
    for _ in range(iterations):
        nxt = {nid: base for nid in node_ids}
        for src in node_ids:
            outs = out_map.get(src, set())
            if outs:
                share = damping * pr[src] / len(outs)
                for dst in outs:
                    nxt[dst] = nxt.get(dst, base) + share
            else:
                share = damping * pr[src] / n
                for dst in node_ids:
                    nxt[dst] += share
        pr = nxt
    return pr


def compute_quanzhong_metrics(
    nodes: list[dict],
    links: list[dict],
    rho: float = 0.5,
    engagement_map: dict[str, dict] | None = None,
) -> dict:
    node_ids: list[str] = []
    node_map: dict[str, dict] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or node.get("handle") or "").strip()
        if not nid:
            continue
        node_ids.append(nid)
        node_map[nid] = node

    out_map: dict[str, set[str]] = defaultdict(set)
    in_map: dict[str, set[str]] = defaultdict(set)
    link_pairs: list[tuple[str, str]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        s = endpoint(link.get("source"))
        t = endpoint(link.get("target"))
        if not s or not t or s == t:
            continue
        if s not in node_map or t not in node_map:
            continue
        out_map[s].add(t)
        in_map[t].add(s)
        link_pairs.append((s, t))

    token_map: dict[str, set[str]] = {}
    sem_raw: dict[str, float] = {}
    for nid in node_ids:
        node = node_map[nid]
        tags = node.get("bioTags")
        if isinstance(tags, list):
            tags_blob = " ".join(str(x) for x in tags)
        else:
            tags_blob = str(tags or "")
        toks = _tokenize(
            node.get("name"),
            node.get("handle"),
            node.get("group"),
            node.get("role"),
            node.get("associated"),
            node.get("bio"),
            tags_blob,
        )
        token_map[nid] = toks
        hit = sum(1 for w in AI_KEYWORDS if w in toks)
        sem_raw[nid] = min(1.0, hit / 8.0)

    pr_map = _pagerank(node_ids, out_map)

    # Cross-follow signal: mutual following relationships.
    reciprocal_count: dict[str, int] = {nid: 0 for nid in node_ids}
    for s, t in link_pairs:
        if s in out_map.get(t, set()):
            reciprocal_count[s] += 1
    cross_follow_ratio: dict[str, float] = {}
    for nid in node_ids:
        out_n = max(1, len(out_map.get(nid, set())))
        cross_follow_ratio[nid] = reciprocal_count[nid] / out_n

    weighted_links: list[dict] = []
    weighted_degree: dict[str, float] = {nid: 0.0 for nid in node_ids}
    for s, t in link_pairs:
        reciprocal = 1.0 if s in out_map.get(t, set()) else 0.0
        shared_out = _jaccard(out_map.get(s, set()), out_map.get(t, set()))
        shared_in = _jaccard(in_map.get(s, set()), in_map.get(t, set()))
        semantic_sim = _jaccard(token_map.get(s, set()), token_map.get(t, set()))

        structural = 0.50 * reciprocal + 0.25 * shared_out + 0.25 * shared_in
        edge_weight = 0.65 * structural + 0.35 * semantic_sim
        edge_weight = max(0.02, min(1.0, edge_weight))

        weighted_links.append(
            {
                "source": s,
                "target": t,
                "weight": round(edge_weight, 6),
                "structural": round(structural, 6),
                "semantic_similarity": round(semantic_sim, 6),
                "reciprocal": int(reciprocal),
            }
        )
        weighted_degree[s] += edge_weight
        weighted_degree[t] += edge_weight

    followers = {nid: to_int(node_map[nid].get("followers", 0)) for nid in node_ids}
    in_deg = {nid: float(len(in_map.get(nid, set()))) for nid in node_ids}
    out_deg = {nid: float(len(out_map.get(nid, set()))) for nid in node_ids}
    wd = {nid: float(weighted_degree.get(nid, 0.0)) for nid in node_ids}
    sem = {nid: float(sem_raw.get(nid, 0.0)) for nid in node_ids}
    pr = {nid: float(pr_map.get(nid, 0.0)) for nid in node_ids}

    # Engagement signals from X:
    # posts_count, comments_count, likes_count, reposts_count
    emap = engagement_map or {}
    posts = {}
    comments = {}
    likes = {}
    reposts = {}
    for nid in node_ids:
        node = node_map[nid]
        handle = str(node.get("handle") or nid).strip().lstrip("@").lower()
        rec = emap.get(handle) or emap.get(nid.lower()) or {}
        posts[nid] = float(to_int(rec.get("posts_count", rec.get("posts", 0))))
        comments[nid] = float(to_int(rec.get("comments_count", rec.get("comments", 0))))
        likes[nid] = float(to_int(rec.get("likes_count", rec.get("likes", 0))))
        reposts[nid] = float(to_int(rec.get("reposts_count", rec.get("reposts", 0))))

    ind_names = [
        "followers_log",
        "in_degree",
        "out_degree",
        "weighted_degree",
        "pagerank",
        "semantic_ai",
        "cross_follow_ratio",
        "posts_count",
        "comments_count",
        "likes_count",
        "reposts_count",
    ]
    ind_raw = {
        "followers_log": [math.log10(max(1, followers[nid])) for nid in node_ids],
        "in_degree": [in_deg[nid] for nid in node_ids],
        "out_degree": [out_deg[nid] for nid in node_ids],
        "weighted_degree": [wd[nid] for nid in node_ids],
        "pagerank": [pr[nid] for nid in node_ids],
        "semantic_ai": [sem[nid] for nid in node_ids],
        "cross_follow_ratio": [cross_follow_ratio[nid] for nid in node_ids],
        "posts_count": [math.log10(max(1.0, posts[nid])) for nid in node_ids],
        "comments_count": [math.log10(max(1.0, comments[nid])) for nid in node_ids],
        "likes_count": [math.log10(max(1.0, likes[nid])) for nid in node_ids],
        "reposts_count": [math.log10(max(1.0, reposts[nid])) for nid in node_ids],
    }
    ind_norm = {k: _minmax(v) for k, v in ind_raw.items()}

    # Dynamic indicator weights by coefficient-of-variation.
    cvs: dict[str, float] = {}
    for name in ind_names:
        vals = ind_norm[name]
        avg = fmean(vals) if vals else 0.0
        sd = pstdev(vals) if len(vals) > 1 else 0.0
        cvs[name] = (sd / avg) if avg > 1e-9 else 0.0
    total_cv = sum(cvs.values())
    if total_cv <= 1e-9:
        k_weight = {name: 1.0 / len(ind_names) for name in ind_names}
    else:
        k_weight = {name: cvs[name] / total_cv for name in ind_names}

    # Grey relational analysis with reference sequence x0(k)=1.
    deltas: list[float] = []
    for name in ind_names:
        deltas.extend([abs(1.0 - x) for x in ind_norm[name]])
    delta_min = min(deltas) if deltas else 0.0
    delta_max = max(deltas) if deltas else 1.0
    if delta_max <= 1e-9:
        delta_max = 1.0

    grey_relation: dict[str, float] = {}
    weighted_degree_norm = _minmax([wd[nid] for nid in node_ids])
    wd_norm_map = {nid: weighted_degree_norm[i] for i, nid in enumerate(node_ids)}
    node_metrics: dict[str, dict] = {}

    for i, nid in enumerate(node_ids):
        gamma_sum = 0.0
        for name in ind_names:
            delta = abs(1.0 - ind_norm[name][i])
            gamma = (delta_min + rho * delta_max) / (delta + rho * delta_max)
            gamma_sum += k_weight[name] * gamma
        grey_relation[nid] = gamma_sum

        final_score = 0.75 * gamma_sum + 0.25 * wd_norm_map[nid]
        node_metrics[nid] = {
            "grey_relation": round(gamma_sum, 6),
            "association_weight": round(wd[nid], 6),
            "association_weight_norm": round(wd_norm_map[nid], 6),
            "semantic_ai": round(sem[nid], 6),
            "cross_follow_count": int(reciprocal_count[nid]),
            "cross_follow_ratio": round(cross_follow_ratio[nid], 6),
            "posts_count": int(posts[nid]),
            "comments_count": int(comments[nid]),
            "likes_count": int(likes[nid]),
            "reposts_count": int(reposts[nid]),
            "pagerank": round(pr[nid], 8),
            "in_degree": int(in_deg[nid]),
            "out_degree": int(out_deg[nid]),
            "quanzhong_score": round(final_score, 6),
        }

    return {
        "model_name": "quanzhong-grey-semantic-v2",
        "rho": rho,
        "indicator_weights": {k: round(v, 6) for k, v in k_weight.items()},
        "reference_sequence": "x0(k)=1",
        "engagement_fields": ["posts_count", "comments_count", "likes_count", "reposts_count"],
        "node_metrics": node_metrics,
        "weighted_links": weighted_links,
    }
