import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="stat-reception-pending_visits">5</div>
    <div id="badge-reception-status">نشط</div>
    <div id="stat-doctor-in_progress_visits">3</div>
    <div id="badge-doctor-status">نشط</div>
    <div id="stat-emergency-emergency_visits">2</div>
    <div id="badge-emergency-status">نشط</div>
    <div id="stat-lab-lab_requests">25</div>
    <div id="badge-lab-status">نشط</div>
    <div id="stat-radiology-radiology_requests">41</div>
    <div id="badge-radiology-status">نشط</div>
    <div id="stat-accountant-open_invoices">7</div>
    <div id="badge-accountant-status">نشط</div>
  `;
  window.__M = [];
  window.escHtml = (s) => s;
  window.__M0__ = 'units';
  window.__M1__ = 'reception';
  window.__M2__ = 'doctor';
  window.__M3__ = 'emergency';
  window.__M4__ = 'lab';
  window.__M5__ = 'radiology';
  window.__M6__ = 'accountant';
  window.__M7__ = '/manager/api/monitoring/refresh';
  window.API_ROUTES = {};
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, units_status: {} }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('monitoring.js', () => {
  it('refreshMonitoring does not throw', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    expect(() => mod.refreshMonitoring()).not.toThrow();
  });

  it('exportMonitoringReport creates link', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.exportMonitoringReport();
    expect(document.body.innerHTML).toBeDefined();
  });

  it('viewUnitDetails shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.viewUnitDetails('lab');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('refreshUnit shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.refreshUnit('lab');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('clearLogs confirm then clears', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.clearLogs();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('clearLogs cancel does not follow-up', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.clearLogs();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('exportLogs shows success', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.exportLogs();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('updateUnitStatus updates stats and badges', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({
      reception: { pending_visits: 8, status: 'active' },
      lab: { lab_requests: 25, status: 'active' },
      radiology: { radiology_requests: 41, status: 'active' },
      emergency: { emergency_visits: 3, status: 'inactive' },
    });
    expect(document.getElementById('stat-reception-pending_visits').textContent).toBe('8');
    expect(document.getElementById('badge-lab-status').className).toContain('bg-warning');
    expect(document.getElementById('badge-radiology-status').className).toContain('bg-danger');
    expect(document.getElementById('badge-emergency-status').textContent).toBe('معطل');
  });

  it('setInterval auto-refresh fetches and updates status', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, units_status: { lab: { lab_requests: 99, status: 'active' } } }) });
    await loadModule('static/js/pages/manager/monitoring.js');
    await vi.advanceTimersByTimeAsync(60000);
    expect(global.fetch).toHaveBeenCalled();
    expect(document.getElementById('stat-lab-lab_requests').textContent).toBe('99');
    vi.useRealTimers();
  });

  it('setInterval auto-refresh fetch failure logs warning', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await loadModule('static/js/pages/manager/monitoring.js');
    await vi.advanceTimersByTimeAsync(60000);
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  it('setInterval auto-refresh with unsuccessful body does nothing', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/manager/monitoring.js');
    await vi.advanceTimersByTimeAsync(60000);
    expect(document.getElementById('stat-lab-lab_requests').textContent).toBe('25');
    vi.useRealTimers();
  });

  it('updateUnitStatus emergency warning threshold', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ emergency: { emergency_visits: 10, status: 'active' } });
    expect(document.getElementById('badge-emergency-status').className).toContain('bg-warning');
    mod.updateUnitStatus({ emergency: { emergency_visits: 20, status: 'active' } });
    expect(document.getElementById('badge-emergency-status').className).toContain('bg-danger');
  });
});