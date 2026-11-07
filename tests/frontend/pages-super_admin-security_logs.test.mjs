import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <table id="securityLogsTable"><tbody><tr data-level="INFO"><td>x</td></tr><tr data-level="CRITICAL"><td>y</td></tr></tbody></table>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/security_logs.js', () => {
  it('refreshLogs does not throw', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    expect(() => mod.refreshLogs()).not.toThrow();
  });

  it('exportLogs builds CSV', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    expect(() => mod.exportLogs()).not.toThrow();
  });

  it('filterLogs all shows all rows', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    mod.filterLogs('all', null);
    const rows = document.querySelectorAll('#securityLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('filterLogs filters by level', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    mod.filterLogs('INFO', null);
    const rows = document.querySelectorAll('#securityLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterLogs marks clicked button active', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    const btn = document.createElement('button');
    mod.filterLogs('all', { target: btn });
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('viewLogDetails shows details', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    mod.viewLogDetails('42');
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('42');
  });

  it('blockIP prompts for ip and shows success', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: '1.2.3.4' });
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    await mod.blockIP();
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('success');
  });

  it('blockIP cancel does not show success', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    await mod.blockIP();
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('resetFailedLogins confirms', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    await mod.resetFailedLogins();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('clearLogs confirms', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    await mod.clearLogs();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('exportSecurityReport shows success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/security_logs.js');
    mod.exportSecurityReport();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('DOMContentLoaded attaches hover handlers', async () => {
    await loadModule('static/js/pages/super_admin/security_logs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#securityLogsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});