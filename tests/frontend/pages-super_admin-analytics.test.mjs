import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setupCharts() {
  document.body.innerHTML = `
    <canvas id="usageChart"></canvas>
    <canvas id="userDistributionChart"></canvas>
  `;
  const usage = document.getElementById('usageChart');
  const dist = document.getElementById('userDistributionChart');
  usage.getContext = vi.fn(() => ({}));
  dist.getContext = vi.fn(() => ({}));
}

beforeEach(() => {
  setupCharts();
  window.__M = [];
  window.__M0__ = {
    visits: { labels: ['11-01', '11-02'], data: [4, 7] },
    roles: { labels: ['doctor', 'reception'], data: [12, 34] },
  };
  window.__M1__ = {
    total_users: 100,
    total_patients: 900,
    total_visits: 5000,
    visits_today: 42,
    payments_today: 11,
    payment_amount_today: 1500.5,
    prescriptions_today: 20,
    audit_errors_today: 1,
  };
  window.API_ROUTES = {};
  window.escHtml = (s) => s;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { rtl: false, labels: {} } }, font: {} };
});

afterEach(() => {
  vi.useRealTimers();
  delete window.__M0__;
  delete window.__M1__;
});

describe('analytics.js', () => {
  it('refreshAnalytics is defined', async () => {
    const mod = await loadModule('static/js/pages/super_admin/analytics.js');
    expect(typeof mod.refreshAnalytics).toBe('function');
  });

  it('exportAnalytics exports the real payload as CSV', async () => {
    const mod = await loadModule('static/js/pages/super_admin/analytics.js');
    global.URL.createObjectURL = vi.fn(() => 'blob:x');
    global.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    mod.exportAnalytics();
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it('exportAnalytics works with missing payloads', async () => {
    delete window.__M0__;
    delete window.__M1__;
    const mod = await loadModule('static/js/pages/super_admin/analytics.js');
    global.URL.createObjectURL = vi.fn(() => 'blob:x');
    global.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    expect(() => mod.exportAnalytics()).not.toThrow();
    clickSpy.mockRestore();
  });

  it('renders charts from the passed payload on DOMContentLoaded', async () => {
    // loadModule re-imports per call, so listeners accumulate across tests;
    // assert on the calls triggered by this dispatch instead of an absolute count.
    await loadModule('static/js/pages/super_admin/analytics.js');
    const before = window.Chart.mock.calls.length;
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const newCalls = window.Chart.mock.calls.slice(before);
    expect(newCalls.length).toBeGreaterThanOrEqual(2);
    const lineCall = newCalls.find(c => c[1] && c[1].type === 'line')[1];
    expect(lineCall.data.labels).toEqual(['11-01', '11-02']);
    expect(lineCall.data.datasets[0].data).toEqual([4, 7]);
    const doughnutCall = newCalls.find(c => c[1] && c[1].type === 'doughnut')[1];
    expect(doughnutCall.data.labels).toEqual(['doctor', 'reception']);
    expect(doughnutCall.data.datasets[0].data).toEqual([12, 34]);
  });

  it('tolerates missing payload without throwing', async () => {
    delete window.__M0__;
    await loadModule('static/js/pages/super_admin/analytics.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
  });

  it('does not construct charts when Chart is missing', async () => {
    delete window.Chart;
    await loadModule('static/js/pages/super_admin/analytics.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
  });
});
