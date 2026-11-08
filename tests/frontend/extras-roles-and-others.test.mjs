import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.location = { href: '', reload: vi.fn() };
  window.print = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/list.js', () => {
  it('select change submits the form', async () => {
    document.body.innerHTML = `
      <form id="filterForm">
        <select name="priority"><option value="">" "</option><option value="high">high</option></select>
      </form>
    `;
    const form = document.getElementById('filterForm');
    form.submit = vi.fn();
    await loadModule('static/js/pages/emergency/list.js');
    const sel = document.querySelector('select[name="priority"]');
    sel.dispatchEvent(new Event('change'));
    expect(form.submit).toHaveBeenCalled();
  });

  it('setInterval check does not fire reload when no .status-active', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/emergency/list.js');
    vi.advanceTimersByTime(31000);
    expect(window.location.reload).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});

describe('super_admin/roles.js', () => {
  beforeEach(() => {
    window.API_ROUTES = {
      edit_role: '/super-admin/roles/0/edit',
      manage_role_permissions: '/super-admin/roles/0/permissions',
      manage_role_department_permissions: '/super-admin/roles/0/department-permissions',
    };
  });

  it('editRole navigates to edit url', async () => {
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.editRole('5');
    expect(window.location.href).toContain('/super-admin/roles/5/edit');
  });

  it('managePermissions navigates to permissions url', async () => {
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.managePermissions('5');
    expect(window.location.href).toContain('/super-admin/roles/5/permissions');
  });

  it('manageDepartmentPermissions navigates to department url', async () => {
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.manageDepartmentPermissions('5');
    expect(window.location.href).toContain('/super-admin/roles/5/department-permissions');
  });

  it('editRole falls back to default when API_ROUTES missing', async () => {
    window.API_ROUTES = undefined;
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.editRole('9');
    expect(window.location.href).toContain('/super-admin/roles/9/edit');
  });

  it('exposes all three functions on window', async () => {
    await loadModule('static/js/pages/super_admin/roles.js');
    expect(typeof window.editRole).toBe('function');
    expect(typeof window.managePermissions).toBe('function');
    expect(typeof window.manageDepartmentPermissions).toBe('function');
  });
});

describe('portal/base.js', () => {
  it('registers service worker when supported', async () => {
    const register = vi.fn().mockResolvedValue({ scope: '/' });
    Object.defineProperty(window.navigator, 'serviceWorker', {
      value: { register },
      configurable: true,
      writable: true,
    });
    await loadModule('static/js/pages/portal/base.js');
    expect(register).toHaveBeenCalledWith('/static/pwa/sw.js', { scope: '/' });
  });

  it('does not throw when serviceWorker unsupported', async () => {
    try { delete window.navigator.serviceWorker; } catch (e) { /* not deletable in all jsdom versions */ }
    if ('serviceWorker' in window.navigator) {
      expect(window.navigator.serviceWorker).toBeTruthy();
      return;
    }
    await loadModule('static/js/pages/portal/base.js');
    expect(true).toBe(true);
  });
});

describe('radiology/add_scan.js', () => {
  it('DOMContentLoaded sets scan_date to today', async () => {
    document.body.innerHTML = '<input name="scan_date">';
    await loadModule('static/js/pages/radiology/add_scan.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const today = new Date().toISOString().split('T')[0];
    expect(document.querySelector('input[name="scan_date"]').value).toBe(today);
  });
});