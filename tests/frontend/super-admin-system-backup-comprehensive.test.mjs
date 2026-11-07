import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-tok" />
    <button class="btn-backup">Backup</button>
  `;
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.API_ROUTES = { create_backup: '/api/backup', backup_schedule: '/api/schedule' };
  window.__M = [];
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, enabled: true }),
  });
  await loadModule('static/js/pages/super_admin/system_backup.js');
});

describe('super_admin/system_backup.js', () => {
  it('loads without error', () => {
    expect(typeof window.createBackup).toBe('function');
  });

  it('createBackup exists', () => {
    expect(window.createBackup).toBeDefined();
  });

  it('scheduleBackup exists', () => {
    expect(window.scheduleBackup).toBeDefined();
  });

  it('createFullBackup exists', () => {
    expect(window.createFullBackup).toBeDefined();
  });

  it('restoreBackup exists', () => {
    expect(window.restoreBackup).toBeDefined();
  });

  it('deleteBackup exists', () => {
    expect(window.deleteBackup).toBeDefined();
  });
});