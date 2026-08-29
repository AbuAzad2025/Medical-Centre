import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="usersTable"><tbody>
      <tr data-status="active"><td>Admin</td></tr>
      <tr data-status="inactive"><td>User1</td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Active</button>
    <button class="btn-outline-warning">Inactive</button>
    <meta name="csrf-token" content="test-token" />
  `;
  window.__M0__ = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('super_admin/users.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/users.js');
  });

  test('filterUsers is a function', async () => {
    await loadScript('static/js/pages/super_admin/users.js');
    expect(typeof window.filterUsers).toBe('function');
  });

  test('filterUsers with event parameter', async () => {
    await loadScript('static/js/pages/super_admin/users.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    window.filterUsers('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('filterUsers filters by status', async () => {
    await loadScript('static/js/pages/super_admin/users.js');
    window.filterUsers('active');
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  test('deleteUser is a function', async () => {
    await loadScript('static/js/pages/super_admin/users.js');
    expect(typeof window.deleteUser).toBe('function');
  });
});
