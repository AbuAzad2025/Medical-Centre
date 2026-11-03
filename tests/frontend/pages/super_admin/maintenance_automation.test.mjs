import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/maintenance_automation.js');
});

describe('maintenance_automation.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('saveBtn (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.saveBtn).toBeDefined();
    });
  });
});
