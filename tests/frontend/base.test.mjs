import { describe, it, expect, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  loadScript('static/js/base.js');
});

describe('base.js', () => {
  describe('escHtml (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.escHtml).toBe('function');
    });
    it('escapes HTML entities', () => {
      expect(window.escHtml('<script>')).toBe('&lt;script&gt;');
    });
    it('handles null', () => {
      expect(window.escHtml(null)).toBe('');
    });
    it('handles undefined', () => {
      expect(window.escHtml(undefined)).toBe('');
    });
  });
});
