import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/department_detail.js');
});

describe('department_detail.js', () => {
  describe('activateDepartment (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.activateDepartment).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
  describe('deactivateDepartment (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.deactivateDepartment).toBeDefined();
    });
  });
});
