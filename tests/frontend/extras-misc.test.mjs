import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('digits-ar.js', () => {
  it('normalizeArabicDigits converts Arabic-Indic digits in text nodes', async () => {
    document.body.innerHTML = '<p id="p">٣٤٢ ٥</p>';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    expect(document.getElementById('p').textContent).toBe('342 5');
  });

  it('normalizeArabicDigits skips text without target digits', async () => {
    document.body.innerHTML = '<p>hello 123</p>';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    expect(document.querySelector('p').textContent).toBe('hello 123');
  });

  it('normalizeArabicDigits on missing root does nothing', async () => {
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    expect(() => normalizeArabicDigits(null)).not.toThrow();
    expect(() => normalizeArabicDigits(undefined)).not.toThrow();
  });

  it('normalizeArabicDigits attaches input handler that converts digits', async () => {
    document.body.innerHTML = '<input type="text" id="inp"><textarea id="ta"></textarea>';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    const inp = document.getElementById('inp');
    inp.value = '١٢٣٤٥٦٧٨٩٠';
    inp.dispatchEvent(new Event('input'));
    expect(inp.value).toBe('1234567890');
    const ta = document.getElementById('ta');
    ta.value = '٣٤٢';
    ta.dispatchEvent(new Event('input'));
    expect(ta.value).toBe('342');
  });

  it('normalizeArabicDigits re-attaches handler when called twice', async () => {
    document.body.innerHTML = '<input type="text" id="inp">';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    normalizeArabicDigits(document.body);
    const inp = document.getElementById('inp');
    inp.value = '١٢٣';
    inp.dispatchEvent(new Event('input'));
    expect(inp.value).toBe('123');
  });
});

describe('motion.js', () => {
  it('motionEnabled returns true by default', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false }));
    const { motionEnabled } = await loadModule('static/js/motion.js');
    expect(motionEnabled()).toBe(true);
  });

  it('motionEnabled false when reduced motion preferred', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true }));
    const { motionEnabled } = await loadModule('static/js/motion.js');
    expect(motionEnabled()).toBe(false);
  });

  it('motionEnabled false when user preference is reduced', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false }));
    window.__USER_PREFS__ = { ui: { motion: 'reduced' } };
    const { motionEnabled } = await loadModule('static/js/motion.js');
    expect(motionEnabled()).toBe(false);
  });

  it('runEntranceAnimations calls gsap.from when motion enabled', async () => {
    document.body.innerHTML = '<div class="animate-in">x</div>';
    window.gsap = { from: vi.fn() };
    window.matchMedia = vi.fn(() => ({ matches: false }));
    delete window.__USER_PREFS__;
    const { runEntranceAnimations } = await loadModule('static/js/motion.js');
    runEntranceAnimations();
    expect(window.gsap.from).toHaveBeenCalled();
  });

  it('runEntranceAnimations does nothing when no .animate-in items', async () => {
    window.gsap = { from: vi.fn() };
    window.matchMedia = vi.fn(() => ({ matches: false }));
    const { runEntranceAnimations } = await loadModule('static/js/motion.js');
    expect(() => runEntranceAnimations()).not.toThrow();
    expect(window.gsap.from).not.toHaveBeenCalled();
  });

  it('runEntranceAnimations does nothing when gsap is undefined', async () => {
    document.body.innerHTML = '<div class="animate-in">x</div>';
    window.matchMedia = vi.fn(() => ({ matches: false }));
    delete window.gsap;
    const { runEntranceAnimations } = await loadModule('static/js/motion.js');
    expect(() => runEntranceAnimations()).not.toThrow();
  });

  it('motionEnabled with matchMedia throwing still returns true', async () => {
    window.matchMedia = vi.fn(() => { throw new Error('no mm'); });
    const { motionEnabled } = await loadModule('static/js/motion.js');
    expect(motionEnabled()).toBe(true);
  });

  it('exposes window.motionEnabled and runEntranceAnimations', async () => {
    await loadModule('static/js/motion.js');
    expect(typeof window.motionEnabled).toBe('function');
    expect(typeof window.runEntranceAnimations).toBe('function');
  });
});

describe('dark-mode.js', () => {
  it('applies stored theme from localStorage', async () => {
    localStorage.setItem('azad-theme', 'dark');
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('applies light theme by default when system prefers light', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    // A system-derived theme is not persisted: the page must keep following
    // OS theme changes until the user actually picks one via the toggle.
    expect(localStorage.getItem('azad-theme')).toBeNull();
  });

  it('applies dark theme when system prefers dark', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('window.toggleTheme toggles between themes', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    localStorage.setItem('azad-theme', 'light');
    document.documentElement.setAttribute('data-theme', 'light');
    window.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('azad-theme')).toBe('dark');
  });

  it('window.getTheme returns current theme', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    expect(window.getTheme()).toBe('dark');
  });

  it('updates theme-color meta when present', async () => {
    document.head.innerHTML = '<meta name="theme-color" content="#ffffff">';
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/dark-mode.js');
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#0f172a');
  });

  it('theme change handler applies dark when system switches to dark and no stored preference', async () => {
    let changeCb;
    window.matchMedia = vi.fn((q) => ({
      matches: false,
      addEventListener: vi.fn((ev, cb) => { if (ev === 'change') changeCb = cb; }),
      removeEventListener: vi.fn(),
    }));
    await loadModule('static/js/dark-mode.js');
    localStorage.removeItem('azad-theme');
    changeCb({ matches: true });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('theme change handler ignores when stored preference exists', async () => {
    let changeCb;
    window.matchMedia = vi.fn((q) => ({
      matches: false,
      addEventListener: vi.fn((ev, cb) => { if (ev === 'change') changeCb = cb; }),
      removeEventListener: vi.fn(),
    }));
    await loadModule('static/js/dark-mode.js');
    localStorage.setItem('azad-theme', 'light');
    document.documentElement.setAttribute('data-theme', 'light');
    changeCb({ matches: true });
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});