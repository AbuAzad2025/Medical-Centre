import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="servicesTable"><tbody></tbody></table>
    <input id="searchInput" type="text" />
    <form id="addServiceForm">
      <input name="name" value="Test Service" />
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

describe('super_admin/services.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/services.js');
  });

  test('activateService is a function', async () => {
    await loadScript('static/js/pages/super_admin/services.js');
    expect(typeof activateService).toBe('function');
  });

  test('deactivateService is a function', async () => {
    await loadScript('static/js/pages/super_admin/services.js');
    expect(typeof deactivateService).toBe('function');
  });

  test('exportServices is a function', async () => {
    await loadScript('static/js/pages/super_admin/services.js');
    expect(typeof exportServices).toBe('function');
  });
});
