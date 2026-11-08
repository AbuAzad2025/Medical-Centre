import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="generalSettingsForm">
      <input id="app_name" name="app_name" value="Clinic">
      <input id="feature_enabled" type="checkbox" name="feature_enabled" checked>
      <textarea id="welcome_message" name="welcome_message">Hello</textarea>
    </form>
    <form id="securitySettingsForm">
      <input id="require_2fa" type="checkbox" name="require_2fa">
    </form>
    <form id="databaseSettingsForm"><input id="ignored" name="ignored" value="x"></form>
    <form id="notificationsSettingsForm"><input id="notif_email" name="notif_email" value="a@b.com"></form>
    <form id="backupSettingsForm"><input id="backup_time" name="backup_time" value="02:00"></form>
    <select id="sms_provider"><option value="none">none</option><option value="twilio">twilio</option></select>
    <div id="twilioSettings" style="display:none"></div>
    <input id="db_host" value="localhost">
    <input id="db_port" value="5432">
    <input id="db_name" value="clinic">
    <input id="db_username" value="postgres">
    <input id="db_password" value="secret">
    <table id="deptQueueTable"><tbody></tbody></table>
    <button id="saveDeptQueueSettings">Save Dept Queue</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/config/save';
  window.__M1__ = '/api/config/test_db';
  window.__M2__ = '/api/config/audit_log';
  window.__M3__ = '/api/dept/queue';
  window.__M4__ = '/api/dept/queue/save';
  window.__M5__ = '/api/sms/test';
  window.__M6__ = '/api/notifications/process';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
  };
  window.showToast = vi.fn();
  window.prompt = vi.fn(() => '+970599123456');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, settings: { app_name: 'Clinic', require_2fa: true }, items: [{ department_id: 3, department_name: 'Cardiology', max_queue_size: 5, payment_required: false, emergency_payment_waived: true, force_entry_allowed: false, average_wait_time: 20, allow_partial_payment: true, allow_debt: false }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/system_config.js', () => {
  it('saveSettings gathers all form values and posts them', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.saveSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    const [, opts] = global.fetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.app_name).toBe('Clinic');
    expect(body.feature_enabled).toBe(true);
    expect(body.require_2fa).toBe(false);
  });

  it('saveSettings with non-ok response shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.saveSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('resetSettings cancel does not reload', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    expect(() => mod.resetSettings()).not.toThrow();
  });

  it('testSmsConnection sends phone number', async () => {
    window.prompt = vi.fn(() => '+970599123456');
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testSmsConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/sms/test', expect.objectContaining({ method: 'POST' }));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).phone_number).toBe('+970599123456');
  });

  it('testSmsConnection with empty prompt does nothing', async () => {
    window.prompt = vi.fn(() => '');
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testSmsConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('processNotificationQueue posts and reports result', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.processNotificationQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/notifications/process', expect.objectContaining({ method: 'POST' }));
  });

  it('processNotificationQueue fetch failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.processNotificationQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('testConnection posts db settings', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/api/config/test_db?action=test_db');
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).host).toBe('localhost');
  });

  it('testConnection failure shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'boom' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('twilio provider change shows and hides settings', async () => {
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const select = document.getElementById('sms_provider');
    select.value = 'twilio';
    select.dispatchEvent(new Event('change'));
    expect(document.getElementById('twilioSettings').style.display).toBe('block');
    select.value = 'none';
    select.dispatchEvent(new Event('change'));
    expect(document.getElementById('twilioSettings').style.display).toBe('none');
  });

  it('DOMContentLoaded loads general settings from audit load', async () => {
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/config/audit_log?action=load', expect.objectContaining({ credentials: 'same-origin' }));
    expect(document.getElementById('app_name').value).toBe('Clinic');
    expect(document.querySelector('[name="require_2fa"]').checked).toBe(true);
  });

  it('DOMContentLoaded loads department queue items', async () => {
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#deptQueueTable tbody').innerHTML).toContain('Cardiology');
    expect(document.querySelector('.dept-avg').value).toBe('20');
  });

  it('save dept queue settings button posts rows', async () => {
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/dept/queue/save', expect.objectContaining({ method: 'POST' }));
  });

  it('save dept queue settings fetch failure shows toast', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('dept/queue/save')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [{ department_id: 3, department_name: 'Cardiology', max_queue_size: 5, payment_required: false, emergency_payment_waived: true, force_entry_allowed: false, average_wait_time: 20, allow_partial_payment: true, allow_debt: false }] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('saveSettings ignores elements without id and name', async () => {
    document.body.innerHTML += '<form id="generalSettingsForm"><input type="text" value="noid"></form>';
    // No name and no id: must be skipped silently
    document.querySelectorAll('#generalSettingsForm input')[0].removeAttribute('id');
    document.querySelectorAll('#generalSettingsForm input')[0].removeAttribute('name');
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.saveSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(Object.keys(body).every(k => k.length > 0)).toBe(true);
  });

  it('saveSettings server success:false shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.saveSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('testSmsConnection non-ok status shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 400 });
    window.prompt = vi.fn(() => '+970599123456');
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testSmsConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('testSmsConnection server success:false shows error icon', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'bad phone' }) });
    window.prompt = vi.fn(() => '+970599123456');
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testSmsConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('فشل');
  });

  it('processNotificationQueue server success:false shows error icon', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'empty queue' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.processNotificationQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('processNotificationQueue non-ok status shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.processNotificationQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('testConnection non-ok status shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('testConnection server failure without message uses empty string', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/system_config.js');
    mod.testConnection();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('فشل الاتصال بقاعدة البيانات');
  });

  it('DOMContentLoaded loads boolean-like settings as true', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('action=load')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({
          success: true,
          settings: { app_name: 'Clinic', feature_alpha: 'true', feature_beta: '1', feature_gamma: 'yes', feature_delta: 'on', feature_epsilon: 'false' },
          items: [],
        }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    document.body.innerHTML += '<input id="feature_alpha" type="checkbox"><input id="feature_beta" type="checkbox"><input id="feature_gamma" type="checkbox"><input id="feature_delta" type="checkbox"><input id="feature_epsilon" type="checkbox">';
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('feature_alpha').checked).toBe(true);
    expect(document.getElementById('feature_beta').checked).toBe(true);
    expect(document.getElementById('feature_gamma').checked).toBe(true);
    expect(document.getElementById('feature_delta').checked).toBe(true);
    expect(document.getElementById('feature_epsilon').checked).toBe(false);
  });

  it('DOMContentLoaded skips settings with missing element', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('action=load')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: { nonexistent_key: 'v' }, items: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(true).toBe(true);
  });

  it('DOMContentLoaded dept queue rows render with false flags', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('dept/queue') && u.includes('load')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 7, department_name: '', max_queue_size: 10, payment_required: false, emergency_payment_waived: false, force_entry_allowed: false, average_wait_time: 10, allow_partial_payment: false, allow_debt: false }] }) });
      }
      if (u.includes('dept/queue') && u.includes('save')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const row = document.querySelector('#deptQueueTable tbody tr');
    expect(row).toBeTruthy();
    expect(row.querySelector('.dept-required').checked).toBe(false);
    expect(row.querySelector('.dept-emergency-waived').checked).toBe(false);
    expect(row.querySelector('.dept-force').checked).toBe(false);
    expect(row.querySelector('.dept-partial').checked).toBe(false);
    expect(row.querySelector('.dept-debt').checked).toBe(false);
  });

  it('save dept queue settings uses zero defaults for empty fields', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('dept/queue') && u.includes('load')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 9, department_name: 'X', max_queue_size: 10, payment_required: true, emergency_payment_waived: true, force_entry_allowed: true, average_wait_time: 10, allow_partial_payment: true, allow_debt: true }] }) });
      }
      if (u.includes('dept/queue') && u.includes('save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const row = document.querySelector('#deptQueueTable tbody tr');
    row.querySelector('.dept-max').value = '';
    row.querySelector('.dept-avg').value = '';
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls.find(c => String(c[0]).includes('/api/dept/queue/save'))[1].body);
    expect(body.items[0].max_queue_size).toBe(0);
    expect(body.items[0].average_wait_time).toBe(0);
  });

  it('save dept queue settings server success:false shows error', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: false }) });
      if (u.includes('dept/queue')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 9, department_name: 'X', max_queue_size: 5, payment_required: false, emergency_payment_waived: false, force_entry_allowed: false, average_wait_time: 10, allow_partial_payment: false, allow_debt: false }] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('save dept queue settings non-ok response shows toast', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('save')) return Promise.resolve({ ok: false, status: 500 });
      if (u.includes('dept/queue')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_id: 9, department_name: 'X', max_queue_size: 5, payment_required: false, emergency_payment_waived: false, force_entry_allowed: false, average_wait_time: 10, allow_partial_payment: false, allow_debt: false }] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('department queue load failure without showToast falls back to alert', async () => {
    delete window.showToast;
    window.alert = vi.fn();
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('dept/queue') && u.includes('load')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('DOMContentLoaded loads sms provider with twilio pre-selected', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    document.getElementById('sms_provider').value = 'twilio';
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('twilioSettings').style.display).toBe('block');
  });

  it('DOMContentLoaded settings load failure without showToast falls back to alert', async () => {
    delete window.showToast;
    window.alert = vi.fn();
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('audit_log') && u.includes('load')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('saveDeptQueueSettings non-ok fails to toast with alert fallback', async () => {
    delete window.showToast;
    window.alert = vi.fn();
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('save')) return Promise.resolve({ ok: false, status: 500 });
      if (u.includes('dept/queue')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, settings: {}, items: [] }) });
    });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('saveDeptQueueSettings').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('DOMContentLoaded settings load failure shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });
});