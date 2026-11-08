import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <table id="usersTable"><tbody>
      <tr data-status="active" data-admin="admin" data-user-id="7"><td>Ahmad</td><td>ahmad</td><td>a@x.com</td><td>Admin</td><td>Ops</td><td>نشط</td><td>now</td></tr>
      <tr data-status="inactive" data-admin="user" data-user-id="8"><td>Sara</td><td>sara</td><td>s@x.com</td><td>User</td><td>Lab</td><td>معطل</td><td>never</td></tr>
    </tbody></table>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('manager/user_management.js', () => {
  it('viewUser renders the real row data', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.viewUser('7');
    const args = window.Swal.fire.mock.calls[0][0];
    expect(args.title).toBe('Ahmad');
    expect(args.html).toContain('ahmad');
    expect(args.html).toContain('a@x.com');
    expect(args.html).toContain('Ops');
    expect(args.html).toContain('now');
  });

  it('viewUser with unknown id shows a gentle message instead of fake data', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.viewUser('999');
    expect(window.Swal.fire).toHaveBeenCalledWith(expect.objectContaining({ title: 'تفاصيل المستخدم' }));
  });

  it('exportUsers creates a CSV blob from the visible rows', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    expect(() => mod.exportUsers()).not.toThrow();
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    expect(blob.type).toContain('text/csv');
  });

  it('exportUsers with no data rows produces an empty-body CSV without crashing', async () => {
    document.body.innerHTML = '<table id="usersTable"><tbody></tbody></table>';
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    expect(() => mod.exportUsers()).not.toThrow();
  });

  it('filterUsers filter active shows only active rows', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    const e = { target: document.createElement('button') };
    mod.filterUsers('active', e);
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
    expect(e.target.classList.contains('active')).toBe(true);
  });

  it('filterUsers admin shows admin rows only', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.filterUsers('admin', null);
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterUsers all shows every row', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.filterUsers('all', null);
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('DOMContentLoaded attaches hover handlers', async () => {
    await loadModule('static/js/pages/manager/user_management.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#usersTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});
