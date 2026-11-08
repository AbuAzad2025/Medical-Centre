import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <select id="auto_cleanup"><option value="true">true</option><option value="false">false</option></select>
    <input id="cleanup_days" value="45">
    <input id="log_retention_days" value="120">
    <select id="auto_backup"><option value="true">true</option><option value="false">false</option></select>
    <button id="saveAutomation">Save</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/maintenance/automation';
  window.escHtml = (s) => String(s ?? '');
  window.alert = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('maintenance_automation.js payload branches', () => {
  it('empty day fields fall back to 30 and 90', async () => {
    document.getElementById('cleanup_days').value = '';
    document.getElementById('log_retention_days').value = '';
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.cleanup_days).toBe(30);
    expect(body.log_retention_days).toBe(90);
  });

  it('true selects send boolean true in the payload', async () => {
    document.getElementById('auto_cleanup').value = 'true';
    document.getElementById('auto_backup').value = 'true';
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.auto_cleanup).toBe(true);
    expect(body.auto_backup).toBe(true);
  });

  it('save without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('window.__M preset leaves no crash on module load', async () => {
    await expect(loadModule('static/js/pages/super_admin/maintenance_automation.js')).resolves.toBeDefined();
  });

  it('success:false with r.ok true shows the generic alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/maintenance_automation.js');
    document.getElementById('saveAutomation').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalledWith('تعذر الحفظ');
  });
});
