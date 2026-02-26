---
name: quanzhong-skill
description: 基于语义网络分析与灰色关联度分析，计算节点间关联度与节点综合权重（quanzhong_score），并输出可排序的社交影响力排名。适用于社交网络、关系网络、专家网络等图谱排名任务。
---

# quanzhong-skill

## 适用场景
- 需要从图数据（nodes + links）计算节点间关联权重。
- 需要把“结构关系 + 语义关系”合成为统一排名分数。
- 需要可解释指标：灰色关联度、语义得分、关联权重、PageRank。

## 输入约定
- `nodes`: 节点数组，至少包含 `id`（推荐含 `name/handle/group/role/bio/followers`）。
- `links`: 边数组，包含 `source/target`。

## 输出约定
- `weighted_links`: 每条边的 `weight/structural/semantic_similarity`。
- `node_metrics`: 每个节点的
  - `grey_relation`
  - `association_weight` / `association_weight_norm`
  - `cross_follow_count` / `cross_follow_ratio`
  - `posts_count` / `comments_count` / `likes_count` / `reposts_count`
  - `semantic_ai`
  - `pagerank`
  - `quanzhong_score`

## 方法摘要（来自论文思想抽象）
1. 构造多指标向量（关注度、拓扑连接、语义相关、中心性）。
2. 指标规范化到 `[0,1]`（效益型指标）。
3. 设参考序列 `x0(k)=1`，计算灰色关联系数与灰色关联度。
4. 结合节点关联权重（weighted degree）得到最终 `quanzhong_score`。
5. 按 `quanzhong_score` 排序得到影响力排名。

## 互动数据入口
- 文件：`data/engagement_metrics.json`
- 字段：`handle, posts_count, comments_count, likes_count, reposts_count`
- 可用脚本自动生成：
  `python3 scripts/update_engagement_metrics.py --limit 300 --tweets-per-user 50`

## 执行方式
- 运行脚本：`scripts/quanzhong_rank.py`
- 示例：
  `python3 quanzhong-skill/scripts/quanzhong_rank.py --input data/mitbunny_graph.json --output data/top300_quanzhong.json --csv data/top300_quanzhong.csv`

## 代码位置
- 核心模型：`scripts/quanzhong_model.py`
- 技能入口：`quanzhong-skill/scripts/quanzhong_rank.py`
