#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK_START = "<!-- codex-i18n-fix:start -->"
MARK_END = "<!-- codex-i18n-fix:end -->"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new, 1)


def inject_script(path: Path, js: str) -> None:
    text = read(path)
    block = f"{MARK_START}\n<script>\n{js.strip()}\n</script>\n{MARK_END}"
    pattern = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.S)
    if MARK_START in text and MARK_END in text:
        text = pattern.sub(block, text)
    elif "</body>" in text:
        text = text.replace("</body>", block + "\n</body>")
    else:
        text = text + "\n" + block + "\n"
    write(path, text)


def patch_profiles_index() -> None:
    path = ROOT / "profiles" / "index.html"
    js = r'''
(() => {
  const lang = localStorage.getItem('xai_lang') || 'zh';
  const t = (zh, en) => lang === 'zh' ? zh : en;
  const q = document.getElementById('q');
  const layer = document.getElementById('layer');
  const sort = document.getElementById('sort');

  function localize() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = t('博主画像库', 'Creator Profiles');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('博主画像库', 'Creator Profiles');
    const labels = [
      t('首页', 'Home'),
      t('最新分享', 'Latest Shares'),
      'Top10',
      t('每日进展', 'Daily Progress'),
      t('热点词云', 'Topic Cloud'),
      t('公共信号', 'Public Signals'),
      t('自选海报', 'Custom Poster'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (labels[idx]) btn.textContent = labels[idx];
    });
    if (q) q.placeholder = t('搜索姓名 / @handle', 'Search name/handle');
    if (layer && layer.options.length && layer.options[0].value === 'all') {
      layer.options[0].textContent = t('全部圈层', 'All Layers');
    }
    if (sort) {
      const labels = {
        rank: t('按排名排序', 'Sort by Rank'),
        score: t('按分数排序', 'Sort by Score'),
        followers: t('按粉丝数排序', 'Sort by Followers')
      };
      [...sort.options].forEach((option) => {
        option.textContent = labels[option.value] || option.textContent;
      });
    }
    document.querySelectorAll('#grid .item').forEach((item) => {
      item.querySelectorAll('.muted').forEach((node) => {
        node.textContent = node.textContent.replace(/^score\s+/i, t('影响力分 ', 'score '));
      });
      const btns = item.querySelectorAll('.btn');
      if (btns[0]) btns[0].textContent = t('人物页', 'Profile');
      if (btns[1]) btns[1].textContent = t('海报', 'Poster');
      if (btns[2]) btns[2].textContent = t('打开 X', 'Open X');
    });
  }

  const origRender = window.render;
  if (typeof origRender === 'function' && !origRender.__codexI18nWrapped) {
    window.render = function() {
      origRender();
      localize();
    };
    window.render.__codexI18nWrapped = true;
  }
  localize();
  setTimeout(localize, 200);
})();
'''
    inject_script(path, js)


def patch_insights() -> None:
    path = ROOT / 'insights.html'
    js = r'''
(() => {
  const q = document.getElementById('q');
  const langSel = document.getElementById('lang');
  const timeSel = document.getElementById('time');
  const topicSel = document.getElementById('topic');
  const layerSel = document.getElementById('layer');
  const freshness = document.getElementById('freshness');

  function currentLang() {
    return langSel ? langSel.value : (localStorage.getItem('xai_lang') || 'zh');
  }
  function t(zh, en) {
    return currentLang() === 'zh' ? zh : en;
  }
  function localize() {
    const lang = currentLang();
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = t('最新分享', 'Latest Shares');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('最新分享', 'Latest Shares');
    const nav = [
      t('首页', 'Home'),
      t('人物库', 'Profiles'),
      'Top10',
      t('每日进展', 'Daily Progress'),
      t('热点词云', 'Topic Cloud'),
      t('公共信号', 'Public Signals'),
      t('Top10海报', 'Top10 Poster'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (nav[idx]) btn.textContent = nav[idx];
    });
    if (q) q.placeholder = t('搜索姓名 / @handle', 'Search name/handle');
    if (topicSel && topicSel.options.length && topicSel.options[0].value === 'all') {
      topicSel.options[0].textContent = t('全部主题', 'All Topics');
    }
    if (layerSel && layerSel.options.length && layerSel.options[0].value === 'all') {
      layerSel.options[0].textContent = t('全部圈层', 'All Layers');
    }
    if (timeSel) {
      const mapping = { '1': '24h', '7': '7d', '30': '30d' };
      [...timeSel.options].forEach((option) => {
        option.textContent = mapping[option.value] || option.textContent;
      });
    }
    if (freshness && lang === 'zh') {
      freshness.innerHTML = freshness.innerHTML.replace(/Recency:/g, '新鲜度：');
    }
    document.querySelectorAll('#grid .card').forEach((card) => {
      card.querySelectorAll('.muted').forEach((node) => {
        node.textContent = node.textContent.replace(/^Recency:\s*/i, t('新鲜度：', 'Recency: '));
        if (lang === 'en') node.textContent = node.textContent.replace(/^最佳互动基友：/, 'Best buddy: ');
      });
      const btns = card.querySelectorAll('.btn');
      if (btns[0]) btns[0].textContent = t('查看人物页', 'View Profile');
      if (btns[1]) btns[1].textContent = t('海报', 'Poster');
      if (btns[2]) btns[2].textContent = t('打开 X', 'Open X');
    });
  }

  if (langSel) {
    const stored = localStorage.getItem('xai_lang') || 'zh';
    langSel.value = stored;
    langSel.addEventListener('change', () => {
      localStorage.setItem('xai_lang', langSel.value);
      setTimeout(localize, 0);
    });
  }

  const origRender = window.render;
  if (typeof origRender === 'function' && !origRender.__codexI18nWrapped) {
    window.render = function() {
      origRender();
      localize();
    };
    window.render.__codexI18nWrapped = true;
  }
  localize();
  setTimeout(localize, 200);
})();
'''
    inject_script(path, js)


def patch_briefing() -> None:
    path = ROOT / 'daily_briefing.html'
    js = r'''
(() => {
  const lang = localStorage.getItem('xai_lang') || 'zh';
  const t = (zh, en) => lang === 'zh' ? zh : en;
  const grid = document.getElementById('grid');
  function localize() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = t('Top10 观点', 'Top10 Briefing');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('Top10 观点', 'Top10 Briefing');
    const nav = [
      t('首页', 'Home'),
      t('最新分享', 'Latest Shares'),
      t('每日进展', 'Daily Progress'),
      t('热点词云', 'Topic Cloud'),
      t('公共信号', 'Public Signals'),
      t('Top10整合海报', 'Top10 Poster'),
      t('自选博主海报', 'Custom Poster'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (nav[idx]) btn.textContent = nav[idx];
    });
    document.querySelectorAll('.share summary').forEach((node) => {
      node.title = t('分享', 'Share');
    });
    document.querySelectorAll('.share-menu button[data-action="poster"]').forEach((btn) => btn.textContent = t('下载海报', 'Download Poster'));
    document.querySelectorAll('.share-menu button[data-action="copy"]').forEach((btn) => btn.textContent = t('复制链接', 'Copy Link'));
    document.querySelectorAll('.share-menu button[data-action="native"]').forEach((btn) => btn.textContent = t('系统分享', 'System Share'));
    document.querySelectorAll('#grid .card').forEach((card) => {
      const p = card.querySelector('p');
      if (p && lang === 'en') p.innerHTML = p.innerHTML.replace('最新分享：', 'Latest share: ');
      const btns = card.querySelectorAll('.btn');
      if (btns[0]) btns[0].textContent = t('查看人物页', 'View Profile');
      if (btns[1]) btns[1].textContent = t('打开 X', 'Open X');
    });
  }
  localize();
  if (grid) {
    new MutationObserver(localize).observe(grid, { childList: true, subtree: true });
  }
  setTimeout(localize, 200);
})();
'''
    inject_script(path, js)


def patch_daily_progress() -> None:
    path = ROOT / 'daily_progress.html'
    js = r'''
(() => {
  const lang = localStorage.getItem('xai_lang') || 'zh';
  const t = (zh, en) => lang === 'zh' ? zh : en;
  const trend = document.getElementById('trend');
  function localize() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = t('每日领域进展', 'Daily Domain Progress');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('每日领域进展', 'Daily Domain Progress');
    const nav = [
      t('首页', 'Home'),
      t('最新分享', 'Latest Shares'),
      'Top10',
      t('热点词云', 'Topic Cloud'),
      t('公共信号', 'Public Signals'),
      t('Top10海报', 'Top10 Poster'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (nav[idx]) btn.textContent = nav[idx];
    });
    const cards = document.querySelectorAll('.wrap > .card');
    if (cards[1]) {
      const title = cards[1].querySelector('b');
      if (title) title.textContent = t('数据说明：', 'Data note:');
    }
    if (cards[2]) {
      const h3 = cards[2].querySelector('h3');
      if (h3) h3.textContent = t('热门主题', 'Top Topics');
    }
    if (cards[3]) {
      const h3 = cards[3].querySelector('h3');
      if (h3) h3.textContent = t('今日关键人物', 'Key People Today');
    }
    const zh = document.getElementById('sum_zh');
    const en = document.getElementById('sum_en');
    if (zh && en) {
      zh.style.display = lang === 'zh' ? '' : 'none';
      en.style.display = lang === 'zh' ? 'none' : '';
    }
    document.querySelectorAll('#trend .card').forEach((card) => {
      const btns = card.querySelectorAll('.btn');
      if (btns[0]) btns[0].textContent = t('查看人物', 'View Profile');
      if (btns[1]) btns[1].textContent = t('打开 X', 'Open X');
      if (btns[2]) btns[2].textContent = t('海报', 'Poster');
    });
  }
  localize();
  if (trend) new MutationObserver(localize).observe(trend, { childList: true, subtree: true });
  setTimeout(localize, 200);
})();
'''
    inject_script(path, js)


def patch_topics() -> None:
    path = ROOT / 'topics.html'
    js = r'''
(() => {
  const lang = localStorage.getItem('xai_lang') || 'zh';
  const t = (zh, en) => lang === 'zh' ? zh : en;
  const summary = document.getElementById('summary');
  const list = document.getElementById('list');
  function localize() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = t('热点词云', 'Topic Cloud');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('热点词云', 'Topic Cloud');
    const nav = [
      t('首页', 'Home'),
      t('最新分享', 'Latest Shares'),
      'Top10',
      t('每日进展', 'Daily Progress'),
      t('人物库', 'Profiles'),
      t('公共信号', 'Public Signals'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (nav[idx]) btn.textContent = nav[idx];
    });
    const cols = document.querySelectorAll('.row .card');
    if (cols[0]) {
      const h3 = cols[0].querySelector('h3');
      if (h3) h3.textContent = t('热点词云', 'Topic Cloud');
      const muted = cols[0].querySelector('.muted');
      if (muted) muted.textContent = t('点击词或主题，查看对应人物', 'Click a topic or term to inspect linked creators');
    }
    if (cols[1]) {
      const h3 = cols[1].querySelector('h3');
      if (h3) h3.textContent = t('关联人物', 'Linked Creators');
      const note = document.getElementById('selectionNote');
      if (note && note.textContent.trim() === '先选择一个话题或热词') {
        note.textContent = t('先选择一个话题或热词', 'Pick a topic or term first');
      }
    }
    if (summary) {
      const muted = summary.querySelector('.muted');
      if (muted) muted.style.display = lang === 'zh' ? 'none' : '';
      const bold = summary.querySelector('b');
      if (bold && lang === 'zh') bold.textContent = '热点词云';
    }
    if (list) {
      list.querySelectorAll('.item.muted').forEach((node) => {
        node.textContent = t('暂无匹配人物', 'No linked creators');
      });
    }
  }
  localize();
  if (summary) new MutationObserver(localize).observe(summary, { childList: true, subtree: true });
  if (list) new MutationObserver(localize).observe(list, { childList: true, subtree: true });
  setTimeout(localize, 200);
})();
'''
    inject_script(path, js)


def patch_poster() -> None:
    path = ROOT / 'poster.html'
    text = read(path)
    text = replace_once(text, "const lang=params.get('lang')||'zh';", "const lang=(params.get('lang')||localStorage.getItem('xai_lang')||'zh');")
    write(path, text)
    js = r'''
(() => {
  const locale = (new URLSearchParams(location.search).get('lang') || localStorage.getItem('xai_lang') || 'zh');
  const isZh = locale === 'zh';
  const t = (zh, en) => isZh ? zh : en;
  const titleNode = document.getElementById('title');
  const descNode = document.getElementById('desc');
  const essenceNode = document.getElementById('essence');
  const qMeta = document.querySelector('.meta[style*="margin-top:10px"]');

  function localizeStatic() {
    document.documentElement.lang = isZh ? 'zh-CN' : 'en';
    document.title = t('一键转海报', 'Share Poster');
    const h2 = document.querySelector('.top h2');
    if (h2) h2.textContent = t('一键转海报', 'Share Poster');
    const nav = [
      t('首页', 'Home'),
      t('最新分享', 'Latest Shares'),
      'Top10',
      t('每日进展', 'Daily Progress'),
      t('热点词云', 'Topic Cloud'),
      t('公共信号', 'Public Signals'),
      t('商业化', 'Commercial'),
      t('联系', 'Contact')
    ];
    document.querySelectorAll('.top .btn').forEach((btn, idx) => {
      if (nav[idx]) btn.textContent = nav[idx];
    });
    if (titleNode && titleNode.textContent.trim() === 'Loading...') titleNode.textContent = t('加载中...', 'Loading...');
    document.querySelectorAll('[data-mode="single"]').forEach((n) => n.textContent = t('单人海报', 'Single Poster'));
    document.querySelectorAll('[data-mode="top10"]').forEach((n) => n.textContent = t('Top10整合海报', 'Top10 Poster'));
    document.querySelectorAll('[data-mode="custom"]').forEach((n) => n.textContent = t('自选博主海报', 'Custom Poster'));
    document.querySelectorAll('[data-style="clean"]').forEach((n) => n.textContent = t('简洁版', 'Clean'));
    document.querySelectorAll('[data-style="pro"]').forEach((n) => n.textContent = t('商务版', 'Business'));
    document.querySelectorAll('[data-style="vivid"]').forEach((n) => n.textContent = t('活力版', 'Vivid'));
    document.querySelectorAll('[data-style="brand"]').forEach((n) => n.textContent = t('品牌版', 'Brand'));
    if (window.brandColorInput) brandColorInput.placeholder = t('品牌色，如 #2f7cff', 'Brand color, e.g. #2f7cff');
    if (window.brandSloganInput) brandSloganInput.placeholder = t('品牌标语，如 AI Influence Daily', 'Brand slogan, e.g. AI Influence Daily');
    if (window.brandLogoInput) brandLogoInput.placeholder = t('Logo URL（可选）', 'Logo URL (optional)');
    if (qMeta) qMeta.textContent = t('海报尺寸: 1080x1920 · 支持单人 / Top10 / 自选模式', 'Poster size: 1080x1920 · single / top10 / custom');
    const btns = document.querySelectorAll('#downloadBtn, #copyBtn, #openProfile, #openX');
    if (btns[0]) btns[0].textContent = t('下载海报 PNG', 'Download PNG');
    if (btns[1]) btns[1].textContent = t('复制分享链接', 'Copy Share Link');
    if (btns[2]) btns[2].textContent = t('打开博主页', 'Open Profile');
    if (btns[3]) btns[3].textContent = t('打开 X', 'Open X');
  }

  if (isZh && typeof window.drawSingle === 'function') {
    window.drawSingle = function(r) {
      const theme = getTheme();
      drawBackground(theme);
      const brandSlogan = (brandSloganInput.value || 'AI Influence Daily').trim() || 'AI Influence Daily';
      const noTodayShare = !(r && (r.latest_share_zh || r.latest_share_en));
      const buddy = pickBestBuddyInScope(r);
      ctx.fillStyle = theme.title;
      ctx.font = '700 58px "IBM Plex Sans",sans-serif';
      ctx.fillText('AI 观点海报', 100, 170);
      ctx.fillStyle = theme.meta;
      ctx.font = '500 34px "IBM Plex Sans",sans-serif';
      ctx.fillText(`@${r.handle} | 影响力分 ${Number(r.score || 0).toFixed(3)} | ${r.layer_zh || r.layer || ''}`, 100, 235);
      ctx.fillStyle = '#ffffff';
      ctx.font = '800 70px "IBM Plex Sans",sans-serif';
      wrapText(ctx, r.name || '', 100, 350, 860, 86, 2);
      ctx.fillStyle = '#bed6ff';
      ctx.font = '500 34px "IBM Plex Sans",sans-serif';
      wrapText(ctx, (r.topics || []).join(' · '), 100, 540, 860, 48, 3);
      ctx.fillStyle = '#eef5ff';
      ctx.font = '600 44px "IBM Plex Sans",sans-serif';
      ctx.fillText('最新分享', 100, 760);
      ctx.fillStyle = '#d8e7ff';
      ctx.font = '500 38px "IBM Plex Sans",sans-serif';
      wrapText(ctx, noTodayShare ? '无分享，请换一个。' : (r.latest_share_zh || r.latest_viewpoint_zh || r.daily_essence_zh || ''), 100, 835, 880, 54, 10);
      ctx.fillStyle = '#9ec0f1';
      ctx.font = '500 30px "IBM Plex Sans",sans-serif';
      ctx.fillText(buddy ? `今日最佳基友: ${buddy.name} @${buddy.handle}` : '今日最佳基友: 暂无', 100, 1448);
      ctx.fillStyle = theme.box;
      ctx.fillRect(100, 1490, 880, 240);
      ctx.strokeStyle = theme.boxStroke;
      ctx.strokeRect(100, 1490, 880, 240);
      ctx.fillStyle = '#a9d7ff';
      ctx.font = '500 34px "IBM Plex Sans",sans-serif';
      ctx.fillText(styleKey === 'brand' ? brandSlogan : '关联度 + 核心度', 130, 1560);
      ctx.fillStyle = '#ecf5ff';
      ctx.font = '700 52px "IBM Plex Sans",sans-serif';
      ctx.fillText(`A ${Number(r.association_score || 0).toFixed(3)} / C ${Number(r.centrality_score || 0).toFixed(3)}`, 130, 1640);
      ctx.fillStyle = '#a9d7ff';
      ctx.font = '500 30px "IBM Plex Sans",sans-serif';
      ctx.fillText('x-ai-experts-viz · 可分享观点卡片', 130, 1710);
      ctx.fillStyle = '#8ab5e8';
      ctx.font = '500 26px "IBM Plex Sans",sans-serif';
      ctx.fillText(`https://x.com/${r.handle}`, 100, 1830);
    };
  }

  if (isZh && typeof window.drawMulti === 'function') {
    window.drawMulti = function(items) {
      const theme = getTheme();
      drawBackground(theme);
      ctx.fillStyle = theme.title;
      ctx.font = '700 56px "IBM Plex Sans",sans-serif';
      ctx.fillText(posterMode === 'top10' ? 'Top10 观点合集' : '自选观点合集', 100, 160);
      ctx.fillStyle = theme.meta;
      ctx.font = '500 30px "IBM Plex Sans",sans-serif';
      ctx.fillText(`数量 ${items.length} · ${new Date().toISOString().slice(0, 10)}`, 100, 215);
      let y = 290;
      items.slice(0, 10).forEach((r, i) => {
        ctx.fillStyle = 'rgba(255,255,255,.08)';
        ctx.fillRect(90, y - 46, 900, 145);
        ctx.strokeStyle = 'rgba(255,255,255,.15)';
        ctx.strokeRect(90, y - 46, 900, 145);
        ctx.fillStyle = '#eaf4ff';
        ctx.font = '700 34px "IBM Plex Sans",sans-serif';
        ctx.fillText(`#${i + 1} ${r.name}`, 120, y);
        ctx.fillStyle = '#a9c8f3';
        ctx.font = '500 26px "IBM Plex Sans",sans-serif';
        ctx.fillText(`@${r.handle} · 影响力分 ${Number(r.score || 0).toFixed(3)}`, 120, y + 42);
        ctx.fillStyle = '#d6e5ff';
        ctx.font = '500 24px "IBM Plex Sans",sans-serif';
        wrapText(ctx, (r.topics || []).slice(0, 2).join(' · ') || '热点主题', 120, y + 78, 760, 34, 1);
        y += 165;
      });
      ctx.fillStyle = 'rgba(255,255,255,.12)';
      ctx.fillRect(90, 1720, 900, 120);
      ctx.fillStyle = '#dbe8ff';
      ctx.font = '600 30px "IBM Plex Sans",sans-serif';
      ctx.fillText((brandSloganInput.value || 'AI Influence Daily').trim() || 'AI Influence Daily', 120, 1788);
    };
  }

  const origSetInfo = window.setInfo;
  if (typeof origSetInfo === 'function' && !origSetInfo.__codexI18nWrapped) {
    window.setInfo = function(items) {
      origSetInfo(items);
      localizeStatic();
      if (!isZh) return;
      if (items.length === 1) {
        const r = items[0];
        const noTodayShare = !(r && (r.latest_share_zh || r.latest_share_en));
        const buddy = pickBestBuddyInScope(r);
        if (titleNode) titleNode.textContent = `${r.name} @${r.handle}`;
        if (descNode) descNode.textContent = `圈层 ${r.layer_zh || r.layer || ''} · 影响力分 ${Number(r.score || 0).toFixed(3)} · 单人海报${buddy ? ` · 今日最佳基友 ${buddy.name}` : ''}`;
        if (essenceNode) essenceNode.textContent = noTodayShare ? '无分享，请换一个。' : (r.latest_share_zh || r.latest_viewpoint_zh || r.daily_essence_zh || '');
      } else {
        if (titleNode) titleNode.textContent = `${posterMode === 'top10' ? 'Top10' : '自选'} 聚合海报`;
        if (descNode) descNode.textContent = `共 ${items.length} 位博主 · ${posterMode === 'top10' ? 'Top10模式' : '自选模式'}`;
        if (essenceNode) essenceNode.textContent = '可一键分享整页观点，适合日报、周报、社群分发。';
      }
    };
    window.setInfo.__codexI18nWrapped = true;
  }

  localizeStatic();
  setTimeout(localizeStatic, 200);
})();
'''
    inject_script(path, js)


def patch_profile_pages() -> None:
    js = r'''
(() => {
  const lang = localStorage.getItem('xai_lang') || 'zh';
  const t = (zh, en) => lang === 'zh' ? zh : en;
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  const name = (document.querySelector('.name') || {}).textContent || 'Profile';
  document.title = lang === 'zh' ? `${name} | 博主画像` : `${name} | Profile`;
  const links = [...document.querySelectorAll('.row .btn')];
  links.forEach((link) => {
    const href = link.getAttribute('href') || '';
    if (/^https:\/\/x\.com\//.test(href)) link.textContent = t('打开 X', 'Open X');
    else if (href === './index.html') link.textContent = t('返回人物库', 'Profiles');
    else if (href.includes('../topics.html')) link.textContent = t('热点词云', 'Topic Cloud');
    else if (href.includes('../public_signals.html')) link.textContent = t('公共信号', 'Public Signals');
    else if (href.includes('../poster.html')) link.textContent = t('分享海报', 'Share Poster');
    else if (href.includes('../commercial.html')) link.textContent = t('商业化', 'Commercial');
    else if (href.includes('../contact.html')) link.textContent = t('联系', 'Contact');
  });
  const layerLine = document.querySelector('.card > .muted');
  if (layerLine) {
    const parts = layerLine.textContent.split('/').map((x) => x.trim());
    const zhLayer = parts[1] || parts[0] || '';
    const enLayer = parts[0].replace(/^Layer:\s*/i, '').trim() || parts[1] || '';
    layerLine.textContent = lang === 'zh' ? `圈层：${zhLayer}` : `Layer: ${enLayer}`;
  }
  const notice = document.querySelector('.notice');
  if (notice && lang !== 'zh') {
    notice.textContent = notice.textContent
      .replace('最近分享时间：', 'Latest share time: ')
      .replace('最近内容距今', 'Content recency: ')
      .replace('天。若今天没有新帖，页面会展示最近一次可用分享，不伪装为当日观点。', ' day(s). If there is no new post today, the page keeps the latest verifiable share instead of pretending it is from today.')
      .replace('当前未拿到可确认发布时间的原始帖子，页面仅展示最近一次可用抓取结果。', 'No verified source timestamp is available yet, so the page shows the latest usable captured share.');
  }
  const kpiLabels = lang === 'zh'
    ? ['排名','影响力分','粉丝数','关联度','核心度','发帖/评论','点赞/转发']
    : ['Rank','Influence Score','Followers','Association Score','Centrality Score','Posts/Comments','Likes/Reposts'];
  document.querySelectorAll('.kpi .k').forEach((node, idx) => {
    if (idx < kpiLabels.length) node.textContent = kpiLabels[idx];
  });
  const sections = [...document.querySelectorAll('.sec')];
  if (sections[0]) {
    const h3 = sections[0].querySelector('h3');
    if (h3) h3.textContent = t('评分解释', 'Explainability');
    const info = sections[0].querySelector('.muted');
    if (info && lang !== 'zh') info.textContent = 'Association reflects cross-follow, interaction strength, and link weight. Centrality reflects PageRank, connectivity, and audience scale.';
    const children = [...sections[0].children];
    children.forEach((child) => {
      if (child.textContent.startsWith('Association:')) child.textContent = lang === 'zh' ? child.textContent.replace('Association:', '关联度：') : child.textContent;
      if (child.textContent.startsWith('Centrality:')) child.textContent = lang === 'zh' ? child.textContent.replace('Centrality:', '核心度：') : child.textContent;
      if (child.textContent.startsWith('Cross-follow')) {
        child.textContent = lang === 'zh'
          ? child.textContent.replace('Cross-follow', '交叉关注').replace('Interaction', '互动').replace('PageRank', 'PageRank')
          : child.textContent;
      }
    });
  }
  if (sections[1]) {
    const h3 = sections[1].querySelector('h3');
    if (h3) h3.textContent = t('最佳互动基友 Top5', 'Top 5 Best Buddies');
    const info = sections[1].querySelector('.muted');
    if (info && lang !== 'zh') info.textContent = 'Computed from association-centrality relationship strength plus interaction proxy signals.';
  }
  if (sections[2]) sections[2].querySelector('h3').textContent = t('中文简介', 'Chinese Summary');
  if (sections[3]) {
    sections[3].querySelector('h3').textContent = t('英文简介', 'English Summary');
    sections[3].style.display = lang === 'zh' ? 'none' : '';
  }
  if (sections[4]) sections[4].querySelector('h3').textContent = t('最新分享', 'Latest Share');
  if (sections[5]) {
    sections[5].querySelector('h3').textContent = t('英文观点', 'Daily Insight (EN)');
    sections[5].style.display = lang === 'zh' ? 'none' : '';
  }
})();
'''
    for path in (ROOT / 'profiles').glob('*.html'):
      if path.name == 'index.html':
        continue
      inject_script(path, js)


def patch_public_signals() -> None:
    path = ROOT / 'public_signals.html'
    text = read(path)
    text = text.replace('<span class="badge" id="updatedBadge">Updated: -</span>', '<span class="badge" id="updatedBadge">内容时间: -</span>')
    write(path, text)


def patch_index() -> None:
    path = ROOT / 'index.html'
    text = read(path)
    text = text.replace('<span class="badge" id="proof_updated">Updated: -</span>', '<span class="badge" id="proof_updated">内容时间: -</span>')
    write(path, text)


def main() -> int:
    patch_index()
    patch_public_signals()
    patch_profiles_index()
    patch_insights()
    patch_briefing()
    patch_daily_progress()
    patch_topics()
    patch_poster()
    patch_profile_pages()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
