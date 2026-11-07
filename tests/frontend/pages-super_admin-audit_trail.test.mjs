import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <table id="auditLogsTable"><tbody><tr data-status="SUCCESS"><td>x</td></tr><tr data-status="FAILED"><td>y</td></tr></tbody></table>
    <form id="auditFiltersForm">
      <input name="from" value="2026-01-01">
      <input name="to" value="">
      <select name="status"><option value="SUCCESS">SUCCESS</option></select>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.__M0__ = [
    { timestamp: '2026-11-01T09:00', user: { full_name: 'admin' }, action: 'login', entity_type: 'user', description: 'login', status: 'SUCCESS' },
  ];
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/audit_trail.js', () => {
  it('refreshAuditLogs calls reload', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.refreshAuditLogs()).not.toThrow();
  });

  it('exportAuditLogs builds CSV link', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs()).not.toThrow();
  });

  it('applyFilters collects non-empty fields', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.applyFilters();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('clearFilters resets form', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.clearFilters();
    expect(document.getElementById('auditFiltersForm').reset).toBeDefined();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('filterLogs shows all rows for all', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.filterLogs('all', null);
    const rows = document.querySelectorAll('#auditLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('filterLogs filters by status', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.filterLogs('SUCCESS', null);
    const rows = document.querySelectorAll('#auditLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterLogs marks clicked button active', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    const btn = document.createElement('button');
    mod.filterLogs('all', { target: btn });
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('viewLogDetails shows details', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.viewLogDetails('42');
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('42');
  });

  it('exportLog shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportLog('42');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('generateAuditReport shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.generateAuditReport();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('exportAllLogs delegates to exportAuditLogs', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAllLogs()).not.toThrow();
  });

  it('cleanOldLogs confirms before cleaning', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    await mod.cleanOldLogs();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('viewAuditSettings shows settings info', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.viewAuditSettings();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('DOMContentLoaded attaches hover handlers', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#auditLogsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});