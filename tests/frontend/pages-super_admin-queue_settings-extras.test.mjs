import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table><tbody id="queueSettingsBody"></tbody></table>
    <button id="saveQueueSettingsBtn">Save</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/queue-settings';
  window.__M1__ = '/api/queue-settings/save';
  window.__M2__ = '/api/unused';
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.notify = { error: vi.fn(), success: vi.fn() };
  window.showToast = vi.fn();
  window.alert = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 3, department_name: 'العيادات', max_queue_size: 20, payment_required: true, emergency_payment_waived: false, force_entry_allowed: true, average_wait_time: 15, allow_partial_payment: false, allow_debt: true }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('queue_settings.js boolSelect/intInput arms', () => {
  it('boolSelect with false renders the zero option selected', async () => {
    const { boolSelect } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    const html = boolSelect(false);
    expect(html).toContain('value="0" selected');
    expect(html).toContain('value="1"');
  });

  it('intInput with null/undefined value renders an empty input', async () => {
    const { intInput } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(intInput(null, 1, 10)).toContain('value=""');
    expect(intInput(undefined, null, null)).toContain('value=""');
    expect(intInput(undefined, null, null)).not.toContain('min=');
  });

  it('intInput omits min and max when not provided', async () => {
    const { intInput } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(intInput(5, null, null)).toContain('value="5"');
    expect(intInput(5, null, null)).not.toContain('min=');
    expect(intInput(5, null, null)).not.toContain('max=');
  });

  it('intInput renders numeric min/max when provided', async () => {
    const { intInput } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(intInput(5, 1, 999)).toContain('min="1"');
    expect(intInput(5, 1, 999)).toContain('max="999"');
  });

  it('boolSelect with true value renders the one option selected', async () => {
    const { boolSelect } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(boolSelect(true)).toContain('value="1" selected');
  });
});

describe('queue_settings.js loadSettings arms', () => {
  it('response without items renders the empty table row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('queueSettingsBody').innerHTML).toContain('لا بيانات');
  });

  it('response with success:false shows the failure row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('queueSettingsBody').innerHTML).toContain('فشل التحميل');
  });

  it('fetch failure without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 40));
    expect(window.alert).toHaveBeenCalled();
  });

  it('row without department_name falls back to the department id', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 77, max_queue_size: 5 }] }) });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('queueSettingsBody').innerHTML).toContain('77');
  });

  it('items key non-array renders the empty row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: 'nope' }) });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('queueSettingsBody').innerHTML).toContain('لا بيانات');
  });
});

describe('queue_settings.js collectSettings arms', () => {
  it('row missing int inputs falls back to the default limits', async () => {
    const mod = await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.getElementById('queueSettingsBody').innerHTML = `
      <tr data-department-id="5">
        <td>اسم</td>
        <td></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="0"><option value="1">نعم</option><option value="0" selected>لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
        <td></td>
        <td><select class="form-select" data-type="bool" value="0"><option value="1">نعم</option><option value="0" selected>لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
      </tr>`;
    const { items } = mod.collectSettings();
    expect(items[0].max_queue_size).toBe(50);
    expect(items[0].average_wait_time).toBe(30);
    expect(items[0].payment_required).toBe(true);
    expect(items[0].allow_debt).toBe(true);
  });
});

describe('queue_settings.js save button arms', () => {
  function seedRow() {
    document.getElementById('queueSettingsBody').innerHTML = `
      <tr data-department-id="3">
        <td class="ps-3 fw-semibold">العيادات</td>
        <td><input class="form-control" data-type="int" type="number" value="25"></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="0"><option value="1">نعم</option><option value="0" selected>لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
        <td><input class="form-control" data-type="int" type="number" value="20"></td>
        <td><select class="form-select" data-type="bool" value="0"><option value="1">نعم</option><option value="0" selected>لا</option></select></td>
        <td><select class="form-select" data-type="bool" value="1"><option value="1" selected>نعم</option><option value="0">لا</option></select></td>
      </tr>`;
  }

  it('save success reloads settings and notifies success', async () => {
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    seedRow();
    document.getElementById('saveQueueSettingsBtn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.success).toHaveBeenCalled();
    expect(global.fetch.mock.calls.filter(c => String(c[0]).includes('save')).length).toBe(1);
  });

  it('save non-ok without window.notify responds silently', async () => {
    delete window.notify;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    seedRow();
    expect(() => document.getElementById('saveQueueSettingsBtn').click()).not.toThrow();
    await new Promise(r => setTimeout(r, 40));
  });

  it('save server failure without window.notify responds silently', async () => {
    delete window.notify;
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    seedRow();
    expect(() => document.getElementById('saveQueueSettingsBtn').click()).not.toThrow();
    await new Promise(r => setTimeout(r, 40));
  });

  it('save network failure without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    seedRow();
    document.getElementById('saveQueueSettingsBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(window.alert).toHaveBeenCalled();
  });

  it('save without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    seedRow();
    document.getElementById('saveQueueSettingsBtn').click();
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('save'));
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('missing save button element does not crash the module', async () => {
    document.getElementById('saveQueueSettingsBtn').remove();
    await expect(loadModule('static/js/pages/super_admin/queue_settings.js')).resolves.toBeDefined();
  });
});
