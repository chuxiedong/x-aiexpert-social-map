#!/usr/bin/env python3
"""Fetch x.mitbunny.ai bundled graph data and export graph + top300 ranking."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from quanzhong_model import compute_quanzhong_metrics, to_int

MITBUNNY_HOME_URL = "https://x.mitbunny.ai"
MITBUNNY_BUNDLE_URL_FALLBACK = "https://x.mitbunny.ai/assets/index-B7Y6x62F.js"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "mitbunny_graph.json"
DEFAULT_TOP_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "top300.json"
DEFAULT_TOP_CSV_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "top300.csv"
DEFAULT_ENGAGEMENT_INPUT = Path(__file__).resolve().parents[1] / "data" / "engagement_metrics.json"


def fetch_bundle(url: str) -> str:
    last_err: Exception | None = None
    for idx in range(8):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as err:  # pragma: no cover - network transient
            last_err = err
            if idx < 7:
                time.sleep(1.0)
    if last_err:
        raise last_err
    raise RuntimeError("Unknown fetch error")


def fetch_latest_bundle_url(home_url: str) -> str:
    req = urllib.request.Request(
        home_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        html = resp.read().decode("utf-8", "ignore")
    m = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
    if not m:
        raise ValueError("Cannot locate mitbunny index bundle path")
    return f"{home_url.rstrip('/')}{m.group(1)}"


def extract_graph_object(js_text: str) -> str:
    marker = "{nodes:["
    starts: list[int] = []
    pos = 0
    while True:
        idx = js_text.find(marker, pos)
        if idx < 0:
            break
        starts.append(idx)
        pos = idx + len(marker)
    if not starts:
        raise ValueError("Cannot find graph object marker '{nodes:[' in bundle")

    def read_object(start: int) -> str | None:
        depth = 0
        in_str: str | None = None
        escape = False
        end = -1
        for i in range(start, len(js_text)):
            ch = js_text[i]
            if in_str is not None:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_str:
                    in_str = None
                continue
            if ch in ('"', "'", "`"):
                in_str = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            return None
        return js_text[start : end + 1]

    candidates: list[str] = []
    for s in starts:
        obj = read_object(s)
        if not obj:
            continue
        if "links:[" not in obj:
            continue
        candidates.append(obj)

    if not candidates:
        raise ValueError("Cannot find valid graph payload object with nodes/links")
    return max(candidates, key=len)


def js_object_to_json(obj_literal: str) -> dict:
    node_code = f"const GRAPH={obj_literal}; console.log(JSON.stringify(GRAPH));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
        tmp.write(node_code)
        tmp_path = tmp.name

    try:
        output = subprocess.check_output(["node", tmp_path], text=True, stderr=subprocess.STDOUT)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise ValueError("Parsed XJ payload is not an object")
    if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("links"), list):
        raise ValueError("Parsed XJ payload missing nodes/links arrays")
    return payload


def normalize_handle(node: dict) -> str:
    return str(node.get("handle") or node.get("id") or "").strip().lstrip("@")


def load_engagement(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = data.get("metrics") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        h = str(item.get("handle") or "").strip().lstrip("@").lower()
        if not h:
            continue
        out[h] = item
    return out


def ensure_engagement_template(path: Path, nodes: list[dict]) -> None:
    if path.exists():
        return
    rows = []
    for node in nodes:
        handle = str(node.get("handle") or node.get("id") or "").strip().lstrip("@")
        if not handle:
            continue
        rows.append(
            {
                "handle": handle,
                "posts_count": 0,
                "comments_count": 0,
                "likes_count": 0,
                "reposts_count": 0,
                "window_days": 30,
                "note": "Fill with latest X metrics",
            }
        )
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "description": "X engagement metrics per account, used by quanzhong model",
        "metrics": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_top300(payload: dict, engagement_map: dict[str, dict]) -> list[dict]:
    nodes = payload.get("nodes", [])
    links = payload.get("links", [])
    qz = compute_quanzhong_metrics(nodes, links, engagement_map=engagement_map)
    node_metrics = qz.get("node_metrics", {})

    rows: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        handle = normalize_handle(node)
        metrics = node_metrics.get(node_id) or node_metrics.get(handle) or {}
        engagement_extra = engagement_map.get(handle.lower(), {}) if handle else {}
        rows.append(
            {
                "id": node_id or handle,
                "name": node.get("name") or handle,
                "handle": handle,
                "group": node.get("group"),
                "role": node.get("role"),
                "followers": to_int(node.get("followers", 0)),
                "following": to_int(node.get("following", 0)),
                "connections": int(metrics.get("in_degree", 0)) + int(metrics.get("out_degree", 0)),
                "in_degree": int(metrics.get("in_degree", 0)),
                "out_degree": int(metrics.get("out_degree", 0)),
                "association_weight": float(metrics.get("association_weight", 0.0)),
                "association_weight_norm": float(metrics.get("association_weight_norm", 0.0)),
                "semantic_ai": float(metrics.get("semantic_ai", 0.0)),
                "cross_follow_count": int(metrics.get("cross_follow_count", 0)),
                "cross_follow_ratio": float(metrics.get("cross_follow_ratio", 0.0)),
                "posts_count": int(metrics.get("posts_count", 0)),
                "comments_count": int(metrics.get("comments_count", 0)),
                "likes_count": int(metrics.get("likes_count", 0)),
                "reposts_count": int(metrics.get("reposts_count", 0)),
                "latest_tweet_id": str(engagement_extra.get("latest_tweet_id") or ""),
                "latest_tweet_text": str(engagement_extra.get("latest_tweet_text") or ""),
                "latest_tweet_at": str(engagement_extra.get("latest_tweet_at") or ""),
                "latest_tweet_url": str(engagement_extra.get("latest_tweet_url") or ""),
                "has_today_tweet": bool(engagement_extra.get("has_today_tweet")),
                "today_hottest_tweet_id": str(engagement_extra.get("today_hottest_tweet_id") or ""),
                "today_hottest_tweet_text": str(engagement_extra.get("today_hottest_tweet_text") or ""),
                "today_hottest_tweet_at": str(engagement_extra.get("today_hottest_tweet_at") or ""),
                "today_hottest_tweet_url": str(engagement_extra.get("today_hottest_tweet_url") or ""),
                "today_hottest_tweet_heat": float(engagement_extra.get("today_hottest_tweet_heat") or 0.0),
                "today_hottest_likes": int(engagement_extra.get("today_hottest_likes") or 0),
                "today_hottest_reposts": int(engagement_extra.get("today_hottest_reposts") or 0),
                "today_hottest_replies": int(engagement_extra.get("today_hottest_replies") or 0),
                "today_hottest_quotes": int(engagement_extra.get("today_hottest_quotes") or 0),
                "pagerank": float(metrics.get("pagerank", 0.0)),
                "grey_relation": float(metrics.get("grey_relation", 0.0)),
                "quanzhong_score": float(metrics.get("quanzhong_score", 0.0)),
                "location": node.get("location"),
                "website": node.get("website"),
                "joinedDate": node.get("joinedDate"),
                "verified": node.get("verified"),
            }
        )

    rows.sort(
        key=lambda x: (
            -float(x.get("quanzhong_score", 0)),
            -float(x.get("grey_relation", 0)),
            -float(x.get("association_weight", 0)),
            -int(x.get("connections", 0)),
            -int(x.get("followers", 0)),
            str(x.get("handle", "")).lower(),
        )
    )
    rows = rows[:300]
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def build_export(payload: dict) -> dict:
    engagement_map = payload.get("engagement_map", {})
    qz = compute_quanzhong_metrics(payload.get("nodes", []), payload.get("links", []), engagement_map=engagement_map)
    top300 = build_top300(payload, engagement_map)
    return {
        "source_name": "x.mitbunny.ai graph bundle",
        "source_url": payload.get("bundle_url"),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "total_nodes": len(payload.get("nodes", [])),
        "total_links": len(payload.get("links", [])),
        "ranking_formula": (
            "quanzhong_score = 0.75*grey_relation + 0.25*association_weight_norm; "
            "grey_relation by Grey Relational Analysis over indicators "
            "[followers_log,in_degree,out_degree,weighted_degree,pagerank,semantic_ai,"
            "cross_follow_ratio,posts_count,comments_count,likes_count,reposts_count]"
        ),
        "ranking_sort": "rank by quanzhong_score desc, grey_relation desc, association_weight desc",
        "quanzhong_model": {
            "name": qz.get("model_name"),
            "rho": qz.get("rho"),
            "indicator_weights": qz.get("indicator_weights"),
            "reference_sequence": qz.get("reference_sequence"),
            "engagement_fields": qz.get("engagement_fields"),
        },
        "top300_total": len(top300),
        "top300": top300,
        "nodes": payload.get("nodes", []),
        "links": payload.get("links", []),
        "weighted_links": qz.get("weighted_links", []),
    }


def write_top300_file(path: Path, graph_export: dict) -> None:
    top_data = {
        "source_name": graph_export.get("source_name"),
        "source_url": graph_export.get("source_url"),
        "generated_at": graph_export.get("generated_at"),
        "ranking_formula": graph_export.get("ranking_formula"),
        "ranking_sort": graph_export.get("ranking_sort"),
        "quanzhong_model": graph_export.get("quanzhong_model"),
        "total_experts": graph_export.get("top300_total", 0),
        "experts": graph_export.get("top300", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(top_data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_top300_csv(path: Path, graph_export: dict) -> None:
    rows = graph_export.get("top300", [])
    headers = [
        "rank",
        "name",
        "handle",
        "group",
        "role",
        "followers",
        "following",
        "connections",
        "in_degree",
        "out_degree",
        "cross_follow_count",
        "cross_follow_ratio",
        "posts_count",
        "comments_count",
        "likes_count",
        "reposts_count",
        "association_weight",
        "association_weight_norm",
        "semantic_ai",
        "pagerank",
        "grey_relation",
        "quanzhong_score",
        "location",
        "website",
        "joinedDate",
        "verified",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})


def main() -> int:
    parser = argparse.ArgumentParser(description="Update mitbunny graph JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Graph output file path")
    parser.add_argument("--top-output", type=Path, default=DEFAULT_TOP_OUTPUT, help="Top300 output file path")
    parser.add_argument("--top-csv-output", type=Path, default=DEFAULT_TOP_CSV_OUTPUT, help="Top300 CSV output file path")
    parser.add_argument(
        "--engagement-input",
        type=Path,
        default=DEFAULT_ENGAGEMENT_INPUT,
        help="X engagement metrics JSON path",
    )
    args = parser.parse_args()

    try:
        bundle_url = fetch_latest_bundle_url(MITBUNNY_HOME_URL)
    except Exception:
        bundle_url = MITBUNNY_BUNDLE_URL_FALLBACK
    js_text = fetch_bundle(bundle_url)
    obj_literal = extract_graph_object(js_text)
    parsed = js_object_to_json(obj_literal)
    ensure_engagement_template(args.engagement_input, parsed.get("nodes", []))
    parsed["engagement_map"] = load_engagement(args.engagement_input)
    parsed["bundle_url"] = bundle_url
    data = build_export(parsed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_top300_file(args.top_output, data)
    write_top300_csv(args.top_csv_output, data)

    print(f"Updated {args.output}")
    print(f"Updated {args.top_output}")
    print(f"Updated {args.top_csv_output}")
    print(f"Nodes: {data['total_nodes']} | Links: {data['total_links']} | Top300: {data['top300_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
