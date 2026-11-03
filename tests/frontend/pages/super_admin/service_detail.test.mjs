import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/service_detail.js');
});

describe('service_detail.js', () => {
  describe('activateService (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.activateService).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
  describe('deactivateService (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.deactivateService).toBeDefined();
    });
  });
});
