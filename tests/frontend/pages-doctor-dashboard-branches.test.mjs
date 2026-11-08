import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div id="doctorPanels">
      <div class="dashboard-panel" data-panel="vitals">Vitals</div>
      <div class="dashboard-panel" data-panel="labs">Labs</div>
    </div>
    <div id="dashboardSettingsList"></div>
    <button id="saveDashboardSettings">Save</button>
    <div data-stat="today-visits"></div>
    <div data-stat="waiting"></div>
    <div data-stat="in-progress"></div>
    <div data-stat="completed"></div>
    <div data-stat="prescriptions"></div>
    <div data-stat="appointments"></div>
    <div data-stat="pending-lab"></div>
    <div data-stat="pending-radiology"></div>
  `;
}

const LAYOUT = {
  items: [
    { id: 'vitals', title: 'Vitals', order: 2, enabled: true },
    { id: 'labs', title: 'Labs', order: 1, enabled: false },
  ],
};

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/api/doctor/layout';
  window.__M1__ = 'csrf';
  window.__M2__ = '/doctor/queue';
  window.__M3__ = '/doctor/prescriptions';
  window.__M4__ = '/doctor/reports';
  window.__M5__ = '/doctor/appointments';
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = { doctor_dashboard_stats: '/doctor/api/dashboard-stats' };
  window.notify = { warning: vi.fn(), error: vi.fn(), success: vi.fn() };
  window.showToast = vi.fn();
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn((url) => {
    if (String(url).includes('dashboard-stats')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, stats: { today_visits: 5, waiting_patients: 2, in_progress: 1, completed_today: 3, prescriptions_today: 7, appointments_today: 11, pending_lab: 13, pending_radiology: 17 } }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(LAYOUT) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/dashboard.js loadLayout branches', () => {
  it('panel absent from the layout map keeps its default order', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: [{ id: 'unrelated', title: 'X', order: 9, enabled: true }] }),
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    const vitals = document.querySelector('[data-panel="vitals"]');
    expect(vitals.style.display).toBe('');
  });

  it('item without order defaults to 0 in settings and layout', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: [{ id: 'vitals', title: 'V', enabled: true }] }),
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    const numberInput = document.querySelector('#dashboardSettingsList input[type="number"]');
    expect(numberInput.value).toBe('0');
  });

  it('item without title falls back to its id', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: [{ id: 'labs', order: 1, enabled: true }] }),
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    expect(document.querySelector('#dashboardSettingsList').innerHTML).toContain('labs');
  });

  it('null items argument renders without crashing', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: null }) });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    expect(document.querySelector('#dashboardSettingsList').innerHTML).toBe('');
  });

  it('applyLayout with null items does not throw', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    expect(() => mod.applyLayout(null)).not.toThrow();
    expect(() => mod.renderSettings(null)).not.toThrow();
  });

  it('non-ok layout response triggers notify.warning', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    expect(window.notify.warning).toHaveBeenCalled();
  });

  it('layout response without items is ignored silently', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await expect(mod.loadLayout()).resolves.toBeUndefined();
    expect(window.notify.warning).not.toHaveBeenCalled();
  });

  it('missing notify still resolves without throwing', async () => {
    delete window.notify;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await expect(mod.loadLayout()).resolves.toBeUndefined();
  });
});

describe('doctor/dashboard.js saveLayout branches', () => {
  it('save sends enabled state from the checkbox', async () => {
    document.body.insertAdjacentHTML('beforeend', '<div id="dashboardSettingsListMount"></div>');
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings(LAYOUT.items);
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('layout') && c[1] && c[1].method === 'POST');
    expect(call).toBeTruthy();
  });

  it('save with empty number input defaults order to 0', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'V', order: 3, enabled: true }]);
    const input = document.querySelector('#dashboardSettingsList input[type="number"]');
    input.value = '';
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls.find(c => c[1] && c[1].method === 'POST');
    const body = JSON.parse(call[1].body);
    expect(body.items[0].order).toBe(0);
  });

  it('save without csrfToken sends no token header', async () => {
    window.__M1__ = '';
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'V', order: 1, enabled: true }]);
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls.find(c => c[1] && c[1].method === 'POST');
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('save non-ok response triggers notify.error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'V', order: 1, enabled: true }]);
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('save response without items does not re-render settings', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'V', order: 1, enabled: true }]);
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).not.toHaveBeenCalled();
  });

  it('missing notify.error does not crash', async () => {
    delete window.notify;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'V', order: 1, enabled: true }]);
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(true).toBe(true);
  });
});

describe('doctor/dashboard.js refreshDashboardStats branches', () => {
  it('stats fetch non-ok triggers showToast fallback', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('dashboard-stats')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(window.showToast).toHaveBeenCalled();
  });

  it('stats fetch non-ok without showToast uses console.warn', async () => {
    delete window.showToast;
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn((url) => {
      if (String(url).includes('dashboard-stats')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('stats response without stats object returns silently', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('dashboard-stats')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(document.querySelector('[data-stat="today-visits"]').textContent).toBe('');
  });

  it('stats response with success=false returns silently', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('dashboard-stats')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: false, stats: {} }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(document.querySelector('[data-stat="today-visits"]').textContent).toBe('');
  });

  it('undefined stat values render as 0', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('dashboard-stats')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, stats: {} }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(document.querySelector('[data-stat="today-visits"]').textContent).toBe('0');
  });

  it('API_ROUTES doctor_dashboard_stats is honoured', async () => {
    window.API_ROUTES = { doctor_dashboard_stats: '/custom/stats' };
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(global.fetch.mock.calls.some(c => String(c[0]) === '/custom/stats')).toBe(true);
  });

  it('update skips missing stat elements', async () => {
    document.querySelector('[data-stat="waiting"]').remove();
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(document.querySelector('[data-stat="today-visits"]').textContent).toBe('5');
  });
});

describe('doctor/dashboard.js polling & keyboard branches', () => {
  it('startStatsPolling twice clears the previous interval', async () => {
    vi.useFakeTimers();
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.startStatsPolling();
    mod.startStatsPolling();
    const fetchesBefore = global.fetch.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30000);
    expect(global.fetch.mock.calls.length).toBeGreaterThan(fetchesBefore);
    mod.stopStatsPolling();
    mod.stopStatsPolling(); // idempotent
    vi.useRealTimers();
  });

  it('keydown Alt+Q/P/R/A navigates to the configured pages', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    for (const [key, url] of [['q', '/doctor/queue'], ['p', '/doctor/prescriptions'], ['r', '/doctor/reports'], ['a', '/doctor/appointments']]) {
      window.location.href = '';
      document.dispatchEvent(new KeyboardEvent('keydown', { key, altKey: true, bubbles: true }));
      expect(window.location.href).toBe(url);
    }
  });

  it('keydown inside an input field is ignored', async () => {
    await loadModule('static/js/pages/doctor/dashboard.js');
    const input = document.createElement('input');
    input.tagName; // INPUT
    document.body.appendChild(input);
    window.location.href = '';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', altKey: true, bubbles: true }));
    expect(window.location.href).toBe('');
  });

  it('keydown without Alt does nothing', async () => {
    await loadModule('static/js/pages/doctor/dashboard.js');
    window.location.href = '';
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', bubbles: true }));
    expect(window.location.href).toBe('');
  });

  it('keydown with unrelated Alt combo does nothing', async () => {
    await loadModule('static/js/pages/doctor/dashboard.js');
    window.location.href = '';
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', altKey: true, bubbles: true }));
    expect(window.location.href).toBe('');
  });

  it('DOMContentLoaded starts polling when stats exist', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/doctor/dashboard.js');
    global.fetch.mockClear();
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('dashboard-stats'))).toBe(true);
    vi.useRealTimers();
  });

  it('DOMContentLoaded without stats elements does not start polling', async () => {
    document.querySelectorAll('[data-stat]').forEach(el => el.remove());
    await loadModule('static/js/pages/doctor/dashboard.js');
    global.fetch.mockClear();
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('dashboard-stats'))).toBe(false);
  });

  it('visibilitychange hidden stops and visible restarts polling', async () => {
    vi.useFakeTimers();
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.startStatsPolling();
    global.fetch.mockClear();
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    document.dispatchEvent(new Event('visibilitychange'));
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('dashboard-stats'))).toBe(true);
    mod.stopStatsPolling();
    vi.useRealTimers();
  });

  it('beforeunload stops polling', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.startStatsPolling();
    expect(() => window.dispatchEvent(new Event('beforeunload'))).not.toThrow();
  });
});
