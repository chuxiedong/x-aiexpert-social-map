;(function () {
  function hasChinese(s) {
    return /[\u4e00-\u9fff]/.test(String(s || ""));
  }

  function translateEnToZh(text) {
    let t = String(text || "").trim();
    if (!t) return "";
    if (hasChinese(t)) return t;

    const rules = [
      [/\bnew\s+paper\b/gi, "新论文"],
      [/\bpaper\b/gi, "论文"],
      [/\bresearch\b/gi, "研究"],
      [/\bbenchmark\b/gi, "基准测试"],
      [/\bopen\s*source\b/gi, "开源"],
      [/\bopen\-sourced\b/gi, "已开源"],
      [/\brelease(d)?\b/gi, "发布"],
      [/\blaunch(ed)?\b/gi, "上线"],
      [/\bmodel(s)?\b/gi, "模型"],
      [/\btraining\b/gi, "训练"],
      [/\binference\b/gi, "推理"],
      [/\bagent(s)?\b/gi, "智能体"],
      [/\bworkflow(s)?\b/gi, "工作流"],
      [/\bproduction\b/gi, "生产环境"],
      [/\bdeploy(ment)?\b/gi, "部署"],
      [/\bperformance\b/gi, "性能"],
      [/\bsafety\b/gi, "安全"],
      [/\balignment\b/gi, "对齐"],
      [/\bfine[- ]?tuning\b/gi, "微调"],
      [/\bAPI\b/g, "接口"],
      [/\bSDK\b/g, "开发工具包"],
      [/\bGPU(s)?\b/g, "GPU"],
      [/\bNVIDIA\b/g, "英伟达"],
      [/\bOpenAI\b/g, "OpenAI"],
      [/\bX\b/g, "X 平台"],
    ];
    for (const [re, to] of rules) t = t.replace(re, to);
    t = t.replace(/\s{2,}/g, " ").trim();
    return "最新分享：" + t;
  }

  function pickZhShare(row) {
    if (!row) return "";
    const zh = row.latest_share_zh || row.latest_viewpoint_zh || row.daily_essence_zh;
    if (zh) return zh;
    const en = row.latest_share_en || row.latest_viewpoint_en || row.daily_essence_en || "";
    return translateEnToZh(en);
  }

  window.XAIShareI18n = { pickZhShare, translateEnToZh, hasChinese };
})();
