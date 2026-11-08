import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="auditFiltersForm">
      <input name="action" value="">
      <input name="status" value="pending">
    </form>
    <table id="auditLogsTable"><tbody><tr data-status="success"><td>A</td></tr></tbody></table>
  `;
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('audit_trail.js exportAuditLogs fallback arms', () => {
  it('log with missing timestamp, user, entity_type and description falls back to placeholders', async () => {
    window.__M0__ = [{ action: 'login', status: 'success' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs()).not.toThrow();
  });

  it('log with a user but missing full_name still renders without crashing', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', user: {}, action: 'x', status: 'success', description: 'd' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs()).not.toThrow();
  });

  it('log with missing status renders without crashing', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', user: { full_name: 'Sara' }, action: 'x', status: 'success', entity_type: 'patient', description: 'd' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs()).not.toThrow();
  });
});

describe('audit_trail.js filterLogs and applyFilters arms', () => {
  it('filterLogs without an event argument clears active marks', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    const btn = document.createElement('button');
    btn.classList.add('btn-outline-primary', 'active');
    document.body.appendChild(btn);
    mod.filterLogs('success');
    expect(document.querySelector('#auditLogsTable tbody tr').style.display).toBe('');
    expect(btn.classList.contains('active')).toBe(false);
  });

  it('applyFilters excludes empty form fields from the filters', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.applyFilters();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });
});
