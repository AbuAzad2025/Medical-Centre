import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/nurse/dashboard_new.js');
});

describe('dashboard_new.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('d (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.d).toBeDefined();
    });
  });
  describe('el (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.el).toBeDefined();
    });
  });
});
