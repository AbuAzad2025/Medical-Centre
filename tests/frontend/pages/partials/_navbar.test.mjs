import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/partials/_navbar.js');
});

describe('_navbar.js', () => {
  describe('updateClock (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.updateClock).toBeDefined();
    });
  });
});
