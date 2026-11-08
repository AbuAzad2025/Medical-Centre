import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <span id="stat-lab-lab_requests">0</span>
    <span id="badge-lab-status" class="badge bg-secondary">?</span>
    <span id="stat-radiology-radiology_requests">0</span>
    <span id="badge-radiology-status" class="badge bg-secondary">?</span>
    <span id="stat-emergency-emergency_visits">0</span>
    <span id="badge-emergency-status" class="badge bg-secondary">?</span>
    <span id="stat-reception-pending_visits">0</span>
    <span id="badge-reception-status" class="badge bg-secondary">?</span>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = { reception: {}, doctor: {}, emergency: {}, lab: {}, radiology: {}, accountant: {} };
  window.__M1__ = 10;
  window.__M2__ = 20;
  window.__M3__ = 30;
  window.__M4__ = 40;
  window.__M5__ = 50;
  window.__M6__ = 60;
  window.__M7__ = '/api/monitoring';
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, units_status: {} }) });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('monitoring.js updateUnitStatus threshold branches', () => {
  it('lab above 40 requests marks the badge danger', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ lab: { status: 'active', lab_requests: 45 } });
    expect(document.getElementById('badge-lab-status').className).toBe('badge bg-danger');
    expect(document.getElementById('badge-lab-status').textContent).toBe('نشط');
  });

  it('lab above 20 requests marks the badge warning', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ lab: { status: 'active', lab_requests: 25 } });
    expect(document.getElementById('badge-lab-status').className).toBe('badge bg-warning');
  });

  it('radiology above 40 requests marks the badge danger', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ radiology: { status: 'active', radiology_requests: 45 } });
    expect(document.getElementById('badge-radiology-status').className).toBe('badge bg-danger');
  });

  it('radiology above 20 requests marks the badge warning', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ radiology: { status: 'active', radiology_requests: 25 } });
    expect(document.getElementById('badge-radiology-status').className).toBe('badge bg-warning');
  });

  it('emergency above 15 visits marks the badge danger', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ emergency: { status: 'active', emergency_visits: 20 } });
    expect(document.getElementById('badge-emergency-status').className).toBe('badge bg-danger');
  });

  it('emergency above 8 visits marks the badge warning', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ emergency: { status: 'active', emergency_visits: 10 } });
    expect(document.getElementById('badge-emergency-status').className).toBe('badge bg-warning');
  });

  it('inactive unit renders danger badge with inactive text', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ lab: { status: 'inactive', lab_requests: 100 } });
    expect(document.getElementById('badge-lab-status').className).toBe('badge bg-danger');
    expect(document.getElementById('badge-lab-status').textContent).toBe('معطل');
  });

  it('unknown unit key is silently skipped', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    expect(() => mod.updateUnitStatus({ unknown_unit: { status: 'active' } })).not.toThrow();
  });

  it('unit with missing counter renders zero', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ reception: { status: 'active' } });
    expect(document.getElementById('stat-reception-pending_visits').textContent).toBe('0');
  });

  it('badge without missing stat element still updates text', async () => {
    document.getElementById('stat-lab-lab_requests').remove();
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    expect(() => mod.updateUnitStatus({ lab: { status: 'active', lab_requests: 1 } })).not.toThrow();
    expect(document.getElementById('badge-lab-status').className).toContain('bg-success');
  });

  it('stat without a badge element does not crash', async () => {
    document.getElementById('badge-lab-status').remove();
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.updateUnitStatus({ lab: { status: 'active', lab_requests: 1 } });
    expect(document.getElementById('stat-lab-lab_requests').textContent).toBe('1');
  });
});

describe('monitoring.js report and teardown arms', () => {
  it('report without any of the __M1__..__M6__ counters defaults them to zero', async () => {
    window.__M1__ = undefined;
    window.__M2__ = undefined;
    window.__M3__ = undefined;
    window.__M4__ = undefined;
    window.__M5__ = undefined;
    window.__M6__ = undefined;
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    expect(() => mod.exportMonitoringReport()).not.toThrow();
  });

  it('refreshMonitoring reloads the page', async () => {
    const mod = await loadModule('static/js/pages/manager/monitoring.js');
    mod.refreshMonitoring();
    expect(window.location.reload).toHaveBeenCalled();
  });
});
