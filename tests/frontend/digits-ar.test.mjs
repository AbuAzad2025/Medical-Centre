import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/digits-ar.js');
});

describe('digits-ar.js', () => {
  describe('_digitHandlers (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window._digitHandlers).toBeDefined();
    });
  });
  describe('map (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.map).toBeDefined();
    });
  });
});
