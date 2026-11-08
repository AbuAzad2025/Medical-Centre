import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const METRICS = {
  success: true,
  cpu_percent: 41.2,
  memory_percent: 62.8,
  disk_percent: 55.1,
  uptime_hours: 38.4,
  active_db_connections: 7,
  db_size_mb: 512.5,
  visits_today: 123,
  payments_today: 45,
  payment_amount_today: 9800,
  prescriptions_today: 67,
};

beforeEach(() => {
  document.body.innerHTML = `
    <div id="cpu-usage"></div>
    <div id="memory-usage"></div>
    <div id="disk-usage"></div>
    <div id="uptime"></div>
    <div id="active-db-connections"></div>
    <div id="db-size-mb"></div>
    <div id="visits-today"></div>
    <div id="payments-today"></div>
    <div id="payment-amount-today"></div>
    <div id="prescriptions-today"></div>
  `;
  window.__M = [];
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(METRICS) });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/performance.js', () => {
  it('fetches the metrics endpoint on load and renders them', async () => {
    await loadModule('static/js/pages/super_admin/performance.js');
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch).toHaveBeenCalledWith('/super-admin/api/performance', expect.objectContaining({ credentials: 'same-origin' }));
    expect(document.getElementById('cpu-usage').textContent).toBe('41%');
    expect(document.getElementById('memory-usage').textContent).toBe('63%');
    expect(document.getElementById('db-size-mb').textContent).toBe('512.5');
    expect(document.getElementById('visits-today').textContent).toBe('123');
    expect(document.getElementById('payments-today').textContent).toBe('45');
    expect(document.getElementById('payment-amount-today').textContent).toBe('9800.00');
    expect(document.getElementById('prescriptions-today').textContent).toBe('67');
  });

  it('uses the API_ROUTES.performance_metrics override', async () => {
    window.API_ROUTES = { performance_metrics: '/custom/perf' };
    await loadModule('static/js/pages/super_admin/performance.js');
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/perf');
  });

  it('fetch failure leaves the placeholders untouched', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/performance.js');
    document.getElementById('cpu-usage').textContent = '-';
    await vi.advanceTimersByTimeAsync(10);
    expect(document.getElementById('cpu-usage').textContent).toBe('-');
  });

  it('response without success:true leaves values untouched', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/performance.js');
    await vi.advanceTimersByTimeAsync(10);
    expect(document.getElementById('cpu-usage').textContent).toBe('');
  });

  it('updatePerformanceData is exposed and bound to window', async () => {
    await loadModule('static/js/pages/super_admin/performance.js');
    expect(typeof window.updatePerformanceData).toBe('function');
  });
});
