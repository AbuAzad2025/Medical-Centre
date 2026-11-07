import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const loadResponse = { success: true, items: [{ department_id: 3, department_name: 'Cardiology', max_queue_size: 10, payment_required: true, emergency_payment_waived: false, force_entry_allowed: true, average_wait_time: 15, allow_partial_payment: false, allow_debt: true }] };

function setupDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table><tbody id="queueSettingsBody"></tbody></table>
    <button id="saveQueueSettingsBtn">Save</button>
  `;
  window.escHtml = (s) => s;
  window.__M0__ = '/api/queue/settings';
  window.__M1__ = '/api/queue/settings/save';
  window.API_ROUTES = {};
  window.notify = { success: vi.fn(), error: vi.fn() };
  window.showToast = vi.fn();
}

beforeEach(async () => {
  setupDom();
  window.__M = [];
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(loadResponse) });
  await loadModule('static/js/pages/super_admin/queue_settings.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('queue_settings.js', () => {
  it('boolSelect renders selected option', async () => {
    const { boolSelect } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(boolSelect(true)).toContain('selected');
    expect(boolSelect(true)).toContain('نعم');
    expect(boolSelect(false)).toContain('لا');
  });

  it('intInput renders value and min/max', async () => {
    const { intInput } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    expect(intInput(5, 1, 10)).toContain('value="5"');
    expect(intInput(5, 1, 10)).toContain('min="1"');
    expect(intInput(null, null, null)).toContain('value=""');
    expect(intInput(null, null, null)).not.toContain('min=');
  });

  it('loadSettings populates a row', async () => {
    const { loadSettings } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    await loadSettings();
    expect(document.querySelectorAll('#queueSettingsBody tr').length).toBe(1);
  });

  it('loadSettings failure shows error row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const { loadSettings } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    await loadSettings();
    expect(document.querySelector('#queueSettingsBody td.text-danger')).toBeTruthy();
  });

  it('loadSettings fetch failure invokes error toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    window.showToast = vi.fn();
    const { loadSettings } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    await loadSettings();
    expect(window.showToast).toHaveBeenCalled();
  });

  it('collectSettings reads row inputs', async () => {
    const { collectSettings } = await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.querySelector('#queueSettingsBody').innerHTML = `<tr data-department-id="3"><td>Cardiology</td><td><input class="form-control form-control-sm" data-type="int" type="number" value="5"></td><td><select class="form-select" data-type="bool"><option value="1" selected>yes</option></select></td><td><select class="form-select" data-type="bool"><option value="0" selected>no</option></select></td><td><select class="form-select" data-type="bool"><option value="1" selected>yes</option></select></td><td><input class="form-control form-control-sm" data-type="int" type="number" value="20"></td><td><select class="form-select" data-type="bool"><option value="0" selected>no</option></select></td><td><select class="form-select" data-type="bool"><option value="1" selected>yes</option></select></td></tr>`;
    const out = collectSettings();
    expect(out.items.length).toBe(1);
    expect(out.items[0].department_id).toBe(3);
  });

  it('DOMContentLoaded triggers loadSettings fetch', async () => {
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('save button posts collected settings and succeeds', async () => {
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveQueueSettingsBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(window.notify.success).toHaveBeenCalled();
  });

  it('save button failure notifies error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/super_admin/queue_settings.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveQueueSettingsBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });
});
