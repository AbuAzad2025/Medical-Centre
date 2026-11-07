import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="addStaffForm">
      <input id="user_id" name="user_id" value="17">
      <button type="submit">Add</button>
    </form>
  `;
  window.__M0__ = '7';
  window.__M1__ = '7';
  window.__M = [];
  window.escHtml = (s) => s;
  window.API_ROUTES = {};
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
  await loadModule('static/js/pages/super_admin/department_staff.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('department_staff.js', () => {
  it('addStaffForm submission posts to add endpoint', async () => {
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/department-staff/7/add');
  });

  it('addStaffForm failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.getElementById('addStaffForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('removeFromDepartment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    mod.removeFromDepartment('17');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/super-admin/department-staff/7/remove');
  });

  it('removeFromDepartment failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    mod.removeFromDepartment('17');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('removeFromDepartment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/department_staff.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    mod.removeFromDepartment('17');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});