import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/system_maintenance.js');
});

describe('system_maintenance.js', () => {
  describe('clearLogs (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.clearLogs).toBeDefined();
    });
  });
  describe('forceLogoutAll (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.forceLogoutAll).toBeDefined();
    });
  });
  describe('loadSystemStatus (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loadSystemStatus).toBeDefined();
    });
  });
  describe('optimizeDatabase (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.optimizeDatabase).toBeDefined();
    });
  });
  describe('refreshLogs (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.refreshLogs).toBeDefined();
    });
  });
});
