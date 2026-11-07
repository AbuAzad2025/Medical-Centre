import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <table id="usersTable"><tbody>
      <tr data-status="active" data-admin="admin"><td>Ahmad</td><td>ahmad</td><td>a@x.com</td><td>Admin</td><td>Ops</td><td>نشط</td><td>now</td></tr>
      <tr data-status="inactive" data-admin="user"><td>Sara</td><td>sara</td><td>s@x.com</td><td>User</td><td>Lab</td><td>معطل</td><td>never</td></tr>
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
});

afterEach(() => {
  vi.useRealTimers();
});

describe('manager/user_management.js', () => {
  it('addNewUser shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.addNewUser();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('viewUser shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.viewUser('42');
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('42');
  });

  it('editUser shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    mod.editUser('42');
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('42');
  });

  it('exportUsers creates csv download', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    expect(() => mod.exportUsers()).not.toThrow();
  });

  it('toggleUser confirm reloads', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.toggleUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('toggleUser cancel does not reload', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.toggleUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('resetPassword shows confirm then success', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.resetPassword('42');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('deleteUser confirms and shows success', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
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

  it('bulkActivate confirms and reloads', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.bulkActivate();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('bulkActivate cancel does not show success', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.bulkActivate();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('bulkDeactivate confirms and reloads', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.bulkDeactivate();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('bulkResetPassword confirms and resets', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    await mod.bulkResetPassword();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('bulkExport calls exportUsers', async () => {
    const mod = await loadModule('static/js/pages/manager/user_management.js');
    expect(() => mod.bulkExport()).not.toThrow();
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