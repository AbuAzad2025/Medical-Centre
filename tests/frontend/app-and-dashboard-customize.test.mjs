import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-app">
    <form id="f1"></form>
    <table id="t1" data-dt="1"><thead><tr><th>A</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>
  `;
  window.__csrfInitialized = false;
  window.UIPreferences = { persist: vi.fn().mockResolvedValue({ ok: true }) };
  window.API_ROUTES = { user_preferences: '/api/user/preferences' };
  window.showToast = vi.fn();
  window.notifications = { show: vi.fn() };
  window.$ = vi.fn((el) => ({ DataTable: vi.fn(() => ({ columns: { adjust: vi.fn() } })) }));
  window.$.fn = { DataTable: true, dataTable: { isDataTable: vi.fn(() => false) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('app.js', () => {
  it('initializes csrf by importing csrf.js', async () => {
    await loadModule('static/js/app.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.__csrfInitialized).toBe(true);
    expect(document.querySelector('#f1 input[name="csrf_token"]')).toBeTruthy();
  });

  it('still sets __csrfInitialized when csrf.js import path fails via fallback branch', async () => {
    window.__csrfInitialized = false;
    const { renameSync } = await import('fs');
    const real = 'static/js/csrf.js';
    const bak = 'static/js/csrf.js.bak';
    renameSync(real, bak);
    try {
      await loadModule('static/js/app.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 30));
      expect(window.__csrfInitialized).toBe(true);
      expect(document.querySelector('#f1 input[name="csrf_token"]')).toBeTruthy();
    } finally {
      renameSync(bak, real);
    }
  });
});

describe('dashboard-customize.js', () => {
  it('csrf reads meta content', async () => {
    const { csrf } = await loadModule('static/js/dashboard-customize.js');
    expect(csrf()).toBe('csrf-app');
  });

  it('csrf returns empty when meta missing', async () => {
    document.body.innerHTML = '';
    const { csrf } = await loadModule('static/js/dashboard-customize.js');
    expect(csrf()).toBe('');
  });

  it('collectHidden collects unchecked toggles', async () => {
    document.body.innerHTML = `
      <input type="checkbox" class="cc-widget-toggle" value="vitals" checked>
      <input type="checkbox" class="cc-widget-toggle" value="labs">
    `;
    const { collectHidden } = await loadModule('static/js/dashboard-customize.js');
    expect(collectHidden()).toEqual(['labs']);
  });

  it('save uses UIPreferences persist when available', async () => {
    const { save } = await loadModule('static/js/dashboard-customize.js');
    await save(['labs']);
    expect(window.UIPreferences.persist).toHaveBeenCalledWith({ dashboard: { hidden_widgets: ['labs'] } });
  });

  it('save falls back to fetch when no UIPreferences', async () => {
    delete window.UIPreferences;
    const { save } = await loadModule('static/js/dashboard-customize.js');
    await save(['vitals']);
    expect(global.fetch).toHaveBeenCalledWith('/api/user/preferences', expect.objectContaining({ method: 'POST' }));
  });

  it('toggleWidgetVisibility hides widget for unchecked toggles', async () => {
    document.body.innerHTML = `
      <input type="checkbox" class="cc-widget-toggle" value="labs">
      <div data-widget="labs"></div>
      <div data-widget="other"></div>
    `;
    const { toggleWidgetVisibility } = await loadModule('static/js/dashboard-customize.js');
    toggleWidgetVisibility(['labs']);
    expect(document.querySelector('[data-widget="labs"]').style.display).toBe('none');
    expect(document.querySelector('[data-widget="other"]').style.display).toBe('');
  });

  it('DOMContentLoaded change handler persists hidden list and shows success', async () => {
    document.body.innerHTML = `
      <div id="ccWidgetToggles">
        <input type="checkbox" class="cc-widget-toggle" value="labs" checked>
      </div>
      <div data-widget="labs"></div>
    `;
    await loadModule('static/js/dashboard-customize.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const cb = document.querySelector('.cc-widget-toggle');
    cb.checked = false;
    cb.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.UIPreferences.persist).toHaveBeenCalled();
    expect(window.notifications.show).toHaveBeenCalledWith(expect.any(String), 'success');
    expect(document.querySelector('[data-widget="labs"]').style.display).toBe('none');
  });

  it('change handler persists failure shows error notification', async () => {
    document.body.innerHTML = `
      <div id="ccWidgetToggles">
        <input type="checkbox" class="cc-widget-toggle" value="labs" checked>
      </div>
    `;
    window.UIPreferences.persist = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/dashboard-customize.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const cb = document.querySelector('.cc-widget-toggle');
    cb.checked = false;
    cb.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.notifications.show).toHaveBeenCalledWith(expect.any(String), 'error');
  });

  it('panel with no toggles is a no-op', async () => {
    document.body.innerHTML = `<div id="ccWidgetToggles"></div>`;
    await loadModule('static/js/dashboard-customize.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('ccWidgetToggles').dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 10));
    expect(window.UIPreferences.persist).not.toHaveBeenCalled();
  });

  it('without panel does not throw', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/dashboard-customize.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });

  it('exposes globals', async () => {
    await loadModule('static/js/dashboard-customize.js');
    expect(typeof window.csrf).toBe('function');
    expect(typeof window.collectHidden).toBe('function');
    expect(typeof window.save).toBe('function');
    expect(typeof window.toggleWidgetVisibility).toBe('function');
  });
});