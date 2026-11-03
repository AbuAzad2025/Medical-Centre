import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/accountant/pending_payments.js');
});

describe('pending_payments.js', () => {
  describe('refreshPage (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.refreshPage).toBeDefined();
    });
  });
});
