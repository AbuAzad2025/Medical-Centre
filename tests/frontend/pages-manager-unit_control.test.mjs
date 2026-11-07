import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function row(name, type, users, status, statusBadgeAlready = 'نشط') {
  return `<tr data-status="${status}"><td>${name}</td><td>${type}</td><td>${users}</td><td><span class="badge">${statusBadgeAlready}</span></td><td><button data-action="toggleUnit" data-module="${name}" data-name-ar="${name}">Toggle</button></td></tr>`;
}

function mockRows() {
  return `
    <table id="unitsTable"><tbody>
      ${row('Attendance', 'HR', '10', 'active', 'نشط')}
      ${row('Inventory', 'Ops', '3', 'inactive', 'معطل')}
    </tbody></table>
    <div><button id="btnActivateMonthly"></button></div>
  `;
}

beforeEach(async () => {
  document.body.innerHTML = mockRows();
  try { localStorage.clear(); } catch (e) {}
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
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'تم' }) });
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
  try { Object.defineProperty(window.location, 'reload', { value: vi.fn(), configurable: true, writable: true }); } catch (e) { /* keep jsdom */ }
  document.body.innerHTML += '<a id="dl" href="#"></a>';
  try { await loadModule('static/js/pages/manager/unit_control.js'); } catch (e) { /* ok */ }
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('unit_control.js', () => {
  it('refreshUnits does not throw', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    expect(() => mod.refreshUnits()).not.toThrow();
  });

  it('exportUnitsReport builds CSV and triggers download', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.exportUnitsReport();
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });

  it('toggleUnit posts to toggle url on confirm', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    const btn = document.querySelector('[data-action="toggleUnit"]');
    await mod.toggleUnit('Attendance', btn);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('toggleUnit does nothing when user cancels', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('Attendance', null);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('bulkActivate activates all inactive units', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkActivate();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('bulkActivate does nothing when user cancels', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkActivate();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('bulkDeactivate deactivates all active units', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkDeactivate();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('bulkDeactivate does nothing when user cancels', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkDeactivate();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('bulkRestart confirms then delegates to bulkActivate', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkRestart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('bulkRestart does nothing when user cancels', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkRestart();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('bulkExport calls exportUnitsReport', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.bulkExport();
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('filterUnits filters active rows', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    const btn = document.createElement('button');
    const e = { target: btn };
    mod.filterUnits('active', e);
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterUnits shows all rows', async () => {
    const mod = await import('../../static/js/pages/manager/unit_control.js');
    mod.filterUnits('all', null);
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('DOMContentLoaded attaches all declared actions', async () => {
    document.body.innerHTML = `
      <table id="unitsTable"><tbody>${row('Attendance','HR','1','active','نشط')}</tbody></table>
      <button data-action="bulk-activate">activate</button>
      <button data-action="bulk-deactivate">deactivate</button>
      <button data-action="bulk-restart">restart</button>
      <button data-action="bulk-export">export</button>
      <button data-action="export-units-report">report</button>
      <button data-action="refresh-units">refresh</button>
      <button data-action="filter-units" data-value="all">filter</button>
    `;
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelectorAll('[data-action]').forEach(btn => btn.click());
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});
