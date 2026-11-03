import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/medication/supply_request_detail.js');
});

describe('supply_request_detail.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
});
