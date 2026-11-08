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

describe('departments.js search branches', () => {
  it('filters rows by the search term (case insensitive)', async () => {
    await loadModule('static/js/pages/super_admin/departments.js');
    const input = document.getElementById('searchInput');
    input.value = 'CARD';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#departmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('no match hides every row; clearing restores all rows', async () => {
    await loadModule('static/js/pages/super_admin/departments.js');
    const input = document.getElementById('searchInput');
    input.value = 'zzz';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#departmentsTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe('none'));
    input.value = '';
    input.dispatchEvent(new Event('input'));
    rows.forEach(r => expect(r.style.display).toBe(''));
  });

  it('missing searchInput element does not crash the module', async () => {
    document.getElementById('searchInput').remove();
    await expect(loadModule('static/js/pages/super_admin/departments.js')).resolves.toBeDefined();
  });
});

describe('departments.js navigation fallback arms', () => {
  it('viewDepartment falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.viewDepartment('3');
    expect(window.open).toHaveBeenCalledWith('/super-admin/department/3', '_blank');
  });

  it('editDepartment falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.editDepartment('3');
    expect(window.location.href).toBe('/super-admin/edit-department/3');
  });

  it('manageStaff falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.manageStaff('3');
    expect(window.location.href).toBe('/super-admin/department-staff/3');
  });

  it('exportDepartments falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.exportDepartments();
    expect(window.open).toHaveBeenCalledWith('/super-admin/export-departments', '_blank');
  });
});

describe('departments.js activate/deactivate branches', () => {
  it('cancelled activation does not fetch and does not reload', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('activation success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('activation failure shows the error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation network failure triggers the catch error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('activation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.activateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/activate-department/3');
  });

  it('cancelled deactivation does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('3');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivation failure shows the error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deactivation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deactivation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/departments.js');
    mod.deactivateDepartment('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/deactivate-department/3');
  });
});

describe('departments.js create form branches', () => {
  it('create success reloads the page', async () => {
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('create failure with server message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'اسم مكرر' }) });
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('اسم مكرر');
  });

  it('create failure without server message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('حدث خطأ في إضافة القسم');
  });

  it('create non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('create without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('create with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    await loadModule('static/js/pages/super_admin/departments.js');
    const form = document.getElementById('addDepartmentForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/departments/create');
  });

  it('missing add form element does not crash the module', async () => {
    document.getElementById('addDepartmentForm').remove();
    await expect(loadModule('static/js/pages/super_admin/departments.js')).resolves.toBeDefined();
  });
});
