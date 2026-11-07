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

describe('super_admin/services.js', () => {
  it('viewService sets location.href', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.viewService('42');
    expect(window.location.href).toBe('/super-admin/service/42');
  });

  it('editService sets location.href', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.editService('42');
    expect(window.location.href).toBe('/super-admin/edit-service/42');
  });

  it('managePricing sets location.href', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.managePricing('42');
    expect(window.location.href).toBe('/super-admin/service-pricing/42');
  });

  it('activateService confirms and fetches activate', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/activate-service/42');
  });

  it('activateService failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activateService fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('activateService cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivateService confirms and fetches deactivate', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/deactivate-service/42');
  });

  it('deactivateService failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('exportServices opens export URL', async () => {
    const mod = await loadModule('static/js/pages/super_admin/services.js');
    mod.exportServices();
    expect(window.open).toHaveBeenCalledWith('/super-admin/export-services', '_blank');
  });

  it('search input filters rows by text', async () => {
    await loadModule('static/js/pages/super_admin/services.js');
    const input = document.getElementById('searchInput');
    input.value = 'consult';
    input.dispatchEvent(new Event('input'));
    const rows = document.querySelectorAll('#servicesTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('addServiceForm submits create', async () => {
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/super-admin/services/create');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
  });

  it('addServiceForm failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'dup' }) });
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('addServiceForm fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/services.js');
    const form = document.getElementById('addServiceForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});