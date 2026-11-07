import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = `
    <input id="orderSetName" value="Admission Bundle">
    <div class="order-set-item">
      <select class="item-type"><option value="medication">medication</option></select>
      <input class="item-name" value="Aspirin">
      <input class="item-code" value="ASA">
      <input class="item-dosage" value="325mg">
      <input class="item-qty" value="1">
      <input class="item-duration" value="7">
      <input type="checkbox" class="item-optional">
    </div>
  `;
  window.__M = [];
  window.API_ROUTES = {};
  window.csrfToken = 'test-csrf';
  window.escHtml = (s) => s;
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 9, advisories: [{ rule: 'allergy' }] }) });
}

beforeEach(async () => {
  setup();
  await loadModule('static/js/pages/clinical/order_sets.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('order_sets.js', () => {
  it('createOrderSet with no name shows toast', async () => {
    document.getElementById('orderSetName').value = '';
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(window.showToast).toHaveBeenCalledWith('Name is required', 'error');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('createOrderSet posts items and succeeds', async () => {
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(global.fetch).toHaveBeenCalled();
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain('/order-sets/api/create');
    expect(JSON.parse(opts.body).items[0].item_name).toBe('Aspirin');
  });

  it('createOrderSet failure shows error toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(window.showToast).toHaveBeenCalledWith('Error creating order set', 'error');
  });

  it('checkBPA returns advisories', async () => {
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    const out = await mod.checkBPA({ diagnosis: 'J06' });
    expect(out).toEqual([{ rule: 'allergy' }]);
    expect(global.fetch.mock.calls[0][0]).toContain('/order-sets/api/bpa/check');
  });

  it('checkBPA failure returns empty list', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    expect(await mod.checkBPA({ diagnosis: 'J06' })).toEqual([]);
  });
});