import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/service_pricing.js');
});

describe('service_pricing.js', () => {
  describe('deletePricing (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.deletePricing).toBeDefined();
    });
  });
});
