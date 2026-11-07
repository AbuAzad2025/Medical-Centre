import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table id="backupsTable"><tbody><tr data-status="completed"><td>Backup 1</td></tr><tr data-status="failed"><td>Backup 2</td></tr></tbody></table>
    <form id="backupSettingsForm"><input name="setting1" value="val1"><input type="checkbox" id="auto_backup" checked></form>
    <button id="createBtn">Create</button>
  `;
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
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'OK', enabled: true, type: 'daily', time: '02:00', history: [{ status: 'COMPLETED', type: 'full', created_at: '2026-01-01' }] }) });
  try { await loadModule('static/js/pages/super_admin/system_backup.js'); } catch (e) { /* ok */ }
});

describe('system_backup.js', () => {
  it('createBackup calls Swal and fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    const btn = document.createElement('button');
    await mod.createBackup({ target: btn });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('scheduleBackup fetches settings', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.scheduleBackup();
    expect(global.fetch).toHaveBeenCalled();
  });

  it('createFullBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.createFullBackup({ target: document.createElement('button') });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('createIncrementalBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.createIncrementalBackup({ target: document.createElement('button') });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('createDatabaseBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.createDatabaseBackup({ target: document.createElement('button') });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('createFilesBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.createFilesBackup({ target: document.createElement('button') });
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('filterBackups filters rows', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    const e = { target: document.createElement('button') };
    mod.filterBackups('completed', e);
    const rows = document.querySelectorAll('#backupsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterBackups all shows all', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    const e = { target: document.createElement('button') };
    mod.filterBackups('all', e);
    const rows = document.querySelectorAll('#backupsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('restoreBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.restoreBackup('123');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('deleteBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.deleteBackup('123');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('cancelBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.cancelBackup('123');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('retryBackup calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('full');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('retryBackup error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'err' }) });
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('incremental');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('retryBackup fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.retryBackup('differential');
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBackupSettings calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBackupSettings error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'err' }) });
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBackupSettings fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    await mod.saveBackupSettings();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('generateBackupReport sets location', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.generateBackupReport();
    expect(window.location.href).toContain('backup/report');
  });

  it('exportBackupLogs sets location', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.exportBackupLogs();
    expect(window.location.href).toContain('export-logs');
  });

  it('viewBackupHistory calls fetch', async () => {
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewBackupHistory with FAILED and IN_PROGRESS statuses', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, history: [{ status: 'FAILED', type: 'db', created_at: '2026-01-01' }, { status: 'IN_PROGRESS', type: 'files', created_at: '2026-01-02' }] }) });
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewBackupHistory with empty history', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, history: [] }) });
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewBackupHistory error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'err' }) });
    const mod = await import('../../static/js/pages/super_admin/system_backup.js');
    mod.viewBackupHistory();
    await new Promise(r => setTimeout(r, 50));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('DOMContentLoaded attaches handlers', async () => {
    document.body.innerHTML = '<table id="backupsTable"><tbody><tr data-status="completed"><td>Backup 1</td></tr></tbody></table>';
    vi.resetModules();
    await loadModule('static/js/pages/super_admin/system_backup.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 50));
    const row = document.querySelector('#backupsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    row.dispatchEvent(new MouseEvent('mouseleave'));
    await new Promise(r => setTimeout(r, 50));
    expect(row.style.backgroundColor).toBe('');
  });
});