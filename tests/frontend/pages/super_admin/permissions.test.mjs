import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <div id="permissionModal" style="display:none"></div>
    <div id="modalTitle"></div>
    <form id="permissionForm"></form>
    <meta name="csrf-token" content="test-token" />
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

describe('super_admin/permissions.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
  });

  test('createPermission is a function', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
    expect(typeof createPermission).toBe('function');
  });

  test('closeModal is a function', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
    expect(typeof closeModal).toBe('function');
  });

  test('createPermission shows modal', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
    createPermission();
    expect(document.getElementById('permissionModal').style.display).toBe('block');
  });

  test('closeModal hides modal', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
    document.getElementById('permissionModal').style.display = 'block';
    closeModal();
    expect(document.getElementById('permissionModal').style.display).toBe('none');
  });

  test('deletePermission is a function', async () => {
    await loadScript('static/js/pages/super_admin/permissions.js');
    expect(typeof deletePermission).toBe('function');
  });
});
