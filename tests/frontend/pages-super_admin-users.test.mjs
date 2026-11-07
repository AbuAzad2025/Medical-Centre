import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table id="usersTable"><tbody><tr data-status="Active"><td>A</td><td id="temp-pass-1"></td></tr><tr data-status="Inactive"><td>B</td><td id="temp-pass-2"></td></tr></tbody></table>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {
    super_admin_delete_user: '/super-admin/users/0/delete',
    super_admin_reset_password: '/super-admin/users/0/reset-password',
  };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, temp_password: 'ABC-XYZ' }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/users.js', () => {
  it('swalInfo shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.swalInfo('hello');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('hello');
  });

  it('swalConfirmOnly prevents default and shows question', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    const e = { preventDefault: vi.fn() };
    mod.swalConfirmOnly(e, 'are you sure?');
    expect(e.preventDefault).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('question');
  });

  it('deleteUser posts to delete url on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/super-admin/users/42/delete');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
  });

  it('deleteUser cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deleteUser non-ok response shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deleteUser fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('resetPassword shows temp password on success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('1');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/super-admin/users/1/reset-password');
    expect(document.getElementById('temp-pass-1').textContent).toBe('ABC-XYZ');
    const successCall = window.Swal.fire.mock.calls.find(c => c[0].title === 'تم');
    expect(successCall).toBeTruthy();
  });

  it('resetPassword cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('42');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('resetPassword failure shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('resetPassword network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('filterUsers filters rows by dataset.status', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    const e = { target: document.createElement('button') };
    mod.filterUsers('Active', e);
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
    expect(e.target.classList.contains('active')).toBe(true);
  });

  it('filterUsers all shows all rows', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.filterUsers('all', null);
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('DOMContentLoaded attaches hover handlers', async () => {
    await loadModule('static/js/pages/super_admin/users.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#usersTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});