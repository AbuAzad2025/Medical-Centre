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

beforeEach(() => {
  baseDom();
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
  const data = {
    items: [
      { id: 'vitals', title: 'Vitals', order: 1, enabled: true },
      { id: 'labs', title: 'Labs', order: 2, enabled: false },
    ],
    success: true,
    stats: { today_visits: 5, waiting_patients: 3, in_progress: 2, completed_today: 1, prescriptions_today: 4, appointments_today: 2, pending_lab: 1, pending_radiology: 0 },
  };
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(data) }));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/dashboard.js', () => {
  it('applyLayout orders and hides panels', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.applyLayout([{ id: 'vitals', order: 1, enabled: true }, { id: 'labs', order: 2, enabled: false }]);
    const vitals = document.querySelector('[data-panel="vitals"]');
    const labs = document.querySelector('[data-panel="labs"]');
    expect(vitals.style.order).toBe('1');
    expect(labs.style.display).toBe('none');
  });

  it('renderSettings renders rows sorted by order', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'b', title: 'Bee', order: 2, enabled: true }, { id: 'a', title: 'Aye', order: 1, enabled: false }]);
    const rows = document.querySelectorAll('#dashboardSettingsList > div');
    expect(rows.length).toBe(2);
    expect(rows[0].querySelector('label').textContent).toBe('Aye');
  });

  it('loadLayout fetches and applies', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    expect(global.fetch).toHaveBeenCalledWith('/api/doctor/layout', expect.objectContaining({ credentials: 'same-origin' }));
    expect(document.querySelector('[data-panel="labs"]').style.display).toBe('none');
  });

  it('loadLayout failure shows warning toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.loadLayout();
    expect(window.notify.warning).toHaveBeenCalled();
  });

  it('saveLayout gathers panel config and posts it', async () => {
    document.body.innerHTML = `
      <div id="doctorPanels">
        <div class="dashboard-panel" data-panel="vitals">Vitals</div>
        <div class="dashboard-panel" data-panel="labs">Labs</div>
      </div>
      <div id="dashboardSettingsList"></div>
      <button id="saveDashboardSettings">Save</button>
    `;
    window.__M0__ = '/api/doctor/layout';
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    mod.renderSettings([{ id: 'vitals', title: 'Vitals', order: 1, enabled: true }]);
    await mod.saveLayout();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    const [url, opts] = global.fetch.mock.calls[0];
    expect(String(url)).toContain('/api/doctor/layout');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body).items[0].id).toBe('vitals');
  });

  it('saveLayout failure shows error toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    document.getElementById('dashboardSettingsList').innerHTML = '<input type="number" data-panel="vitals" value="1"><input type="checkbox" id="panel_vitals" checked>';
    await mod.saveLayout();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('refreshDashboardStats updates stat elements', async () => {
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(document.querySelector('[data-stat="today-visits"]').textContent).toBe('5');
    expect(document.querySelector('[data-stat="waiting"]').textContent).toBe('3');
    expect(document.querySelector('[data-stat="pending-radiology"]').textContent).toBe('0');
  });

  it('refreshDashboardStats failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    await mod.refreshDashboardStats();
    expect(window.showToast).toHaveBeenCalled();
  });

  it('startStatsPolling and stopStatsPolling do not throw', async () => {
    vi.useFakeTimers();
    const mod = await loadModule('static/js/pages/doctor/dashboard.js');
    expect(() => mod.startStatsPolling()).not.toThrow();
    mod.stopStatsPolling();
    vi.useRealTimers();
  });

  it('saveDashboardSettings button triggers saveLayout', async () => {
    await loadModule('static/js/pages/doctor/dashboard.js');
    document.getElementById('saveDashboardSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('keydown alt+q navigates to queue shortcut', async () => {
    await loadModule('static/js/pages/doctor/dashboard.js');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', altKey: true }));
    expect(window.location.href).toBe('/doctor/queue');
  });

  it('keydown in input does not navigate', async () => {
    const input = document.createElement('input');
    document.body.appendChild(input);
    await loadModule('static/js/pages/doctor/dashboard.js');
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', altKey: true, bubbles: true }));
    expect(window.location.href).not.toBe('/doctor/queue');
  });
});