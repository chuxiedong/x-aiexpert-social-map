(() => {
  if (window.__xaiShareFabInstalled) return;
  window.__xaiShareFabInstalled = true;

  const css = `
  .xai-share-wrap{position:fixed;top:14px;right:14px;z-index:9999}
  .xai-share-btn{width:42px;height:42px;border-radius:999px;border:1px solid rgba(125,177,255,.45);background:linear-gradient(135deg,#1d3f82,#143062);color:#eef4ff;cursor:pointer;font-size:20px;line-height:1}
  .xai-share-menu{margin-top:8px;display:none;min-width:188px;background:#0f1730;border:1px solid rgba(148,163,184,.35);border-radius:10px;padding:6px}
  .xai-share-menu.open{display:block}
  .xai-share-item{display:block;width:100%;text-align:left;padding:9px 10px;border:0;background:transparent;color:#e8efff;border-radius:8px;cursor:pointer;font-size:13px}
  .xai-share-item:hover{background:rgba(125,177,255,.16)}
  `;
  const st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);

  const wrap = document.createElement("div");
  wrap.className = "xai-share-wrap";
  wrap.innerHTML = `
    <button class="xai-share-btn" id="xaiShareFab" title="Share">⤴</button>
    <div class="xai-share-menu" id="xaiShareMenu">
      <button class="xai-share-item" data-act="share"></button>
      <button class="xai-share-item" data-act="copy"></button>
      <button class="xai-share-item" data-act="image"></button>
      <button class="xai-share-item" data-act="poster"></button>
    </div>
  `;
  document.body.appendChild(wrap);

  const btn = document.getElementById("xaiShareFab");
  const menu = document.getElementById("xaiShareMenu");
  const getLang = () => localStorage.getItem("xai_lang") || "zh";

  function labels() {
    const zh = getLang() === "zh";
    const text = {
      share: zh ? "转发/分享" : "Forward / Share",
      copy: zh ? "复制链接" : "Copy Link",
      image: zh ? "导出当前页图片" : "Export Page Image",
      poster: zh ? "导出海报" : "Export Poster",
    };
    [...menu.querySelectorAll(".xai-share-item")].forEach((el) => {
      el.textContent = text[el.dataset.act];
    });
  }
  labels();
  window.addEventListener("storage", labels);

  btn.addEventListener("click", () => menu.classList.toggle("open"));
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) menu.classList.remove("open");
  });

  async function copyLink() {
    const u = window.location.href;
    try {
      await navigator.clipboard.writeText(u);
      alert(getLang() === "zh" ? "链接已复制" : "Link copied");
    } catch (_) {
      prompt(getLang() === "zh" ? "复制这个链接：" : "Copy this link:", u);
    }
  }

  async function forwardShare() {
    const u = window.location.href;
    const title = document.title || "AI Influence Intelligence";
    const text = getLang() === "zh" ? "给你看这个页面" : "Check this page";
    if (navigator.share) {
      try {
        await navigator.share({ title, text, url: u });
        return;
      } catch (_) {}
    }
    window.open(
      `https://x.com/intent/post?text=${encodeURIComponent(title)}&url=${encodeURIComponent(u)}`,
      "_blank"
    );
  }

  function posterUrl() {
    const p = window.location.pathname;
    const m = new URLSearchParams(window.location.search);
    const lang = getLang();
    if (p.startsWith("/profiles/")) {
      const slug = p.split("/").pop().replace(".html", "");
      return `/poster.html?mode=single&slug=${encodeURIComponent(slug)}&lang=${lang}`;
    }
    if (p.includes("daily_briefing") || p.includes("insights") || p.includes("daily_progress")) {
      return `/poster.html?mode=top10&lang=${lang}`;
    }
    if (m.get("slug")) return `/poster.html?mode=single&slug=${encodeURIComponent(m.get("slug"))}&lang=${lang}`;
    return `/poster.html?mode=top10&lang=${lang}`;
  }

  async function ensureHtml2Canvas() {
    if (window.html2canvas) return;
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function exportImage() {
    try {
      await ensureHtml2Canvas();
      const canvas = await window.html2canvas(document.body, {
        backgroundColor: null,
        scale: Math.min(2, window.devicePixelRatio || 1.5),
        useCORS: true,
        windowWidth: document.documentElement.scrollWidth,
        windowHeight: document.documentElement.scrollHeight,
      });
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = `page-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
    } catch (e) {
      alert(getLang() === "zh" ? "页面导出失败，请稍后重试" : "Page export failed");
    }
  }

  menu.addEventListener("click", async (e) => {
    const item = e.target.closest("[data-act]");
    if (!item) return;
    const act = item.dataset.act;
    menu.classList.remove("open");
    if (act === "share") await forwardShare();
    if (act === "copy") await copyLink();
    if (act === "image") await exportImage();
    if (act === "poster") window.open(posterUrl(), "_blank");
  });
})();

