import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <select id="auto_cleanup"><option value="true">نعم</option><option value="false" selected>لا</option></select>
    <input id="cleanup_days" type="number" value="45">
    <input id="log_retention_days" type="number" value="120">
    <select id="auto_backup"><option value="true">نعم</option><option value="false" selected>لا</option></select>
    <button id="saveAutomation">Save</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/system/automation';
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.alert = vi.fn();
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('maintenance_automation.js', () => {
  it('save click posts payload', async () => {
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/system/automation', expect.objectContaining({ method: 'POST' }));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.cleanup_days).toBe(45);
    expect(body.log_retention_days).toBe(120);
    expect(body.auto_cleanup).toBe(false);
  });

  it('save success shows alert', async () => {
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('save server failure shows generic alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('save non-ok status shows generic error via showToast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch failure with showToast shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch failure without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('without save button nothing is wired', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    expect(global.fetch).not.toHaveBeenCalled();
  });
});