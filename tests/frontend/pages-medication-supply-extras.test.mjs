import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function supplyDom() {
  document.body.innerHTML = '<button id="approveBtn">Approve</button>';
}

beforeEach(() => {
  supplyDom();
  window.__M = [];
  window.__M0__ = 'csrf-supply';
  window.__M1__ = '/medication/supply/finish/7';
  window.escHtml = (s) => String(s ?? '');
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('supply_request_detail.js branches', () => {
  it('approve posts and reloads', async () => {
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('non-ok response shows the toast when showToast exists', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('non-ok response falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('network failure falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('module loads without an approve button', async () => {
    document.getElementById('approveBtn').remove();
    await expect(loadModule('static/js/pages/medication/supply_request_detail.js')).resolves.toBeDefined();
  });
});

describe('interactions.js fallback arms', () => {
  it('non-ok response without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('3');
    expect(window.alert).toHaveBeenCalled();
  });
});
