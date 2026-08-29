(function () {
  'use strict';

  const ENDPOINT = (window.API_ROUTES && window.API_ROUTES.dashboard_snapshot) || '/api/dashboard/snapshot';

  const METRIC_MAP = {
    queue_live: 'queue_count',
    my_queue: 'waiting_patients',
    patients_waiting: 'waiting_patients',
    cash_summary: 'visits_today',
    worklist_urgent: 'pending_requests',
    critical_count: 'critical_count',
    triage_board: 'active_cases',
    pending_payments: 'pending_invoices',
    kpi_strip: 'visits_today',
  };

  const INTERVAL_MS = 20000;
  let intervalId = null;

  function applyMetrics(metrics) {
    if (!metrics) return;
    document.querySelectorAll('[data-widget-id]').forEach((el) => {
      const id = el.dataset.widgetId;
      const key = METRIC_MAP[id];
      if (!key || metrics[key] === undefined) return;
      const target = el.querySelector('[data-metric-value]');
      if (target) target.textContent = metrics[key];
    });
  }

  function poll() {
    if (document.hidden) return;
    fetch(ENDPOINT, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data && data.metrics) applyMetrics(data.metrics); })
      .catch(() => { console.warn('تعذر تحديث المؤشرات الحية'); });
  }

  function startPolling() {
    if (intervalId) return;
    intervalId = setInterval(poll, INTERVAL_MS);
  }

  function stopPolling() {
    if (intervalId) { clearInterval(intervalId); intervalId = null; }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('.command-center')) return;
    poll();
    startPolling();
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { stopPolling(); } else { poll(); startPolling(); }
    });
  });
})();
