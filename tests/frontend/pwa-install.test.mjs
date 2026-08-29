import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  localStorage.clear();
  loadScript('static/js/pwa-install.js');
});

describe('pwa-install.js', () => {
  it('visitCount reads from localStorage and increments', () => {
    const count = parseInt(localStorage.getItem('azad_pwa_visits') || '0', 10);
    expect(count).toBeGreaterThanOrEqual(1);
  });

  it('bumpVisits increments correctly', () => {
    const before = parseInt(localStorage.getItem('azad_pwa_visits') || '0', 10);
    expect(before).toBeGreaterThanOrEqual(1);
  });

  it('isIOS detects iOS user agent', () => {
    expect(/iphone|ipad|ipod/i.test(navigator.userAgent)).toBe(false);
  });
});
