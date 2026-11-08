import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input id="searchInput">
    <table id="servicesTable">
      <thead><tr><th>Name</th></tr></thead>
      <tbody><tr><td>Consultation</td></tr><tr><td>Lab test</td></tr></tbody>
    </table>
    <form id="addServiceForm">
      <input name="name" value="Procedure">
      <button type="submit">Add</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {
    view_service: '/super-admin/service/0',
    edit_service: '/super-admin/edit-service/0',
    service_pricing: '/super-admin/service-pricing/0',
    activate_service: '/super-admin/activate-service/0',
    deactivate_service: '/super-admin/deactivate-service/0',
    export_services: '/super-admin/export-services',
    create_service: '/super-admin/services/create',
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

describe('services.js search branches', () => {
  it('filters rows by the search term (case insensitive)', async () => {
    await loadModule('static/js/pages/super_admin/services.js');
    const input = document.getElementById('searchInput');
    input.value = 'LAB';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#servicesTable tbody tr');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
  });

  it('no match hides every row; clearing restores all rows', async () => {
    await loadModule('static/js/pages/super_admin/services.js');
    const input = document.getElementById('searchInput');
    input.value = 'zzz';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#servicesTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe('none'));
    input.value = '';
    input.dispatchEvent(new Event('input'));
    rows.forEach(r => expect(r.style.display).toBe(''));
  });

  it('missing searchInput element does not crash the module', async () => {
    document.getElementById('searchInput').remove();
    await expect(loadModule('static/js/pages/super_admin/services.js')).resolves.toBeDefined();
  });
});

describe('services.js navigation fallback arms', () => {
  it('viewService falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.viewService('3');
    expect(window.location.href).toBe('/super-admin/service/3');
  });

  it('editService falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.editService('3');
    expect(window.location.href).toBe('/super-admin/edit-service/3');
  });

  it('managePricing falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.managePricing('3');
    expect(window.location.href).toBe('/super-admin/service-pricing/3');
  });

  it('exportServices falls back to the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.exportServices();
    expect(window.open).toHaveBeenCalledWith('/super-admin/export-services', '_blank');
  });
});

describe('services.js activate/deactivate branches', () => {
  it('cancelled activation does not fetch and does not reload', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('activation success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('activation failure shows the error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation network failure triggers the catch error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activation without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('activation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/activate-service/3');
  });

  it('cancelled deactivation does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('3');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivation failure shows the error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deactivation non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('deactivation with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('3');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/deactivate-service/3');
  });
});

describe('services.js create form branches', () => {
  it('create success reloads the page', async () => {
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('create failure with server message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'مكرر' }) });
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('مكرر');
  });

  it('create failure without server message still shows the prefix', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('حدث خطأ في إضافة الخدمة');
  });

  it('create non-ok response triggers the catch error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('create without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('create with unset API_ROUTES calls the default route', async () => {
    delete window.API_ROUTES;
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/super-admin/services/create');
  });

  it('missing add form element does not crash the module', async () => {
    document.getElementById('addServiceForm').remove();
    await expect(loadModule('static/js/pages/super_admin/services.js')).resolves.toBeDefined();
  });
});
