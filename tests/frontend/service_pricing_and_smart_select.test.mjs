import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.TomSelect = vi.fn().mockImplementation(() => ({}));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('service_pricing.js', () => {
  it('deletePricing confirm posts to the delete endpoint and reloads', async () => {
    window.location = { reload: vi.fn() };
    document.head.innerHTML = '<meta name="csrf-token" content="tok-sp">';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, redirected: true });
    const mod = await loadModule('static/js/pages/super_admin/service_pricing.js');
    mod.deletePricing('7');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalled();
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('/super-admin/service-pricing/delete/7');
    expect(init.method).toBe('POST');
    expect(init.headers['X-CSRFToken']).toBe('tok-sp');
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('deletePricing cancel does not call fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    global.fetch = vi.fn();
    const mod = await loadModule('static/js/pages/super_admin/service_pricing.js');
    mod.deletePricing('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deletePricing with garbage id refuses before confirming', async () => {
    global.fetch = vi.fn();
    const mod = await loadModule('static/js/pages/super_admin/service_pricing.js');
    mod.deletePricing('abc!!');
    expect(window.Swal.fire).toHaveBeenCalledWith(expect.objectContaining({ icon: 'error' }));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deletePricing server failure shows error Swal', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="tok-sp">';
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, redirected: false });
    const mod = await loadModule('static/js/pages/super_admin/service_pricing.js');
    mod.deletePricing('7');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('exposes window.deletePricing', async () => {
    await loadModule('static/js/pages/super_admin/service_pricing.js');
    expect(typeof window.deletePricing).toBe('function');
  });
});

describe('smart-select.js', () => {
  it('initSmartSelect creates TomSelect for multiple select', async () => {
    document.body.innerHTML = '<select id="s" data-smart-select multiple data-max-options="10"><option>A</option><option>B</option></select>';
    const { initSmartSelect } = await loadModule('static/js/smart-select.js');
    const el = document.getElementById('s');
    const result = initSmartSelect(el);
    expect(window.TomSelect).toHaveBeenCalled();
    const opts = window.TomSelect.mock.calls[0][1];
    expect(opts.plugins).toEqual(['remove_button']);
    expect(opts.maxOptions).toBe(10);
    expect(result).toBeTruthy();
  });

  it('initSmartSelect creates TomSelect for single select with placeholder', async () => {
    document.body.innerHTML = '<select id="s2" data-smart-select data-placeholder="Pick"><option>A</option></select>';
    const { initSmartSelect } = await loadModule('static/js/smart-select.js');
    const el = document.getElementById('s2');
    initSmartSelect(el);
    const opts = window.TomSelect.mock.calls[0][1];
    expect(opts.plugins).toEqual(['dropdown_input', 'clear_button']);
    expect(opts.placeholder).toBe('Pick');
  });

  it('initSmartSelect returns existing tomselect when already initialized', async () => {
    document.body.innerHTML = '<select id="s3" data-smart-select></select>';
    const { initSmartSelect } = await loadModule('static/js/smart-select.js');
    const el = document.getElementById('s3');
    el.tomselect = { existing: true };
    expect(initSmartSelect(el)).toEqual({ existing: true });
    expect(window.TomSelect).not.toHaveBeenCalled();
  });

  it('initSmartSelect without TomSelect returns undefined', async () => {
    delete window.TomSelect;
    document.body.innerHTML = '<select id="s4" data-smart-select></select>';
    const { initSmartSelect } = await loadModule('static/js/smart-select.js');
    expect(initSmartSelect(document.getElementById('s4'))).toBeUndefined();
  });

  it('DOMContentLoaded initializes all [data-smart-select] elements', async () => {
    document.body.innerHTML = '<select data-smart-select><option>A</option></select><select data-smart-select><option>B</option></select>';
    await loadModule('static/js/smart-select.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.TomSelect).toHaveBeenCalledTimes(2);
  });

  it('initSmartSelectAll initializes all elements under root', async () => {
    document.body.innerHTML = '<div id="root"><select data-smart-select><option>A</option></select></div>';
    await loadModule('static/js/smart-select.js');
    window.initSmartSelectAll(document.getElementById('root'));
    expect(window.TomSelect).toHaveBeenCalledTimes(1);
  });

  it('initSmartSelectAll without root uses document', async () => {
    document.body.innerHTML = '<select data-smart-select><option>A</option></select>';
    await loadModule('static/js/smart-select.js');
    window.initSmartSelectAll();
    expect(window.TomSelect).toHaveBeenCalledTimes(1);
  });

  it('exposes window.initSmartSelect and initSmartSelectAll', async () => {
    await loadModule('static/js/smart-select.js');
    expect(typeof window.initSmartSelect).toBe('function');
    expect(typeof window.initSmartSelectAll).toBe('function');
  });
});