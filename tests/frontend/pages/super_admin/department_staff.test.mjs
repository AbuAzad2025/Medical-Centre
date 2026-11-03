import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/department_staff.js');
});

describe('department_staff.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('addStaffFormEl (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.addStaffFormEl).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
  describe('removeFromDepartment (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.removeFromDepartment).toBeDefined();
    });
  });
});
