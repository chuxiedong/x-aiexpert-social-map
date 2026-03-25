# X Domain Influence Intelligence

这个项目已经不再只是固定的 `AI Top300` 页面，而是一套可按领域切换的 X 关系图谱与内容情报站。

当前可交付能力：
- 关系图谱与五层圈层
- 最新分享 / Top10 / 每日进展
- 人物页 / 最佳互动基友
- 热点话题词云
- 公共信号页（GitHub / Hacker News / Wikipedia）
- 海报导出
- 商业页 / 联系页
- X 实时链路验真

## 1. 当前状态

当前项目支持两种数据模式：

1. `X API v2` 实时模式
2. `r.jina -> x.com` 公开回退模式

每次刷新后，系统都会把真实状态写进：
- `/Users/somalia/Desktop/x-ai-experts-viz/data/x_api_access.json`
- `/Users/somalia/Desktop/x-ai-experts-viz/data/x_realtime_status.json`
- `/Users/somalia/Desktop/x-ai-experts-viz/data/refresh_status.json`

重点字段：
- `x_api_access_status`
- `x_realtime_mode`
- `x_realtime_verified`

如果没有可用 `X_BEARER_TOKEN`，项目仍可运行，但会明确标记为 `fallback_only`，不会伪装成实时 X 数据。

## 2. 快速启动

### 2.1 本地静态服务

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 -m http.server 8876
```

打开：

- [http://127.0.0.1:8876/index.html](http://127.0.0.1:8876/index.html)
- [http://127.0.0.1:8876/topics.html](http://127.0.0.1:8876/topics.html)
- [http://127.0.0.1:8876/public_signals.html](http://127.0.0.1:8876/public_signals.html)

### 2.2 一键构建

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/build_release.sh 300
```

这条命令会执行：
- X API 预检
- 数据刷新
- 页面生成
- 完整性校验

## 3. X 实时链路

### 3.1 本地配置 token

复制环境模板：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
cp .env.example .env.local
```

填入：

```bash
X_BEARER_TOKEN=你的有效 Bearer Token
XAI_DAILY_TZ=Asia/Shanghai
```

然后执行：

```bash
bash scripts/refresh_site_data.sh 300
```

### 3.2 单独验证 token 是否可用

```bash
python3 scripts/check_x_api_access.py --json
```

返回常见状态：
- `ok`
- `missing_token`
- `unauthorized`
- `credits_depleted`
- `rate_limited`

### 3.3 验证当前是不是实时 X

```bash
python3 scripts/verify_x_realtime.py \
  --engagement data/engagement_metrics.json \
  --refresh-status data/refresh_status.json \
  --output data/x_realtime_status.json
```

## 4. 领域切换

### 4.1 预置领域模板

可用模板：

```bash
python3 scripts/apply_domain_config.py --list
```

当前已内置：
- `ai`
- `robotics`
- `vc`

### 4.2 应用一个领域模板

例如切到机器人领域：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 scripts/apply_domain_config.py robotics
```

这会：
- 覆盖 `data/domain_config.json`
- 重新生成页面和数据
- 运行校验

### 4.3 手工定制领域

编辑：

- `/Users/somalia/Desktop/x-ai-experts-viz/data/domain_config.json`

关键字段：
- `include_handles`: 强制纳入的账号
- `match_keywords`: 命中这些关键词才进入该领域
- `exclude_keywords`: 命中这些关键词则排除
- `topic_taxonomy`: 领域话题分类

改完后执行：

```bash
python3 scripts/generate_content_pages.py
python3 scripts/validate_data_integrity.py
```

## 5. 词云与热点页面

热点词云页面：
- `/Users/somalia/Desktop/x-ai-experts-viz/topics.html`

词云数据：
- `/Users/somalia/Desktop/x-ai-experts-viz/data/topic_cloud.json`

词云基于：
- 最新分享
- 今日热帖
- 人物标签
- 角色与简介

点击一个话题或热词后，会展示对应人物，并可跳转到人物页。

## 6. 公共信号页

公共信号页：
- `/Users/somalia/Desktop/x-ai-experts-viz/public_signals.html`

公共信号数据：
- `/Users/somalia/Desktop/x-ai-experts-viz/data/public_signals.json`

这层能力会把 X 内部热点，叠加到三类公开 API：
- `GitHub Search API`：看开源动向
- `Hacker News API`：看跨平台讨论
- `Wikipedia Search API`：看公共解释层

说明：
- `GitHub` 会尝试在构建期预抓一层兜底数据，并在浏览器里继续实时刷新
- `Hacker News` 与 `Wikipedia` 主要由浏览器实时请求
- 如果浏览器或当前网络无法访问外部源，页面会保留本地兜底结构，而不是空白

生成命令：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
python3 scripts/update_public_signals.py
```

## 7. 自动刷新与禁用状态

当前我已经把本机自动回改的 autopilot 停掉了。

禁用标记：
- `/Users/somalia/Desktop/x-ai-experts-viz/data/autopilot.disabled`

如果你想重新启用：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/start_autopilot.sh 900
```

如果你想再次停掉：

```bash
cd /Users/somalia/Desktop/x-ai-experts-viz
bash scripts/stop_autopilot.sh
```

## 8. GitHub Actions

工作流：
- `/Users/somalia/Desktop/x-ai-experts-viz/.github/workflows/daily-data-refresh.yml`

现在工作流会额外产出：
- `x_api_access.json`
- `x_realtime_status.json`
- `refresh_status.json` 中的 X API / realtime 验真字段

如果要让云端也走实时 X，请在仓库里配置：
- `X_BEARER_TOKEN`

## 9. 关键脚本

- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/refresh_site_data.sh`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/check_x_api_access.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/verify_x_realtime.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/generate_content_pages.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/update_public_signals.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/validate_data_integrity.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/apply_domain_config.py`
- `/Users/somalia/Desktop/x-ai-experts-viz/scripts/build_release.sh`

## 10. 当前已知外部阻塞

代码层面已经支持实时 X 主链路，但当前仍可能回退，原因通常只有这几个：

1. 没有配置 `X_BEARER_TOKEN`
2. token 无效
3. token 额度耗尽
4. X API 限流

系统不会再把这些情况伪装成“实时抓取成功”。
