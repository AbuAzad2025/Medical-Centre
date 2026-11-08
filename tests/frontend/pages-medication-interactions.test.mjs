import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.__M = [];
  window.__M0__ = 'csrf-interaction';
  window.API_ROUTES = { medication_toggle_interaction: '/medication/interactions/0/toggle' };
  window.escHtml = (s) => s;
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.location = { reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('medication/interactions.js', () => {
  it('toggleInteraction posts and reloads', async () => {
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('7');
    expect(String(global.fetch.mock.calls[0][0])).toContain('/medication/interactions/7/toggle');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('toggleInteraction with non-ok response shows toast and does not reload', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('7');
    expect(window.showToast).toHaveBeenCalled();
    expect(window.location.reload).not.toHaveBeenCalled();
  });

  it('toggleInteraction network failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('7');
    expect(window.showToast).toHaveBeenCalled();
  });

  it('toggleInteraction network failure without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('7');
    expect(window.alert).toHaveBeenCalled();
  });

  it('uses default URL when API_ROUTES missing', async () => {
    window.API_ROUTES = undefined;
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('9');
    expect(String(global.fetch.mock.calls[0][0])).toContain('/medication/interactions/9/toggle');
  });

  it('exposes window.toggleInteraction', async () => {
    await loadModule('static/js/pages/medication/interactions.js');
    expect(typeof window.toggleInteraction).toBe('function');
  });
});
describe('interactions.js API_ROUTES key fallback arms', () => {
  it('API_ROUTES object without the toggle key falls back to the default URL', async () => {
    window.API_ROUTES = {}; // defined but missing the key
    const mod = await loadModule('static/js/pages/medication/interactions.js');
    await mod.toggleInteraction('11');
    expect(String(global.fetch.mock.calls[0][0])).toContain('/medication/interactions/11/toggle');
  });
});
