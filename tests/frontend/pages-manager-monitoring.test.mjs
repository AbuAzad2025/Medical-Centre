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
  window.__M0__ = {
    reception: { name: 'الاستقبال', status: 'active', pending_visits: 5 },
    doctor: { name: 'الأطباء', status: 'active', in_progress_visits: 3 },
    emergency: { name: 'الطوارئ', status: 'active', emergency_visits: 2 },
    lab: { name: 'المختبر', status: 'active', lab_requests: 25 },
    radiology: { name: 'الأشعة', status: 'active', radiology_requests: 41 },
    accountant: { name: 'المحاسب', status: 'active', open_invoices: 7 },
  };
  window.__M7__ = { cpu_percent: 32, memory_percent: 61, disk_percent: 48, uptime_hours: 12 };
  window.API_ROUTES = {};
  window.location = { reload: vi.fn() };
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
  vi.restoreAllMocks();
});

describe('monitoring.js', () => {
  it('refreshMonitoring reloads the page', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.refreshMonitoring();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('exportMonitoringReport creates a CSV link with real data', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    global.URL.createObjectURL = vi.fn(() => 'blob:x');
    global.URL.revokeObjectURL = vi.fn();
    mod.exportMonitoringReport();
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  it('exportMonitoringReport works with missing payloads', async () => {
    delete window.__M0__;
    delete window.__M7__;
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    global.URL.createObjectURL = vi.fn(() => 'blob:x');
    global.URL.revokeObjectURL = vi.fn();
    expect(() => mod.exportMonitoringReport()).not.toThrow();
  });

  it('viewUnitDetails shows real unit stats for a known key', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.viewUnitDetails('lab');
    const args = window.Swal.fire.mock.calls[0][0];
    expect(args.title).toBe('المختبر');
    expect(args.html).toContain('25');
    expect(args.html).toContain('نشطة');
  });

  it('viewUnitDetails with unknown key shows a gentle message instead of fake values', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.viewUnitDetails('spaceship');
    expect(window.Swal.fire).toHaveBeenCalledWith(expect.objectContaining({ title: 'تفاصيل الوحدة' }));
  });

  it('refreshUnit reloads the page', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.refreshUnit('lab');
    expect(window.location.reload).toHaveBeenCalled();
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

  it('updateUnitStatus emergency warning threshold', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ emergency: { emergency_visits: 10, status: 'active' } });
    expect(document.getElementById('badge-emergency-status').className).toContain('bg-warning');
    mod.updateUnitStatus({ emergency: { emergency_visits: 20, status: 'active' } });
    expect(document.getElementById('badge-emergency-status').className).toContain('bg-danger');
  });
});
