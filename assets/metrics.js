(function () {
  const KEY = 'xai_metrics_events_v1';
  const MAX = 1500;

  function nowIso() {
    return new Date().toISOString();
  }

  function getEvents() {
    try {
      const raw = localStorage.getItem(KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  function saveEvents(arr) {
    try {
      localStorage.setItem(KEY, JSON.stringify(arr.slice(-MAX)));
    } catch {
      // ignore quota or privacy mode errors
    }
  }

  function track(type, payload) {
    const events = getEvents();
    events.push({
      type,
      ts: nowIso(),
      path: location.pathname,
      ref: document.referrer || '',
      payload: payload || {},
    });
    saveEvents(events);
  }

  window.XAIMetrics = {
    track,
    read: getEvents,
    clear: function () {
      try { localStorage.removeItem(KEY); } catch {}
    },
    exportJson: function () {
      return JSON.stringify(getEvents(), null, 2);
    },
  };

  document.addEventListener('click', function (e) {
    const el = e.target && e.target.closest ? e.target.closest('a,button') : null;
    if (!el) return;
    const label = (el.getAttribute('data-cta') || el.textContent || '').trim().slice(0, 80);
    const href = el.getAttribute('href') || '';
    track('click', {
      label,
      href,
      id: el.id || '',
      cls: (el.className || '').toString().slice(0, 120),
    });
  }, true);

  track('pageview', {
    title: document.title,
    ua: navigator.userAgent,
  });
})();
