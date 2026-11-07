import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <i data-theme-icon></i>
    <button id="themeToggleBtn">Toggle</button>
  `;
  document.documentElement.removeAttribute('data-theme');
  localStorage.clear();
  window.API_ROUTES = { user_preferences: '/api/user/preferences' };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});

describe('theme-toggle.js', () => {
  it('DOMContentLoaded attaches click handler that toggles and persists', async () => {
    await loadModule('static/js/theme-toggle.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('themeToggleBtn').click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(global.fetch).toHaveBeenCalled();
  });

  it('currentTheme defaults to light', async () => {
    const { currentTheme } = await loadModule('static/js/theme-toggle.js');
    expect(currentTheme()).toBe('light');
  });

  it('currentTheme reads dark attribute', async () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    const { currentTheme } = await loadModule('static/js/theme-toggle.js');
    expect(currentTheme()).toBe('dark');
  });

  it('applyTheme switches to light', async () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    const { applyTheme } = await loadModule('static/js/theme-toggle.js');
    applyTheme('light');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('light');
  });

  it('applyTheme switches to dark', async () => {
    const { applyTheme } = await loadModule('static/js/theme-toggle.js');
    applyTheme('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
  });

  it('updateIcon swaps icon classes', async () => {
    const { updateIcon } = await loadModule('static/js/theme-toggle.js');
    updateIcon('dark');
    expect(document.querySelector('[data-theme-icon]').className).toBe('fas fa-sun');
    updateIcon('light');
    expect(document.querySelector('[data-theme-icon]').className).toBe('fas fa-moon');
  });

  it('persist posts theme to user preferences', async () => {
    const { persist } = await loadModule('static/js/theme-toggle.js');
    persist('dark');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).toHaveBeenCalledWith('/api/user/preferences', expect.objectContaining({ method: 'POST' }));
  });

  it('persist failure calls showToast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const { persist } = await loadModule('static/js/theme-toggle.js');
    persist('light');
    await new Promise(r => setTimeout(r, 20));
    expect(window.showToast).toHaveBeenCalled();
  });

});