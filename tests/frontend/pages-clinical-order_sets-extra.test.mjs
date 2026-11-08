import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <input id="orderSetName" value="Bundle">
    <div class="order-set-item"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {};
  window.csrfToken = 'csrf-os';
  window.escHtml = (s) => String(s || '');
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 9, advisories: [{ rule: 'x' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('clinical/order_sets.js extra branches', () => {
  it('createOrderSet with incomplete item row uses defaults', async () => {
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.items[0].item_type).toBe('medication');
    expect(body.items[0].default_quantity).toBe(1);
    expect(body.items[0].default_duration).toBe(7);
    expect(body.items[0].is_optional).toBe(false);
  });

  it('createOrderSet without orderSetName element shows required toast', async () => {
    document.getElementById('orderSetName').remove();
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(window.showToast).toHaveBeenCalledWith('Name is required', 'error');
  });

  it('createOrderSet non-ok response shows error toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(window.showToast).toHaveBeenCalledWith('Error creating order set', 'error');
  });

  it('createOrderSet success without toast does not throw', async () => {
    delete window.showToast;
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    expect(() => mod.createOrderSet()).not.toThrow();
  });

  it('createOrderSet response without id does not toast or reload', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(window.showToast).not.toHaveBeenCalled();
  });

  it('createOrderSet non-ok and no showToast does not throw', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    expect(() => mod.createOrderSet()).not.toThrow();
  });

  it('checkBPA non-ok response throws internally and returns []', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    expect(await mod.checkBPA({ diagnosis: 'x' })).toEqual([]);
  });

  it('checkBPA response without advisories returns []', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    expect(await mod.checkBPA({ diagnosis: 'x' })).toEqual([]);
  });

  it('checkBPA without csrfToken still sends empty token', async () => {
    delete window.csrfToken;
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.checkBPA({ diagnosis: 'x' });
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('');
  });

  it('createOrderSet without csrfToken sends empty token', async () => {
    delete window.csrfToken;
    const mod = await loadModule('static/js/pages/clinical/order_sets.js');
    await mod.createOrderSet();
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('');
  });
});