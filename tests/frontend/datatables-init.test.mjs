import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

let dtSpy;

beforeEach(() => {
  document.body.innerHTML = '<table id="tbl" data-dt="1"><thead><tr><th>A</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>';
  dtSpy = vi.fn();
  window.$ = vi.fn(() => ({ DataTable: dtSpy }));
  window.$.fn = { DataTable: dtSpy };
  window.$.DataTable = dtSpy;
});

describe('datatables-init.js', () => {
  it('initializes DataTable on data-dt tables', async () => {
    const { initDataTables } = await loadModule('static/js/datatables-init.js');
    initDataTables();
    expect(window.$).toHaveBeenCalled();
    expect(dtSpy).toHaveBeenCalled();
  });

  it('does nothing when DataTable is unavailable', async () => {
    window.$ = undefined;
    const { initDataTables } = await loadModule('static/js/datatables-init.js');
    expect(() => initDataTables()).not.toThrow();
  });
});