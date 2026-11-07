import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = '<meta name="csrf-token" content="test-csrf">';
  window.__M = [];
  window.escHtml = (s) => s;
  window.API_ROUTES = {
    activate_department: '/super-admin/activate-department/0',
    deactivate_department: '/super-admin/deactivate-department/0',
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
  await loadModule('static/js/pages/super_admin/department_detail.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('department_detail.js', () => {
  it('activateDepartment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/activate-department/7');
  });

  it('activateDepartment fetch error shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('activateDepartment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.activateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deactivateDepartment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/deactivate-department/7');
  });

  it('deactivateDepartment fetch error shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('deactivateDepartment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_detail.js');
    mod.deactivateDepartment('7');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});