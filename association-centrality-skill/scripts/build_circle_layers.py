#!/usr/bin/env python3
"""Build association+centrality circle layers from graph data."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def endpoint(value: object) -> str:
    if isinstance(value, dict):
        for k in ("id", "handle", "name"):
            v = value.get(k)
            if v:
                return str(v).strip()
        return ""
    return str(value or "").strip()


def minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def pagerank(node_ids: list[str], out_map: dict[str, set[str]], damping: float = 0.85, iterations: int = 30) -> dict[str, float]:
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


def quantile_threshold(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int((len(sorted_vals) - 1) * q)
    return sorted_vals[max(0, min(len(sorted_vals) - 1, idx))]


def build_layers(
    nodes: list[dict],
    links: list[dict],
    alpha: float,
    beta: float,
) -> dict:
    node_map: dict[str, dict] = {}
    node_ids: list[str] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or n.get("handle") or "").strip()
        if not nid:
            continue
        node_ids.append(nid)
        node_map[nid] = n

    out_map: dict[str, set[str]] = defaultdict(set)
    in_map: dict[str, set[str]] = defaultdict(set)
    weighted_degree: dict[str, float] = {nid: 0.0 for nid in node_ids}
    reciprocal_count: dict[str, int] = {nid: 0 for nid in node_ids}

    for lk in links:
        if not isinstance(lk, dict):
            continue
        s = endpoint(lk.get("source"))
        t = endpoint(lk.get("target"))
        if not s or not t or s == t:
            continue
        if s not in node_map or t not in node_map:
            continue
        w = lk.get("weight", 1.0)
        try:
            w = float(w)
        except Exception:
            w = 1.0
        if w <= 0:
            w = 1.0
        out_map[s].add(t)
        in_map[t].add(s)
        weighted_degree[s] += w
        weighted_degree[t] += w

    for s in node_ids:
        for t in out_map.get(s, set()):
            if s in out_map.get(t, set()):
                reciprocal_count[s] += 1

    pr = pagerank(node_ids, out_map)
    deg = {nid: len(in_map.get(nid, set())) + len(out_map.get(nid, set())) for nid in node_ids}
    bridge = {nid: len(out_map.get(nid, set()) - in_map.get(nid, set())) for nid in node_ids}
    cross_ratio = {nid: reciprocal_count[nid] / max(1, len(out_map.get(nid, set()))) for nid in node_ids}

    wd_n = {nid: v for nid, v in zip(node_ids, minmax([weighted_degree[nid] for nid in node_ids]))}
    cr_n = {nid: v for nid, v in zip(node_ids, minmax([cross_ratio[nid] for nid in node_ids]))}
    pr_n = {nid: v for nid, v in zip(node_ids, minmax([pr[nid] for nid in node_ids]))}
    deg_n = {nid: v for nid, v in zip(node_ids, minmax([float(deg[nid]) for nid in node_ids]))}
    bri_n = {nid: v for nid, v in zip(node_ids, minmax([float(bridge[nid]) for nid in node_ids]))}

    rows = []
    for nid in node_ids:
        # Association: weighted connectivity + cross-follow reciprocity
        association = 0.7 * wd_n[nid] + 0.3 * cr_n[nid]
        # Centrality: global and local core-ness
        centrality = 0.5 * pr_n[nid] + 0.35 * deg_n[nid] + 0.15 * bri_n[nid]
        influence = alpha * association + beta * centrality
        node = node_map[nid]
        rows.append(
            {
                "id": nid,
                "name": node.get("name") or nid,
                "handle": node.get("handle") or nid,
                "association_score": round(association, 6),
                "centrality_score": round(centrality, 6),
                "influence_score": round(influence, 6),
                "weighted_degree": round(weighted_degree[nid], 6),
                "cross_follow_ratio": round(cross_ratio[nid], 6),
                "pagerank": round(pr[nid], 8),
                "degree": deg[nid],
                "bridge_degree": bridge[nid],
            }
        )

    rows.sort(key=lambda x: (-x["influence_score"], x["id"]))
    vals = sorted([r["influence_score"] for r in rows])
    q80 = quantile_threshold(vals, 0.80)
    q60 = quantile_threshold(vals, 0.60)
    q40 = quantile_threshold(vals, 0.40)
    q20 = quantile_threshold(vals, 0.20)

    for i, r in enumerate(rows, start=1):
        r["rank"] = i
        score = r["influence_score"]
        if score >= q80:
            r["layer"] = "core"
            r["layer_index"] = 1
            r["layer_label"] = "核心"
        elif score >= q60:
            r["layer"] = "inner_core"
            r["layer_index"] = 2
            r["layer_label"] = "内核"
        elif score >= q40:
            r["layer"] = "middle_core"
            r["layer_index"] = 3
            r["layer_label"] = "中间核"
        elif score >= q20:
            r["layer"] = "outer_core"
            r["layer_index"] = 4
            r["layer_label"] = "外核"
        else:
            r["layer"] = "surface"
            r["layer_index"] = 5
            r["layer_label"] = "表层"

    return {
        "model": {
            "name": "association-centrality-v1",
            "alpha": alpha,
            "beta": beta,
            "association_formula": "0.7*weighted_degree_norm + 0.3*cross_follow_ratio_norm",
            "centrality_formula": "0.5*pagerank_norm + 0.35*degree_norm + 0.15*bridge_norm",
            "influence_formula": "alpha*association + beta*centrality",
        },
        "layers": {"core": 1, "inner_core": 2, "middle_core": 3, "outer_core": 4, "surface": 5},
        "nodes": rows,
    }


def build_html(payload: dict) -> str:
    rows = payload.get("nodes", [])
    layers = {"core": 90, "inner_core": 145, "middle_core": 205, "outer_core": 270, "surface": 340}
    colors = {
        "core": "#7dd3fc",
        "inner_core": "#34d399",
        "middle_core": "#fbbf24",
        "outer_core": "#f59e0b",
        "surface": "#94a3b8",
    }

    rnd = random.Random(42)
    dots = []
    for r in rows:
        layer = r.get("layer", "edge")
        base = layers.get(layer, 330)
        radius = base + rnd.uniform(-18, 18)
        theta = rnd.uniform(0, math.pi * 2)
        x = 400 + radius * math.cos(theta)
        y = 400 + radius * math.sin(theta)
        dots.append(
            {
                "x": round(x, 2),
                "y": round(y, 2),
                "name": r.get("name"),
                "handle": r.get("handle"),
                "rank": r.get("rank"),
                "layer": layer,
                "score": r.get("influence_score"),
                "color": colors.get(layer, "#94a3b8"),
            }
        )

    data_json = json.dumps(dots, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>关联度+核心度圈层图（可交互）</title>
  <style>
    body {{ margin:0; background:#070b18; color:#e2e8f0; font-family: -apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:16px; }}
    .title {{ font-size:20px; font-weight:700; }}
    .sub {{ margin-top:6px; color:#94a3b8; font-size:13px; }}
    .card {{ margin-top:12px; border:1px solid rgba(148,163,184,.25); border-radius:12px; background:#0b1228; padding:10px; }}
    svg {{ width:100%; height:auto; display:block; background: radial-gradient(circle at center, rgba(37,99,235,0.08), transparent 60%); border-radius:10px; }}
    .legend {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; font-size:12px; color:#cbd5e1; }}
    .tag {{ display:flex; align-items:center; gap:6px; }}
    .dot {{ width:10px; height:10px; border-radius:999px; }}
    .toolbar {{ margin-top:10px; display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; font-size:12px; color:#cbd5e1; }}
    .toolbar label {{ display:inline-flex; align-items:center; gap:6px; cursor:pointer; }}
    .toolbar input[type="checkbox"] {{ accent-color:#60a5fa; }}
    .toolbar input[type="text"] {{
      background:#0f172a; border:1px solid rgba(148,163,184,.35); color:#e2e8f0;
      border-radius:8px; padding:6px 8px; min-width:220px;
    }}
    .tip {{ margin-top:8px; font-size:12px; color:#93a4bf; }}
    .node-link text {{ fill:#dbe7ff; font-size:10px; paint-order:stroke; stroke:#0b1228; stroke-width:2px; pointer-events:none; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title">关联度 + 核心度 圈层可视化（可点击）</div>
    <div class="sub">支持点击节点跳转到 X，支持按层级筛选显示。</div>
    <div class="card">
      <div class="toolbar">
        <label><input type="checkbox" data-layer="core" checked />核心</label>
        <label><input type="checkbox" data-layer="inner_core" checked />内核</label>
        <label><input type="checkbox" data-layer="middle_core" checked />中间核</label>
        <label><input type="checkbox" data-layer="outer_core" checked />外核</label>
        <label><input type="checkbox" data-layer="surface" checked />表层</label>
        <input id="search" type="text" placeholder="搜索博主名 / @handle" />
      </div>
      <svg viewBox="0 0 800 800" id="viz"></svg>
      <div class="legend">
        <div class="tag"><span class="dot" style="background:#7dd3fc"></span>核心</div>
        <div class="tag"><span class="dot" style="background:#34d399"></span>内核</div>
        <div class="tag"><span class="dot" style="background:#fbbf24"></span>中间核</div>
        <div class="tag"><span class="dot" style="background:#f59e0b"></span>外核</div>
        <div class="tag"><span class="dot" style="background:#94a3b8"></span>表层</div>
      </div>
      <div class="tip">提示：点击任意节点会在新标签页打开对应 X 主页。</div>
    </div>
  </div>
  <script>
    const data = {data_json};
    const svg = document.getElementById('viz');
    const search = document.getElementById('search');
    const checkboxes = [...document.querySelectorAll('input[data-layer]')];
    const ns = 'http://www.w3.org/2000/svg';
    [['90','#1e293b'],['145','#1e293b'],['205','#1e293b'],['270','#1e293b'],['340','#1e293b']].forEach(([r,c])=>{{
      const circle = document.createElementNS(ns,'circle');
      circle.setAttribute('cx','400'); circle.setAttribute('cy','400'); circle.setAttribute('r',r);
      circle.setAttribute('fill','none'); circle.setAttribute('stroke',c); circle.setAttribute('stroke-width','1');
      svg.appendChild(circle);
    }});

    function render() {{
      [...svg.querySelectorAll('.node-link')].forEach(el => el.remove());
      const activeLayers = new Set(checkboxes.filter(cb => cb.checked).map(cb => cb.dataset.layer));
      const q = (search.value || '').trim().toLowerCase();

      data.forEach(n=>{{
        const blob = `${{n.name||''}} @${{n.handle||''}}`.toLowerCase();
        if (!activeLayers.has(n.layer)) return;
        if (q && !blob.includes(q)) return;

        const a = document.createElementNS(ns,'a');
        a.setAttribute('href', `https://x.com/${{n.handle}}`);
        a.setAttribute('target', '_blank');
        a.setAttribute('class', 'node-link');

        const c = document.createElementNS(ns,'circle');
        c.setAttribute('cx', n.x); c.setAttribute('cy', n.y);
        c.setAttribute('r', Math.max(2.6, 7 - Math.log10((n.rank||1)+1)));
        c.setAttribute('fill', n.color);
        c.setAttribute('opacity','0.92');
        c.setAttribute('stroke','rgba(255,255,255,0.35)');
        c.setAttribute('stroke-width','0.5');

        const label = document.createElementNS(ns,'text');
        label.setAttribute('x', Number(n.x) + 5);
        label.setAttribute('y', Number(n.y) - 5);
        label.textContent = n.name || n.handle;

        const t = document.createElementNS(ns,'title');
        t.textContent = `#${{n.rank}} ${{n.name}} @${{n.handle}} | ${{n.layer}} | score=${{n.score}}`;
        c.appendChild(t);
        a.appendChild(c);
        a.appendChild(label);
        svg.appendChild(a);
      }});
    }}

    checkboxes.forEach(cb => cb.addEventListener('change', render));
    search.addEventListener('input', render);
    render();
  </script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build association+centrality circle layers")
    parser.add_argument("--input", type=Path, required=True, help="Graph JSON path with nodes/links")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument("--html", type=Path, required=True, help="Output HTML path")
    parser.add_argument("--alpha", type=float, default=0.55, help="Association weight")
    parser.add_argument("--beta", type=float, default=0.45, help="Centrality weight")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    payload = build_layers(nodes, links, args.alpha, args.beta)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(payload), encoding="utf-8")
    print(f"Updated {args.output}")
    print(f"Updated {args.html}")
    print(f"Nodes: {len(payload.get('nodes', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
