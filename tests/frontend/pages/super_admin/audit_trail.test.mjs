import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="auditLogsTable"><tbody>
      <tr data-status="success"><td>Success Log</td></tr>
      <tr data-status="failure"><td>Failure Log</td></tr>
    </tbody></table>
    <form id="auditFiltersForm"></form>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Success</button>
  `;
  window.__M0__ = [{ timestamp: '2026-01-01', user: { full_name: 'Admin' }, action: 'login', entity_type: 'user', description: 'Login', status: 'success' }];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

describe('super_admin/audit_trail.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/audit_trail.js');
  });

  test('filterLogs is a function', async () => {
    await loadScript('static/js/pages/super_admin/audit_trail.js');
    expect(typeof filterLogs).toBe('function');
  });

  test('exportAuditLogs is a function', async () => {
    await loadScript('static/js/pages/super_admin/audit_trail.js');
    expect(typeof exportAuditLogs).toBe('function');
  });

  test('filterLogs with event parameter', async () => {
    await loadScript('static/js/pages/super_admin/audit_trail.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterLogs('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('filterLogs filters by status', async () => {
    await loadScript('static/js/pages/super_admin/audit_trail.js');
    filterLogs('success');
    const rows = document.querySelectorAll('#auditLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });
});
