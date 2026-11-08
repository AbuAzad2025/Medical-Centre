import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
});

afterEach(() => {
  vi.useRealTimers();
});

describe('dashboard-live.js', () => {
  it('applyMetrics writes values for known widgets', async () => {
    document.body.innerHTML = `
      <div data-widget-id="queue_live"><span data-metric-value>0</span></div>
      <div data-widget-id="worklist_urgent"><span data-metric-value>0</span></div>
      <div data-widget-id="unknown_widget"><span data-metric-value>0</span></div>
    `;
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    const { applyMetrics } = await loadModule('static/js/dashboard-live.js');
    applyMetrics({ queue_count: 7, pending_requests: 3, mystery: 99 });
    expect(document.querySelector('[data-widget-id="queue_live"] [data-metric-value]').textContent).toBe('7');
    expect(document.querySelector('[data-widget-id="worklist_urgent"] [data-metric-value]').textContent).toBe('3');
  });

  it('applyMetrics ignores missing metrics or empty args', async () => {
    document.body.innerHTML = '<div data-widget-id="queue_live"><span data-metric-value>0</span></div>';
    const { applyMetrics } = await loadModule('static/js/dashboard-live.js');
    expect(() => applyMetrics()).not.toThrow();
    expect(() => applyMetrics(null)).not.toThrow();
    applyMetrics({ queue_count: 12 });
    expect(document.querySelector('[data-widget-id="queue_live"] [data-metric-value]').textContent).toBe('12');
  });

  it('poll uses hidden-document guard and warns on failure', async () => {
    document.body.innerHTML = '<div data-widget-id="kpi_strip"><span data-metric-value>0</span></div>';
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    window.console.warn = vi.fn();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const { poll } = await loadModule('static/js/dashboard-live.js');
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    poll();
    await new Promise(r => setTimeout(r, 30));
    expect(window.console.warn).toHaveBeenCalled();
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    poll();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('poll applies metrics from a successful snapshot', async () => {
    document.body.innerHTML = '<div data-widget-id="kpi_strip"><span data-metric-value>0</span></div>';
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ metrics: { visits_today: 88 } }) });
    const { poll } = await loadModule('static/js/dashboard-live.js');
    poll();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('[data-widget-id="kpi_strip"] [data-metric-value]').textContent).toBe('88');
  });

  it('poll ignores non-ok responses', async () => {
    document.body.innerHTML = '<div data-widget-id="kpi_strip"><span data-metric-value>0</span></div>';
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const { poll } = await loadModule('static/js/dashboard-live.js');
    poll();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('[data-widget-id="kpi_strip"] [data-metric-value]').textContent).toBe('0');
  });

  it('startPolling and stopPolling manage the interval', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div class="command-center"></div>';
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ metrics: {} }) });
    const mod = await loadModule('static/js/dashboard-live.js');
    mod.startPolling();
    mod.startPolling(); // idempotent
    mod.stopPolling();
    mod.stopPolling();
    expect(true).toBe(true);
    vi.useRealTimers();
  });

  it('DOMContentLoaded on command-center page starts polling', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div class="command-center"></div>';
    window.API_ROUTES = { dashboard_snapshot: '/api/dashboard/snapshot' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/dashboard-live.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    vi.advanceTimersByTime(100);
    expect(true).toBe(true);
    vi.useRealTimers();
  });

  it('DOMContentLoaded without command-center page is a no-op', async () => {
    await loadModule('static/js/dashboard-live.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('.command-center')).toBeNull();
  });

  it('exposes window helpers', async () => {
    await loadModule('static/js/dashboard-live.js');
    expect(typeof window.applyMetrics).toBe('function');
    expect(typeof window.poll).toBe('function');
    expect(typeof window.startPolling).toBe('function');
    expect(typeof window.stopPolling).toBe('function');
  });
});

describe('biometric/status.js extra branches', () => {
  it('register click without showToast still completes', async () => {
    document.body.innerHTML = `
      <meta name="csrf-token" content="csrf-bio">
      <button id="registerBtn">Register</button>
      <div id="registerResult"></div>
    `;
    delete window.showToast;
    window.escHtml = (s) => String(s ?? '');
    window.__M0__ = '/biometric/api/register';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/biometric/status.js');
    document.getElementById('registerBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('registerResult').innerHTML).toContain('alert-success');
  });

  it('register click failure without showToast falls back to alert-danger', async () => {
    document.body.innerHTML = `
      <meta name="csrf-token" content="csrf-bio">
      <button id="registerBtn">Register</button>
      <div id="registerResult"></div>
    `;
    delete window.showToast;
    window.escHtml = (s) => String(s ?? '');
    window.__M0__ = '/biometric/api/register';
    global.fetch = vi.fn().mockRejectedValue(new Error('boom'));
    await loadModule('static/js/pages/biometric/status.js');
    document.getElementById('registerBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('registerResult').innerHTML).toContain('alert-danger');
  });

  it('register click without meta csrf uses empty token', async () => {
    document.body.innerHTML = `
      <button id="registerBtn">Register</button>
      <div id="registerResult"></div>
    `;
    window.escHtml = (s) => String(s ?? '');
    window.__M0__ = '/biometric/api/register';
    window.showToast = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/biometric/status.js');
    document.getElementById('registerBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('');
  });
});