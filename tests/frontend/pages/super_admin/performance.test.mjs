import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/performance.js');
});

describe('performance.js', () => {
  describe('updatePerformanceData (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.updatePerformanceData).toBeDefined();
    });
  });
});
