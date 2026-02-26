#!/usr/bin/env python3
"""CLI entry for quanzhong-skill."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from quanzhong_model import compute_quanzhong_metrics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute quanzhong ranking from graph data")
    parser.add_argument("--input", type=Path, required=True, help="Input graph JSON with nodes/links")
    parser.add_argument("--output", type=Path, required=True, help="Output ranking JSON")
    parser.add_argument("--csv", type=Path, required=True, help="Output ranking CSV")
    parser.add_argument("--engagement", type=Path, default=None, help="Optional engagement metrics JSON")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    engagement_map = {}
    if args.engagement and args.engagement.exists():
        raw = json.loads(args.engagement.read_text(encoding="utf-8"))
        metrics = raw.get("metrics") if isinstance(raw, dict) else raw
        if isinstance(metrics, list):
            for m in metrics:
                if not isinstance(m, dict):
                    continue
                h = str(m.get("handle") or "").strip().lstrip("@").lower()
                if h:
                    engagement_map[h] = m

    result = compute_quanzhong_metrics(nodes, links, engagement_map=engagement_map)
    node_metrics = result.get("node_metrics", {})

    rows = []
    for node in nodes:
        nid = str(node.get("id") or node.get("handle") or "").strip()
        if not nid:
            continue
        m = node_metrics.get(nid, {})
        rows.append(
            {
                "id": nid,
                "name": node.get("name") or nid,
                "handle": node.get("handle") or nid,
                "group": node.get("group"),
                "role": node.get("role"),
                "followers": node.get("followers", 0),
                "quanzhong_score": m.get("quanzhong_score", 0.0),
                "grey_relation": m.get("grey_relation", 0.0),
                "association_weight": m.get("association_weight", 0.0),
                "cross_follow_count": m.get("cross_follow_count", 0),
                "cross_follow_ratio": m.get("cross_follow_ratio", 0.0),
                "posts_count": m.get("posts_count", 0),
                "comments_count": m.get("comments_count", 0),
                "likes_count": m.get("likes_count", 0),
                "reposts_count": m.get("reposts_count", 0),
                "semantic_ai": m.get("semantic_ai", 0.0),
                "pagerank": m.get("pagerank", 0.0),
            }
        )
    rows.sort(
        key=lambda x: (
            -float(x["quanzhong_score"]),
            -float(x["grey_relation"]),
            -float(x["association_weight"]),
            str(x["handle"]).lower(),
        )
    )
    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    payload = {
        "model_name": result.get("model_name"),
        "rho": result.get("rho"),
        "indicator_weights": result.get("indicator_weights"),
        "top300": rows[:300],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = [
        "rank",
        "name",
        "handle",
        "group",
        "role",
        "followers",
        "quanzhong_score",
        "grey_relation",
        "association_weight",
        "cross_follow_count",
        "cross_follow_ratio",
        "posts_count",
        "comments_count",
        "likes_count",
        "reposts_count",
        "semantic_ai",
        "pagerank",
    ]
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows[:300]:
            writer.writerow({k: row.get(k, "") for k in headers})

    print(f"Updated {args.output}")
    print(f"Updated {args.csv}")
    print(f"Rows: {len(rows[:300])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
