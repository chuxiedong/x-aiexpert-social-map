# X AI Experts Visualization

## 1) 更新数据
在项目目录执行：

```bash
python3 scripts/update_mitbunny_graph.py
python3 scripts/update_experts.py --limit 300
```

如果你要把 `交叉关注 + 发帖/评论/点赞/转发` 纳入影响力：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
export X_BEARER_TOKEN="你的X API Bearer Token"
python3 scripts/update_engagement_metrics.py --limit 300 --tweets-per-user 50
python3 scripts/update_mitbunny_graph.py
```

说明：
- `scripts/update_engagement_metrics.py` 会写入 `data/engagement_metrics.json`
- `update_mitbunny_graph.py` 会自动读取 `data/engagement_metrics.json` 并重算 `quanzhong_score`
- 若无 API Token，可手工编辑 `data/engagement_metrics.json`

会生成：
- `data/mitbunny_graph.json`（主图谱数据）
- `data/top300.json`（Top300 结构化数据）
- `data/top300.csv`（Top300 可运营表格）
- `data/experts.json`（本地增强数据）

可选参数：

```bash
python3 scripts/update_experts.py --limit 300 --manual data/manual_experts.json
```

说明：
- `data/manual_experts.json` 中的专家会按 `handle` 合并覆盖（可修正分类/粉丝/标签，或新增必须展示账号）
- 模板文件已提供：`data/manual_experts.json`
- 每次更新都会写入历史快照：`data/history.json`
- 页面会自动读取最近 30 次快照并绘制“总粉丝趋势”折线图
- 页面优先使用 `history_daily` 绘制按天趋势，并展示“排名变化（相较上次快照）”

高级参数示例：

```bash
python3 scripts/update_experts.py --limit 300 --history-days 90 --rank-change-limit 20
```

## 2) 启动本地页面
为避免浏览器 `file://` 限制（无法 fetch 本地 JSON），建议本地启动 HTTP 服务：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 -m http.server 8765
```

浏览器打开：

`http://127.0.0.1:8765/`

## 3) 自动更新（可选）
如果你希望每小时更新一次：

```bash
while true; do
  python3 scripts/update_experts.py --limit 300
  sleep 3600
done
```

页面内已内置每 5 分钟自动重载 `data/experts.json`（在 HTTP 服务模式下生效）。

## 4) 商业化与运营面板

- 商业方案页：`/commercial.html`
- 线索收集页：`/contact.html`
- 运营看板：`/ops.html`

说明：
- 全站按钮与关键操作已接入本地埋点（`assets/metrics.js`），用于查看页面浏览和CTA点击。
- 线索表单保存于浏览器本地存储（便于快速试运营），后续可接企业CRM。

## 5) 项目自动心跳（自迭代巡检）

手动执行一次心跳：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 scripts/heartbeat.py
```

启动后台自动巡检（默认每 900 秒一次）：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/start_autopilot.sh 900
```

停止自动巡检：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/stop_autopilot.sh
```

输出文件：
- `data/heartbeat_status.json`：最新心跳结果
- `data/autopilot_loop.log`：后台循环日志
- `data/autopilot_last_run.log`：最近一次巡检日志

### macOS 常驻守护（推荐）

项目已提供 `launchd` 配置，可由系统级守护进程每 15 分钟执行一次心跳：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/install_launchd_autopilot.sh
```

配置文件：
- `ops/com.xai.experts.autopilot.plist`

## 数据来源
- x.mitbunny.ai graph bundle（主）
- https://x.mitbunny.ai
- Feedspot Top AI Influencers on X
- https://x.feedspot.com/artificial_intelligence_twitter_influencers/
- Top300 导出：`data/top300.json`
- Top300 表格：`data/top300.csv`

## UI 说明（参考 x.mitbunny.ai）
- 暗色网络舞台 + 可折叠左侧榜单
- 悬浮图例筛选与专家详情卡
- 方法论弹窗（展示抓取与评分流程）
- 顶栏 `立即刷新` 按钮可手动拉取最新 JSON
- 图谱模式切换：`3D（ForceGraph） / 2D（SVG兜底）`
- 榜单强制使用 Top300 排序池（来源：`data/top300.json`）
- 保留并增强趋势/排名变化可视化
- 新增关系连线开关（基于目标站真实 links）
- 趋势支持自动/快照/日/周四种粒度切换
