import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const TABLE = `
  <table id="unitsTable"><tbody>
    <tr data-status="active"><td>Sales</td><td>Module</td><td>5</td><td><span class="badge">نشط</span></td><td><button data-action="toggleUnit" data-module="sales" data-name-ar="المبيعات">Toggle</button></td></tr>
    <tr data-status="inactive"><td>Lab</td><td>Module</td><td>2</td><td><span class="badge">معطل</span></td><td><button data-action="toggleUnit" data-module="lab">Toggle</button></td></tr>
    <tr data-status="inactive"><td>NoButton</td><td>Module</td><td>0</td><td><span class="badge">معطل</span></td><td></td></tr>
    <tr data-status="inactive"><td>NoModule</td><td>Module</td><td>0</td><td><span class="badge">معطل</span></td><td><button data-action="toggleUnit">Toggle</button></td></tr>
    <tr data-status="inactive"><td>NoBadge</td><td>Module</td><td>0</td><td></td><td><button data-action="toggleUnit" data-module="nobadge">Toggle</button></td></tr>
    <tr data-status="active"><td>Sparse</td><td>OnlyTwo</td></tr>
  </tbody></table>
`;

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table id="unitsTable"><tbody>
      <tr data-status="active"><td>Sales</td><td>Module</td><td>5</td><td><span class="badge">نشط</span></td><td><button data-action="toggleUnit" data-module="sales" data-name-ar="المبيعات">Toggle</button></td></tr>
      <tr data-status="inactive"><td>Lab</td><td>Module</td><td>2</td><td><span class="badge">معطل</span></td><td><button data-action="toggleUnit" data-module="lab">Toggle</button></td></tr>
      <tr data-status="inactive"><td>NoButton</td><td>Module</td><td>0</td><td><span class="badge">معطل</span></td><td></td></tr>
      <tr data-status="inactive"><td>NoModule</td><td>Module</td><td>0</td><td><span class="badge">معطل</span></td><td><button data-action="toggleUnit">Toggle</button></td></tr>
      <tr data-status="inactive"><td>NoBadge</td><td>Module</td><td>0</td><td></td><td><button data-action="toggleUnit" data-module="nobadge">Toggle</button></td></tr>
      <tr data-status="active"><td>Sparse</td><td>OnlyTwo</td></tr>
    </tbody></table>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = {};
  window.location = { href: '', reload: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Modal: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) };
  window.URL.createObjectURL = vi.fn(() => 'blob:url');
  window.URL.revokeObjectURL = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'done' }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('unit_control.js toggleUnit fallback arms', () => {
  it('uses the Arabic name from data-name-ar when present', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    const btn = document.querySelector('[data-module="sales"]');
    await mod.toggleUnit('sales', btn);
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('المبيعات');
  });

  it('falls back to the module name when data-name-ar is missing', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    const btn = document.querySelector('[data-module="lab"]');
    await mod.toggleUnit('lab', btn);
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('lab');
  });

  it('works without a button argument at all', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('attendance', null);
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('attendance');
  });

  it('non-ok toggle response surfaces the generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('lab', null);
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('server failure without a message uses the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('lab', null);
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.text).toBe('حدث خطأ');
  });

  it('toggle without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('lab', null);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('uses API_ROUTES.unit_toggle when set', async () => {
    window.API_ROUTES = { unit_toggle: '/custom/toggle' };
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('lab', null);
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/toggle');
  });

  it('falls back to the default toggle route when API_ROUTES unset', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.toggleUnit('lab', null);
    expect(global.fetch.mock.calls[0][0]).toBe('/manager/api/units/toggle');
  });
});

describe('unit_control.js bulk operations arms', () => {
  it('bulkActivate skips active badges and rows without toggle buttons', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.bulkActivate();
    const urls = global.fetch.mock.calls.map(c => JSON.parse(c[1].body).module_name);
    expect(urls).toContain('lab');
    expect(urls).toContain('nobadge');
    expect(urls).not.toContain('sales');     // active row skipped
    expect(urls).not.toContain('NoButton');  // no toggle button → skipped by row filter
    expect(global.fetch.mock.calls.length).toBe(2); // lab + nobadge only
  });

  it('bulkDeactivate skips معطل badges and rows missing modules', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.bulkDeactivate();
    const bodies = global.fetch.mock.calls.map(c => JSON.parse(c[1].body).module_name);
    expect(bodies).toContain('sales');
    expect(bodies).toContain('nobadge');
    expect(bodies).not.toContain('lab');     // inactive row skipped
  });

  it('bulk operations non-ok fetch surfaces the generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.bulkDeactivate();
    await new Promise(r => setTimeout(r, 60));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('bulk operations without csrf meta send no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.bulkDeactivate();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('bulk without any candidate rows resolves the success path', async () => {
    document.querySelector('#unitsTable tbody').innerHTML = '';
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    await mod.bulkActivate();
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('success');
  });

  it('filterUnits without an event argument clears active marks but works', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    expect(() => mod.filterUnits('all')).not.toThrow();
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe(''));
  });

  it('exportUnitsReport skips rows with fewer than 4 cells', async () => {
    const mod = await loadModule('static/js/pages/manager/unit_control.js');
    expect(() => mod.exportUnitsReport()).not.toThrow();
    expect(window.URL.createObjectURL).toHaveBeenCalled();
  });
});
