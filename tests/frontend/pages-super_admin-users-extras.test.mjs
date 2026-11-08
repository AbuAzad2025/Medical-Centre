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
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }), showLoading: vi.fn() };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, temp_password: 'ABC-XYZ' }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('users.js deleteUser fallback arms', () => {
  it('unset API_ROUTES falls back to the default delete URL', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/users/42/delete');
  });

  it('missing csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.deleteUser('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('users.js resetPassword branches', () => {
  it('success writes the temp password to the cell then clears it after 60s', async () => {
    vi.useFakeTimers();
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('1');
    await vi.advanceTimersByTimeAsync(30);
    expect(document.getElementById('temp-pass-1').textContent).toBe('ABC-XYZ');
    await vi.advanceTimersByTimeAsync(61000);
    expect(document.getElementById('temp-pass-1').textContent).toBe('');
    vi.useRealTimers();
  });

  it('success with a missing password cell surfaces the outer error path', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('999');
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('unset API_ROUTES falls back to the default reset URL', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('1');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/users/1/reset-password');
  });

  it('non-ok response triggers the catch error path', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('1');
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('missing csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.resetPassword('1');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('users.js filterUsers branches', () => {
  it('filter by Active hides inactive rows and marks the button active', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    const btn = document.createElement('button');
    btn.classList.add('btn-outline-primary');
    document.body.appendChild(btn);
    mod.filterUsers('Active', { target: btn });
    const rows = document.querySelectorAll('#usersTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('filter without an event argument works and clears active marks', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    const btn = document.createElement('button');
    btn.classList.add('btn-outline-primary', 'active');
    document.body.appendChild(btn);
    mod.filterUsers('all');
    expect(document.querySelectorAll('#usersTable tbody tr')[1].style.display).toBe('');
    expect(btn.classList.contains('active')).toBe(false);
  });

  it('unknown status hides every row', async () => {
    const mod = await loadModule('static/js/pages/super_admin/users.js');
    mod.filterUsers('Mystery');
    document.querySelectorAll('#usersTable tbody tr').forEach(r => expect(r.style.display).toBe('none'));
  });
});
