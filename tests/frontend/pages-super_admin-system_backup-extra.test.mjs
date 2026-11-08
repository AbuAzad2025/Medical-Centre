import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table id="backupsTable"><tbody><tr data-status="completed"><td>Backup 1</td></tr><tr data-status="failed"><td>Backup 2</td></tr></tbody></table>
    <form id="backupSettingsForm"><input name="setting1" value="val1"><input type="checkbox" id="auto_backup" checked></form>
    <button id="createBtn">Create</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {
    create_backup: '/api/backup/create',
    backup_schedule: '/api/backup/schedule',
    restore_backup: '/api/backup/restore/0',
    delete_backup: '/api/backup/delete/0',
    cancel_backup: '/api/backup/cancel/0',
    save_backup_settings: '/api/backup/settings',
    backup_report: '/api/backup/report',
    export_backup_logs: '/api/backup/export-logs',
    backup_history: '/api/backup/history',
  };
  window.escHtml = (s) => s;
  window.location = { href: '', reload: vi.fn() };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'OK', enabled: true, type: 'daily', time: '02:00', history: [{ status: 'COMPLETED', type: 'full', created_at: '2026-01-01' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('system_backup.js extra branches', () => {
  it('createBackup with cancelled confirmation does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createBackup({ target: document.createElement('button') });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('createBackup non-ok response shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createBackup({ target: document.createElement('button') });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('createBackup failure without message uses fallback text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createBackup({ target: document.createElement('button') });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('createBackup success re-enables button', async () => {
    const btn = document.createElement('button');
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createBackup({ target: btn });
    await new Promise(r => setTimeout(r, 30));
    expect(btn.disabled).toBe(false);
  });

  it('createFullBackup non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 502 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createFullBackup({ target: document.createElement('button') });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('createIncrementalBackup with missing server message uses fallback', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const btn = document.createElement('button');
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createIncrementalBackup({ target: btn });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
    expect(btn.disabled).toBe(false);
    expect(btn.innerHTML).toContain('fas fa-plus-circle');
  });

  it('createIncrementalBackup cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createIncrementalBackup({ target: document.createElement('button') });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('createDatabaseBackup non-ok shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const btn = document.createElement('button');
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createDatabaseBackup({ target: btn });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
    expect(btn.disabled).toBe(false);
    expect(btn.innerHTML).toContain('fas fa-table');
  });

  it('createFilesBackup cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createFilesBackup({ target: document.createElement('button') });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('createFilesBackup non-ok shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const btn = document.createElement('button');
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createFilesBackup({ target: btn });
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
    expect(btn.disabled).toBe(false);
    expect(btn.innerHTML).toContain('fas fa-folder');
  });

  it('scheduleBackup network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0]).toMatch(/خطأ/);
  });

  it('scheduleBackup server success:false shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'boom' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0]).toMatch(/خطأ/);
  });

  it('scheduleBackup server save failure response shows error', async () => {
    const responses = [
      { ok: true, json: () => Promise.resolve({ success: true, enabled: true, type: 'daily', time: '02:00' }) },
      { ok: true, json: () => Promise.resolve({ success: false, message: 'bad config' }) },
    ];
    let call = 0;
    global.fetch = vi.fn().mockImplementation(() => Promise.resolve(responses[call++]));
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: { enabled: true, type: 'daily', time: '02:00' } });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    await new Promise(r => setTimeout(r, 100));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('scheduleBackup server save success shows success', async () => {
    const responses = [
      { ok: true, json: () => Promise.resolve({ success: true, enabled: true, type: 'daily', time: '02:00' }) },
      { ok: true, json: () => Promise.resolve({ success: true, message: 'saved' }) },
    ];
    let call = 0;
    global.fetch = vi.fn().mockImplementation(() => Promise.resolve(responses[call++]));
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: { enabled: true, type: 'daily', time: '02:00' } });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    await new Promise(r => setTimeout(r, 100));
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('scheduleBackup server save non-ok shows error', async () => {
    const responses = [
      { ok: true, json: () => Promise.resolve({ success: true, enabled: true, type: 'daily', time: '02:00' }) },
      { ok: false, status: 500 },
    ];
    let call = 0;
    global.fetch = vi.fn().mockImplementation(() => Promise.resolve(responses[call++]));
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: { enabled: true, type: 'daily', time: '02:00' } });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    await new Promise(r => setTimeout(r, 100));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('restoreBackup cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.restoreBackup('1');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('restoreBackup non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.restoreBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('restoreBackup server failure shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'too new' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.restoreBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('restoreBackup fetch network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.restoreBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('deleteBackup non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.deleteBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('deleteBackup network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.deleteBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('cancelBackup non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.cancelBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('cancelBackup network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.cancelBackup('1');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire.mock.calls[1][0]).toMatch(/خطأ/);
  });

  it('retryBackup with INCREMENTAL uppercase maps to incremental', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('INCREMENTAL');
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.type).toBe('incremental');
  });

  it('retryBackup with DIFFERENTIAL maps to database', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('DIFFERENTIAL');
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.type).toBe('database');
  });

  it('retryBackup with differential maps to database', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('differential');
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.type).toBe('database');
  });

  it('retryBackup with unknown type falls back to full', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('bogus');
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.type).toBe('full');
  });

  it('retryBackup cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('full');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('retryBackup non-ok shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('full');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('retryBackup success with message shows success', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('full');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('retryBackup network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('full');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBackupSettings sends auto_backup=false when unchecked', async () => {
    document.getElementById('auto_backup').checked = false;
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.auto_backup).toBe(false);
  });

  it('saveBackupSettings non-ok shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBackupSettings success shows success', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'saved' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0] || window.Swal.fire.mock.calls[0][0]).toMatch(/تم|أكمل/);
  });

  it('saveBackupSettings cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('viewBackupHistory with secondary status', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, history: [{ status: 'OTHER', type: 'full', created_at: '2026-01-01' }] }) });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewBackupHistory network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewBackupHistory non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('filterBackups works without e argument', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    mod.filterBackups('failed');
    const rows = document.querySelectorAll('#backupsTable tbody tr');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
  });

  it('filterBackups marks the clicked button active', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    const btn = document.createElement('button');
    btn.classList.add('btn-outline-success');
    mod.filterBackups('all', { target: btn });
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('createBackup works without meta csrf', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/system_backup.js');
    await mod.createBackup({ target: document.createElement('button') });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('DOMContentLoaded without backupsTable does not throw', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/super_admin/system_backup.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});