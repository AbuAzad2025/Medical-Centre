import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-ui">
    <select id="uiDensitySelect"><option value="normal">normal</option><option value="compact">compact</option></select>
    <select id="uiRadiusSelect"><option value="md">md</option><option value="sm">sm</option></select>
  `;
  localStorage.clear();
  window.API_ROUTES = { user_preferences: '/api/user/preferences' };
  window.__USER_PREFS__ = { density: 'compact', radius: 'sm' };
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ui-preferences.js', () => {
  it('csrf reads meta content', async () => {
    const { csrf } = await loadModule('static/js/ui-preferences.js');
    expect(csrf()).toBe('csrf-ui');
  });

  it('csrf returns empty when meta missing', async () => {
    document.body.innerHTML = '';
    const { csrf } = await loadModule('static/js/ui-preferences.js');
    expect(csrf()).toBe('');
  });

  it('persist posts updates to preferences endpoint', async () => {
    const { persist } = await loadModule('static/js/ui-preferences.js');
    persist({ density: 'compact' });
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).toHaveBeenCalledWith('/api/user/preferences', expect.objectContaining({ method: 'POST' }));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).density).toBe('compact');
  });

  it('persist failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const { persist } = await loadModule('static/js/ui-preferences.js');
    persist({ radius: 'sm' });
    await new Promise(r => setTimeout(r, 20));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('applyDensity normal removes attribute', async () => {
    document.documentElement.setAttribute('data-density', 'compact');
    const { applyDensity } = await loadModule('static/js/ui-preferences.js');
    applyDensity('normal');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(localStorage.getItem('ui_density')).toBe('normal');
    expect(window.__USER_PREFS__.density).toBe('normal');
  });

  it('applyDensity compact sets attribute', async () => {
    const { applyDensity } = await loadModule('static/js/ui-preferences.js');
    applyDensity('compact');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
  });

  it('applyRadius md removes attribute', async () => {
    document.documentElement.setAttribute('data-radius', 'sm');
    const { applyRadius } = await loadModule('static/js/ui-preferences.js');
    applyRadius('md');
    expect(document.documentElement.hasAttribute('data-radius')).toBe(false);
    expect(localStorage.getItem('ui_radius')).toBe('md');
    expect(window.__USER_PREFS__.radius).toBe('md');
  });

  it('applyRadius sm sets attribute', async () => {
    const { applyRadius } = await loadModule('static/js/ui-preferences.js');
    applyRadius('sm');
    expect(document.documentElement.getAttribute('data-radius')).toBe('sm');
  });

  it('bindSelect without element does nothing', async () => {
    const { bindSelect } = await loadModule('static/js/ui-preferences.js');
    expect(() => bindSelect('nonexistentSelect', () => {}, 'k')).not.toThrow();
  });

  it('changing the density select applies and persists', async () => {
    await loadModule('static/js/ui-preferences.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const select = document.getElementById('uiDensitySelect');
    select.value = 'normal';
    select.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 20));
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(global.fetch).toHaveBeenCalled();
  });

  it('changing the radius select applies and persists', async () => {
    await loadModule('static/js/ui-preferences.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const select = document.getElementById('uiRadiusSelect');
    select.value = 'md';
    select.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 20));
    expect(document.documentElement.hasAttribute('data-radius')).toBe(false);
    expect(global.fetch).toHaveBeenCalled();
  });

  it('DOMContentLoaded sets selects to stored prefs', async () => {
    await loadModule('static/js/ui-preferences.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('uiDensitySelect').value).toBe('compact');
    expect(document.getElementById('uiRadiusSelect').value).toBe('sm');
  });

  it('DOMContentLoaded without selects does not throw', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/ui-preferences.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });

  it('exposes window.UIPreferences', async () => {
    await loadModule('static/js/ui-preferences.js');
    expect(typeof window.UIPreferences.applyDensity).toBe('function');
    expect(typeof window.UIPreferences.applyRadius).toBe('function');
    expect(typeof window.UIPreferences.persist).toBe('function');
  });
});