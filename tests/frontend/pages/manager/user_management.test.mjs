import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="usersTable"><tbody>
      <tr data-user-id="1" data-status="active"><td>Admin</td><td>admin1</td><td>a@a</td><td>Admin</td><td>Ops</td><td>نشط</td><td>now</td></tr>
      <tr data-user-id="2" data-status="inactive"><td>User1</td><td>user1</td><td>u@u</td><td>User</td><td>Lab</td><td>معطل</td><td>never</td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Active</button>
  `;
  window.__M0__ = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
  window.location = { href: '', reload: vi.fn() };
});

describe('manager/user_management.js', () => {
  test('loads without critical errors', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
  });

  test('filterUsers is a function', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
    expect(typeof filterUsers).toBe('function');
  });

  test('filterUsers with event parameter', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterUsers('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('exportUsers is a function', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
    expect(typeof exportUsers).toBe('function');
  });

  test('viewUser renders row content in a Swal', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
    viewUser('1');
    const args = window.Swal.fire.mock.calls[0][0];
    expect(args.title).toBe('Admin');
    expect(args.html).toContain('a@a');
  });
});
