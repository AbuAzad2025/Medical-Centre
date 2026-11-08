import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<meta name="csrf-token" content="test-csrf">';
  window.__M = [];
  window.API_ROUTES = {
    activate_department: '/super-admin/activate-department/0',
    deactivate_department: '/super-admin/deactivate-department/0',
  };
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('department_detail.js activate/deactivate branches', () => {
  it('activation success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('activation cancelled does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('activation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation network failure triggers the catch error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/activate-department/7');
  });

  it('activation without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('deactivation success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('deactivation cancelled does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deactivation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/deactivate-department/7');
  });

  it('server success:false stays silent (current behavior)', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).not.toHaveBeenCalled();
  });
});
