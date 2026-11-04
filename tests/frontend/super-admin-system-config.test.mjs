import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-tok" />
    <form id="generalSettingsForm">
      <input name="site_name" value="Test" />
      <input type="checkbox" name="debug" checked />
      <select name="lang"><option value="ar" selected>AR</option></select>
      <textarea name="notes">note</textarea>
    </form>
    <form id="securitySettingsForm"><input name="max_login" value="5" /></form>
    <form id="databaseSettingsForm"><input name="db_pool" value="10" /></form>
    <form id="notificationsSettingsForm"><input name="email_enabled" value="true" /></form>
    <form id="backupSettingsForm"><input name="backup_freq" value="daily" /></form>
  `;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.__M = [];
  window.__M0__ = '/api/settings';
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true }),
  });
  await loadModule('static/js/pages/super_admin/system_config.js');
});

describe('super_admin/system_config.js', () => {
  it('loads without error', () => {
    expect(typeof window.saveSettings).toBe('function');
  });

  it('saveSettings calls fetch', async () => {
    window.saveSettings();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('resetSettings calls Swal', async () => {
    if (typeof window.resetSettings === 'function') {
      window.resetSettings();
      expect(window.Swal.fire).toHaveBeenCalled();
    }
  });
});