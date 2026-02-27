(function () {
  const KEY = 'xai_expert_limit';
  const MIN = 10;
  const MAX = 1000;
  const DEFAULT = 300;

  function clamp(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return DEFAULT;
    return Math.max(MIN, Math.min(MAX, Math.round(n)));
  }

  function getLimit(fallback = DEFAULT) {
    const raw = localStorage.getItem(KEY);
    if (raw == null || raw === '') return clamp(fallback);
    return clamp(raw);
  }

  function setLimit(v) {
    const n = clamp(v);
    localStorage.setItem(KEY, String(n));
    return n;
  }

  function apply(rows, fallback = DEFAULT) {
    const list = Array.isArray(rows) ? rows : [];
    const limit = getLimit(fallback);
    return list.slice(0, Math.min(limit, list.length));
  }

  window.XAIExpertLimit = {
    KEY,
    MIN,
    MAX,
    DEFAULT,
    clamp,
    getLimit,
    setLimit,
    apply,
  };
})();
