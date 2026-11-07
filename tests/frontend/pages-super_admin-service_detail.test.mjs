import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = '<meta name="csrf-token" content="test-csrf">';
  window.__M = [];
  window.escHtml = (s) => s;
  window.API_ROUTES = {
    activate_service: '/super-admin/activate-service/0',
    deactivate_service: '/super-admin/deactivate-service/0',
  };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
  };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
}

beforeEach(async () => {
  setup();
  await loadModule('static/js/pages/super_admin/service_detail.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('service_detail.js', () => {
  it('activateService posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/activate-service/42');
  });

  it('activateService failure shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('activateService fetch error shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('activateService cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.activateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivateService posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/deactivate-service/42');
  });

  it('deactivateService failure shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('deactivateService fetch error shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('deactivateService cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/service_detail.js');
    mod.deactivateService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});