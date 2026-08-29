import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.__USER_PREFS__ = { ui: {} };
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
  loadScript('static/js/motion.js');
});

describe('motion.js', () => {
  it('exposes __MOTION_ENABLED__ function', () => {
    expect(typeof window.__MOTION_ENABLED__).toBe('function');
  });

  it('returns true when no reduced motion preference', () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    loadScript('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(true);
  });

  it('returns false when reduced motion is preferred', () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    loadScript('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(false);
  });

  it('returns false when user pref is reduced', () => {
    window.__USER_PREFS__ = { ui: { motion: 'reduced' } };
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    loadScript('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(false);
  });
});
