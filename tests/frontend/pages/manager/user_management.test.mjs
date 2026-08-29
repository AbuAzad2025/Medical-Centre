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
  `;
  window.__M0__ = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('manager/user_management.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/user_management.js');
  });

  test('filterUsers is a function', async () => {
    await loadScript('static/js/pages/manager/user_management.js');
    expect(typeof filterUsers).toBe('function');
  });

  test('filterUsers with event parameter', async () => {
    await loadScript('static/js/pages/manager/user_management.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterUsers('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('exportUsers is a function', async () => {
    await loadScript('static/js/pages/manager/user_management.js');
    expect(typeof exportUsers).toBe('function');
  });
});
