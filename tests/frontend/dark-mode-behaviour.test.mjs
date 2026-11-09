import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

// dark-mode.js applies the OS/theme choice at load time, persists only
// user-driven toggles, and follows OS theme changes while the user has
// no stored choice.
describe('dark-mode.js', () => {
  const STORAGE_KEY = 'azad-theme';

  function setStored(value) {
    if (value === null) {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, value);
    }
  }

  beforeEach(() => {
    vi.resetModules();
    document.documentElement.removeAttribute('data-theme');
    document.head.innerHTML = '';
    setStored(null);
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    });
  });

  test('no stored choice + OS light -> theme light, nothing persisted', async () => {
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  test('no stored choice + OS dark -> theme dark, nothing persisted', async () => {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  test('stored theme wins over OS preference and is re-persisted', async () => {
    setStored('dark');
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark');
  });

  test('stored light wins over OS dark', async () => {
    setStored('light');
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  test('toggleTheme flips light to dark and persists the choice', async () => {
    setStored('light');
    await loadModule('static/js/dark-mode.js');
    window.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark');
    window.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('light');
  });

  test('getTheme returns the current theme, defaulting to light', async () => {
    await loadModule('static/js/dark-mode.js');
    expect(window.getTheme()).toBe('light');
    document.documentElement.setAttribute('data-theme', 'dark');
    expect(window.getTheme()).toBe('dark');
  });

  test('matchMedia change listener re-applies OS theme while no stored choice', async () => {
    let changeHandler = null;
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn((event, cb) => {
        changeHandler = cb;
      }),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    changeHandler({ matches: true });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    changeHandler({ matches: false });
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  test('matchMedia change listener is ignored once the user chose a theme', async () => {
    let changeHandler = null;
    setStored('dark');
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn((event, cb) => {
        changeHandler = cb;
      }),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    changeHandler({ matches: false });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  test('localStorage getItem throwing falls back to OS matchMedia', async () => {
    const original = Object.getOwnPropertyDescriptor(Storage.prototype, 'getItem');
    Storage.prototype.getItem = vi.fn(() => {
      throw new Error('sandboxed');
    });
    try {
      await loadModule('static/js/dark-mode.js');
      expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    } finally {
      Storage.prototype.getItem = original.value;
    }
  });

  test('localStorage setItem throwing is swallowed, theme still applies', async () => {
    setStored('light');
    const original = Object.getOwnPropertyDescriptor(Storage.prototype, 'setItem');
    Storage.prototype.setItem = vi.fn(() => {
      throw new Error('quota');
    });
    try {
      await loadModule('static/js/dark-mode.js');
      window.toggleTheme();
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    } finally {
      Storage.prototype.setItem = original.value;
    }
  });

  test('meta theme-color is updated for dark and light', async () => {
    document.head.innerHTML = '<meta name="theme-color" content="#ffffff">';
    setStored('light');
    await loadModule('static/js/dark-mode.js');
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#ffffff');
    window.toggleTheme();
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#0f172a');
  });
});
