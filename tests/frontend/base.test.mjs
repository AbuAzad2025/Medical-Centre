import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/base.js');
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
