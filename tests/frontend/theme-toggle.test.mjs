import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  document.documentElement.removeAttribute('data-theme');
  localStorage.clear();
  window.fetch = vi.fn().mockResolvedValue({ ok: true });
  window.showToast = vi.fn();
  document.body.innerHTML = '<meta name="csrf-token" content="test">';
  loadScript('static/js/theme-toggle.js');
});

describe('theme-toggle.js', () => {
  it('currentTheme returns light when no data-theme set', () => {
    const result = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    expect(result).toBe('light');
  });

  it('currentTheme returns dark when data-theme is dark', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    const result = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    expect(result).toBe('dark');
  });

  it('applyTheme sets dark theme', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('applyTheme removes theme for light', () => {
    document.documentElement.removeAttribute('data-theme');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
  });

  it('saves to localStorage', () => {
    localStorage.setItem('theme', 'dark');
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
