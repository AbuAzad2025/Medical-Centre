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

  it('DOMContentLoaded settings load failure shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/system_config.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });
});