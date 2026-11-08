import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<meta name="csrf-token" content="csrf-ui">';
  window.localStorage.clear();
  delete window.__USER_PREFS__;
  delete window.showToast;
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ui-preferences.js fallback arms', () => {
  it('persist posts to the default endpoint when API_ROUTES key is missing', async () => {
    const { persist } = await loadModule('static/js/ui-preferences.js');
    persist({ density: 'compact' });
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls[0][0]).toBe('/api/user/preferences');
  });

  it('persist failure without showToast resolves silently', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const { persist } = await loadModule('static/js/ui-preferences.js');
    await expect(persist({ density: 'compact' })).resolves.toBeUndefined();
  });

  it('applyDensity with falsy value falls back to normal', async () => {
    const { applyDensity } = await loadModule('static/js/ui-preferences.js');
    document.documentElement.setAttribute('data-density', 'compact');
    applyDensity('');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
  });

  it('applyRadius with falsy value falls back to md', async () => {
    const { applyRadius } = await loadModule('static/js/ui-preferences.js');
    document.documentElement.setAttribute('data-radius', 'sm');
    applyRadius('');
    expect(document.documentElement.hasAttribute('data-radius')).toBe(false);
  });

  it('localStorage failures do not break applyDensity', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: () => null, setItem() { throw new Error('quota'); }, clear() {} },
      configurable: true,
    });
    const { applyDensity } = await loadModule('static/js/ui-preferences.js');
    expect(() => applyDensity('compact')).not.toThrow();
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });

  it('localStorage failures do not break applyRadius', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: () => null, setItem() { throw new Error('quota'); }, clear() {} },
      configurable: true,
    });
    const { applyRadius } = await loadModule('static/js/ui-preferences.js');
    expect(() => applyRadius('sm')).not.toThrow();
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });

  it('applyDensity without __USER_PREFS__ does not crash', async () => {
    const { applyDensity } = await loadModule('static/js/ui-preferences.js');
    expect(() => applyDensity('compact')).not.toThrow();
  });

  it('applyRadius without __USER_PREFS__ does not crash', async () => {
    const { applyRadius } = await loadModule('static/js/ui-preferences.js');
    expect(() => applyRadius('sm')).not.toThrow();
  });
});
