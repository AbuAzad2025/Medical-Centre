import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="departmentsTable"><tbody></tbody></table>
    <input id="searchInput" type="text" />
    <form id="addDepartmentForm">
      <input name="name" value="Test Dept" />
    </form>
    <meta name="csrf-token" content="test-token" />
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('super_admin/departments.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/departments.js');
  });

  test('activateDepartment is a function', async () => {
    await loadScript('static/js/pages/super_admin/departments.js');
    expect(typeof activateDepartment).toBe('function');
  });

  test('deactivateDepartment is a function', async () => {
    await loadScript('static/js/pages/super_admin/departments.js');
    expect(typeof deactivateDepartment).toBe('function');
  });

  test('exportDepartments is a function', async () => {
    await loadScript('static/js/pages/super_admin/departments.js');
    expect(typeof exportDepartments).toBe('function');
  });
});
