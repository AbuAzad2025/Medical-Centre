import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="backupsTable"><tbody>
      <tr data-status="completed"><td>Backup 1</td></tr>
      <tr data-status="failed"><td>Backup 2</td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Completed</button>
    <button class="btn-outline-danger">Failed</button>
    <form id="backupSettingsForm">
      <input type="checkbox" id="auto_backup" checked />
    </form>
    <meta name="csrf-token" content="test-token" />
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Swal.showLoading = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, history: [], enabled: true, type: 'daily', time: '02:00' }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('super_admin/system_backup.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
  });

  test('createBackup is a function', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
    expect(typeof createBackup).toBe('function');
  });

  test('filterBackups is a function', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
    expect(typeof filterBackups).toBe('function');
  });

  test('filterBackups with event parameter', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterBackups('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('restoreBackup is a function', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
    expect(typeof restoreBackup).toBe('function');
  });

  test('deleteBackup is a function', async () => {
    await loadScript('static/js/pages/super_admin/system_backup.js');
    expect(typeof deleteBackup).toBe('function');
  });
});
