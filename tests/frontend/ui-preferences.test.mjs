import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  document.documentElement.removeAttribute('data-density');
  document.documentElement.removeAttribute('data-radius');
  localStorage.clear();
  window.__USER_PREFS__ = {};
  window.fetch = vi.fn().mockResolvedValue({ ok: true });
  window.showToast = vi.fn();
  loadScript('static/js/ui-preferences.js');
});

describe('ui-preferences.js', () => {
  describe('applyDensity', () => {
    it('sets data-density attribute for non-normal values', () => {
      window.UIPreferences.applyDensity('compact');
      expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    });
    it('removes data-density for normal', () => {
      document.documentElement.setAttribute('data-density', 'compact');
      window.UIPreferences.applyDensity('normal');
      expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    });
    it('saves to localStorage', () => {
      window.UIPreferences.applyDensity('comfortable');
      expect(localStorage.getItem('ui_density')).toBe('comfortable');
    });
  });

  describe('applyRadius', () => {
    it('sets data-radius attribute for non-md values', () => {
      window.UIPreferences.applyRadius('lg');
      expect(document.documentElement.getAttribute('data-radius')).toBe('lg');
    });
    it('removes data-radius for md', () => {
      document.documentElement.setAttribute('data-radius', 'lg');
      window.UIPreferences.applyRadius('md');
      expect(document.documentElement.hasAttribute('data-radius')).toBe(false);
    });
    it('saves to localStorage', () => {
      window.UIPreferences.applyRadius('sm');
      expect(localStorage.getItem('ui_radius')).toBe('sm');
    });
  });
});
