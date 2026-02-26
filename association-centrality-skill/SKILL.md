---
name: association-centrality-skill
description: 通用“关联度+核心度”建模技能。对任意图数据（nodes/links）计算节点关联度、节点核心度、综合影响力，并自动输出圈层分层结果与可视化圈层 HTML。适用于社交网络、专家网络、组织网络、交易网络等。
---

# association-centrality-skill

## 目标
- 输入任意节点图谱，输出：
  - `association_score`（关联度）
  - `centrality_score`（核心度）
  - `influence_score`（综合分）
  - `layer`（圈层：core/strong/medium/edge）
  - 圈层可视化页面

## 输入约定
- `nodes`: 数组，至少有 `id`。
- `links`: 数组，至少有 `source/target`，可选 `weight`。
- 可选节点指标：`followers/likes/posts/comments/reposts/cross_follow_ratio` 等。

## 快速运行
```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 association-centrality-skill/scripts/build_circle_layers.py \
  --input data/mitbunny_graph.json \
  --output data/circle_layers.json \
  --html data/circle_layers.html
```

## 权重策略
- 关联度：`weighted_degree + reciprocity + interaction_strength`
- 核心度：`pagerank + degree_centrality + bridging`
- 综合分：`influence_score = alpha*association + beta*centrality`

可通过参数调节：
- `--alpha` 关联度权重
- `--beta` 核心度权重

## 输出文件
- JSON：含每个节点的分数和圈层标签
- HTML：可直接分享的圈层可视化页面

