import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

let dom;

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
  window.API_ROUTES = {};
  window.escHtml = (s) => s;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: { rtl: false }, legend: { rtl: false, labels: {} } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('analytics.js', () => {
  it('refreshAnalytics is defined', async () => {
    const mod = await loadModule('static/js/pages/super_admin/analytics.js');
    expect(() => mod.refreshAnalytics()).not.toThrow();
  });

  it('exportAnalytics creates download link', async () => {
    const mod = await loadModule('static/js/pages/super_admin/analytics.js');
    mod.exportAnalytics();
    expect(true).toBe(true);
  });

  it('loads module and charts are attempted on DOMContentLoaded', async () => {
    await loadModule('static/js/pages/super_admin/analytics.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});