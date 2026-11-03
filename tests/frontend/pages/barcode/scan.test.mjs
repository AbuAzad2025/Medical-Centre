import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/barcode/scan.js');
});

describe('scan.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('submitScan (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.submitScan).toBeDefined();
    });
  });
});
