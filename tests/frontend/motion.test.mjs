import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  window.__USER_PREFS__ = { ui: {} };
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
  await loadModule('static/js/motion.js');
});

describe('motion.js', () => {
  it('exposes __MOTION_ENABLED__ function', () => {
    expect(typeof window.__MOTION_ENABLED__).toBe('function');
  });

  it('returns true when no reduced motion preference', async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    await loadModule('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(true);
  });

  it('returns false when reduced motion is preferred', async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    await loadModule('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(false);
  });

  it('returns false when user pref is reduced', async () => {
    window.__USER_PREFS__ = { ui: { motion: 'reduced' } };
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    await loadModule('static/js/motion.js');
    expect(window.__MOTION_ENABLED__()).toBe(false);
  });
});
