import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input id="searchInput">
    <table id="departmentsTable">
      <thead><tr><th>Name</th></tr></thead>
      <tbody><tr><td>Cardiology</td></tr><tr><td>Laboratory</td></tr></tbody>
    </table>
    <form id="addDepartmentForm">
      <input name="name" value="Ops">
      <button type="submit">Add</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {
    view_department: '/super-admin/department/0',
    edit_department: '/super-admin/edit-department/0',
    department_staff: '/super-admin/department-staff/0',
    activate_department: '/super-admin/activate-department/0',
    deactivate_department: '/super-admin/deactivate-department/0',
    export_departments: '/super-admin/export-departments',
    create_department: '/super-admin/departments/create',
  };
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.open = vi.fn(() => ({}));
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/departments.js', () => {
  it('viewDepartment opens view URL in new window', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.viewDepartment('7');
    expect(window.open).toHaveBeenCalledWith('/super-admin/department/7', '_blank');
  });

  it('editDepartment sets location.href', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.editDepartment('7');
    expect(window.location.href).toBe('/super-admin/edit-department/7');
  });

  it('manageStaff sets location.href', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.manageStaff('7');
    expect(window.location.href).toBe('/super-admin/department-staff/7');
  });

  it('activateDepartment confirms and fetches activate', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/activate-department/7');
  });

  it('activateDepartment failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activateDepartment fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activateDepartment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivateDepartment confirms and fetches deactivate', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/deactivate-department/7');
  });

  it('deactivateDepartment failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('exportDepartments opens export URL', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.exportDepartments();
    expect(window.open).toHaveBeenCalledWith('/super-admin/export-departments', '_blank');
  });

  it('search input filters rows by text', async () => {
    await loadModule('static/js/pages/super_admin/departments.js');
    const input = document.getElementById('searchInput');
    input.value = 'cardio';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#departmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('addDepartmentForm success reloads', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/departments/create');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
  });

  it('addDepartmentForm failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'dup' }) });
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('addDepartmentForm fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});