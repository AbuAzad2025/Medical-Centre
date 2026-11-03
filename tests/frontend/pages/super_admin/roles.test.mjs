import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/roles.js');
});

describe('roles.js', () => {
  describe('editRole (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.editRole).toBeDefined();
    });
  });
});
