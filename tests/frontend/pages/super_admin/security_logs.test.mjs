import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="securityLogsTable"><tbody>
      <tr data-level="CRITICAL"><td>Critical Log</td></tr>
      <tr data-level="INFO"><td>Info Log</td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-danger">Critical</button>
    <button class="btn-outline-warning">Warning</button>
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

describe('super_admin/security_logs.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/security_logs.js');
  });

  test('filterLogs is a function', async () => {
    await loadScript('static/js/pages/super_admin/security_logs.js');
    expect(typeof filterLogs).toBe('function');
  });

  test('exportLogs is a function', async () => {
    await loadScript('static/js/pages/super_admin/security_logs.js');
    expect(typeof exportLogs).toBe('function');
  });

  test('filterLogs with event parameter', async () => {
    await loadScript('static/js/pages/super_admin/security_logs.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterLogs('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('filterLogs filters by level', async () => {
    await loadScript('static/js/pages/super_admin/security_logs.js');
    filterLogs('CRITICAL');
    const rows = document.querySelectorAll('#securityLogsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });
});
