(function () {
  const STYLE_ID = "qz-overlay-style";
  const ROOT_ID = "qz-overlay-root";

  function fmtFollowers(n) {
    const v = Number(n || 0);
    if (!Number.isFinite(v)) return "-";
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
    return String(Math.round(v));
  }

  function f6(n) {
    const v = Number(n);
    return Number.isFinite(v) ? v.toFixed(6) : "-";
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${ROOT_ID} {
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 99999;
        color: #e8efff;
        font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      }
      #${ROOT_ID} .qz-btn {
        border: 1px solid rgba(150, 198, 255, 0.45);
        background: linear-gradient(130deg, #13284f, #0b1433 70%);
        color: #d8e6ff;
        border-radius: 999px;
        padding: 9px 14px;
        font-size: 12px;
        letter-spacing: 0.2px;
        cursor: pointer;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
      }
      #${ROOT_ID} .qz-panel {
        width: min(460px, calc(100vw - 24px));
        height: min(76vh, 760px);
        margin-top: 10px;
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(140, 187, 255, 0.28);
        background: radial-gradient(circle at 20% 0%, #16305b 0%, #0a122b 44%);
        box-shadow: 0 18px 45px rgba(0, 0, 0, 0.5);
        display: none;
        flex-direction: column;
      }
      #${ROOT_ID}.open .qz-panel { display: flex; }
      #${ROOT_ID} .qz-head {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      #${ROOT_ID} .qz-title {
        font-size: 13px;
        font-weight: 700;
        color: #cfe1ff;
      }
      #${ROOT_ID} .qz-sub {
        font-size: 11px;
        color: #8aa4cf;
        margin-top: 2px;
      }
      #${ROOT_ID} .qz-close {
        border: 0;
        background: rgba(255, 255, 255, 0.08);
        color: #c5d8ff;
        border-radius: 8px;
        padding: 4px 8px;
        cursor: pointer;
      }
      #${ROOT_ID} .qz-tools {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 8px;
      }
      #${ROOT_ID} .qz-links {
        padding: 8px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        gap: 8px;
      }
      #${ROOT_ID} .qz-link {
        border: 1px solid rgba(160, 190, 255, 0.25);
        background: rgba(9, 18, 42, 0.65);
        color: #d8e6ff;
        border-radius: 8px;
        padding: 6px 9px;
        font-size: 11px;
        text-decoration: none;
      }
      #${ROOT_ID} input {
        width: 100%;
        border: 1px solid rgba(160, 190, 255, 0.25);
        background: rgba(9, 18, 42, 0.65);
        color: #e7f0ff;
        border-radius: 9px;
        padding: 7px 10px;
        font-size: 12px;
        outline: none;
      }
      #${ROOT_ID} .qz-sort {
        border: 1px solid rgba(160, 190, 255, 0.25);
        background: rgba(9, 18, 42, 0.65);
        color: #d8e6ff;
        border-radius: 9px;
        padding: 7px 10px;
        font-size: 12px;
      }
      #${ROOT_ID} .qz-list {
        overflow: auto;
        padding: 6px 8px 10px;
      }
      #${ROOT_ID} .qz-row {
        display: grid;
        grid-template-columns: 36px 1fr auto;
        align-items: center;
        gap: 9px;
        border: 1px solid rgba(255, 255, 255, 0.07);
        background: rgba(11, 23, 51, 0.56);
        border-radius: 10px;
        padding: 8px;
        margin-bottom: 7px;
      }
      #${ROOT_ID} .qz-rank {
        font-size: 12px;
        font-weight: 700;
        color: #8fb6ff;
        text-align: center;
      }
      #${ROOT_ID} .qz-main {
        min-width: 0;
      }
      #${ROOT_ID} .qz-name {
        font-size: 12px;
        font-weight: 600;
        color: #eff5ff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      #${ROOT_ID} .qz-meta {
        margin-top: 2px;
        font-size: 11px;
        color: #93add6;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      #${ROOT_ID} .qz-score {
        font-size: 11px;
        text-align: right;
        color: #d8e6ff;
      }
      #${ROOT_ID} .qz-score b {
        font-size: 12px;
        color: #96deff;
      }
      #${ROOT_ID} .qz-empty {
        color: #96a9c9;
        font-size: 12px;
        padding: 14px;
      }
      #${ROOT_ID} a {
        color: inherit;
        text-decoration: none;
      }
      @media (max-width: 768px) {
        #${ROOT_ID} {
          left: 8px;
          right: 8px;
          bottom: calc(8px + env(safe-area-inset-bottom));
        }
        #${ROOT_ID} .qz-btn {
          width: 100%;
          min-height: 42px;
          font-size: 13px;
        }
        #${ROOT_ID} .qz-panel {
          width: 100%;
          height: min(82vh, 760px);
          border-radius: 14px;
        }
        #${ROOT_ID} .qz-head {
          padding: 12px;
        }
        #${ROOT_ID} .qz-title {
          font-size: 14px;
        }
        #${ROOT_ID} .qz-sub {
          font-size: 12px;
        }
        #${ROOT_ID} .qz-tools {
          grid-template-columns: 1fr;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createRoot() {
    if (document.getElementById(ROOT_ID)) return document.getElementById(ROOT_ID);
    const root = document.createElement("section");
    root.id = ROOT_ID;
    root.innerHTML = `
      <button class="qz-btn" type="button">Quanzhong 排名</button>
      <div class="qz-panel">
        <div class="qz-head">
          <div>
            <div class="qz-title">X 平台 AI 影响力（Quanzhong）</div>
            <div class="qz-sub" id="qz-meta">加载中...</div>
          </div>
          <button class="qz-close" type="button">收起</button>
        </div>
        <div class="qz-tools">
          <input id="qz-search" type="text" placeholder="搜索 name / @handle" />
          <select id="qz-sort" class="qz-sort">
            <option value="quanzhong">按 Quanzhong</option>
            <option value="followers">按 Followers</option>
            <option value="grey">按 Grey</option>
          </select>
        </div>
        <div class="qz-links">
          <a class="qz-link" href="./data/circle_layers.html" target="_blank" rel="noopener noreferrer">圈层图（5层）</a>
          <a class="qz-link" href="./quanzhong_ranking.html" target="_blank" rel="noopener noreferrer">指标页</a>
        </div>
        <div class="qz-list" id="qz-list"></div>
      </div>
    `;
    document.body.appendChild(root);
    return root;
  }

  function getSortedRows(rows, mode) {
    const data = rows.slice();
    if (mode === "followers") {
      data.sort((a, b) => Number(b.followers || 0) - Number(a.followers || 0));
      return data;
    }
    if (mode === "grey") {
      data.sort((a, b) => Number(b.grey_relation || 0) - Number(a.grey_relation || 0));
      return data;
    }
    data.sort((a, b) => Number(b.quanzhong_score || 0) - Number(a.quanzhong_score || 0));
    return data;
  }

  function renderRows(root, rows) {
    const listEl = root.querySelector("#qz-list");
    const searchEl = root.querySelector("#qz-search");
    const sortEl = root.querySelector("#qz-sort");
    const keyword = (searchEl.value || "").trim().toLowerCase();
    const mode = sortEl.value;

    const filtered = rows.filter((x) => {
      if (!keyword) return true;
      const name = String(x.name || "").toLowerCase();
      const handle = String(x.handle || "").toLowerCase();
      return name.includes(keyword) || handle.includes(keyword);
    });
    const sorted = getSortedRows(filtered, mode);

    if (!sorted.length) {
      listEl.innerHTML = `<div class="qz-empty">没有匹配结果</div>`;
      return;
    }

    listEl.innerHTML = sorted
      .slice(0, 300)
      .map((x, i) => {
        const rank = i + 1;
        const name = x.name || x.handle || "-";
        const handle = x.handle || "-";
        return `
          <a class="qz-row" href="https://x.com/${handle}" target="_blank" rel="noopener noreferrer">
            <div class="qz-rank">#${rank}</div>
            <div class="qz-main">
              <div class="qz-name">${name}</div>
              <div class="qz-meta">@${handle} · ${fmtFollowers(Number(x.followers || 0))} followers · Cross ${f6(Number(x.cross_follow_ratio || 0))}</div>
            </div>
            <div class="qz-score">
              <div><b>${f6(Number(x.quanzhong_score || 0))}</b></div>
              <div>Grey ${f6(Number(x.grey_relation || 0))} · Like ${fmtFollowers(Number(x.likes_count || 0))}</div>
            </div>
          </a>
        `;
      })
      .join("");
  }

  async function loadData() {
    const urls = ["./data/top300.json", "./data/top300_quanzhong.json"];
    for (const url of urls) {
      try {
        const resp = await fetch(url, { cache: "no-store" });
        if (!resp.ok) continue;
        const data = await resp.json();
        const rows = Array.isArray(data.experts) ? data.experts : Array.isArray(data.top300) ? data.top300 : [];
        if (rows.length) return data;
      } catch (_err) {}
    }
    return { experts: [] };
  }

  async function init() {
    injectStyle();
    const root = createRoot();
    const btn = root.querySelector(".qz-btn");
    const close = root.querySelector(".qz-close");
    const search = root.querySelector("#qz-search");
    const sort = root.querySelector("#qz-sort");
    const meta = root.querySelector("#qz-meta");

    btn.addEventListener("click", () => root.classList.toggle("open"));
    close.addEventListener("click", () => root.classList.remove("open"));

    const data = await loadData();
    const rows = Array.isArray(data.experts) ? data.experts : Array.isArray(data.top300) ? data.top300 : [];
    meta.textContent = `样本 ${rows.length} · 更新 ${data.generated_at || "-"}`;

    const rerender = () => renderRows(root, rows);
    search.addEventListener("input", rerender);
    sort.addEventListener("change", rerender);
    rerender();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
