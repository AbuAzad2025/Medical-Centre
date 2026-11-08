import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="addStaffForm">
      <select id="user_id"><option value="11">Staff 11</option></select>
      <button type="submit">Add</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '5';
  window.__M1__ = '5';
  window.API_ROUTES = {
    add_department_staff: '/super-admin/department-staff/0/add',
    remove_department_staff: '/super-admin/department-staff/0/remove',
  };
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('department_staff.js add form branches', () => {
  it('add success reloads the page', async () => {
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('add uses the URL with the department id from __M0__', async () => {
    delete window.API_ROUTES;
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/department-staff/5/add');
  });

  it('add uses API_ROUTES endpoint when set', async () => {
    window.API_ROUTES = { add_department_staff: '/custom/add/0' };
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/add/5');
  });

  it('add failure with server message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'staff exists' }) });
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('staff exists');
  });

  it('add failure without server message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('add non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('add without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/department_staff.js');
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('missing add form element does not crash the module', async () => {
    document.getElementById('addStaffForm').remove();
    await expect(loadModule('static/js/pages/super_admin/department_staff.js')).resolves.toBeDefined();
  });
});

describe('department_staff.js remove branches', () => {
  it('remove success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('cancelled removal does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('remove uses the URL with the department id from __M1__', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/department-staff/5/remove');
  });

  it('remove uses API_ROUTES endpoint when set', async () => {
    window.API_ROUTES = { remove_department_staff: '/custom/remove/0' };
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/remove/5');
  });

  it('remove failure with server message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'has active shifts' }) });
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('has active shifts');
  });

  it('remove failure without server message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('remove non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('remove without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    mod.removeFromDepartment(11);
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});
