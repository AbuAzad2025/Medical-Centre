import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/system_config.js');
});

describe('system_config.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
  describe('processNotificationQueue (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.processNotificationQueue).toBeDefined();
    });
  });
  describe('resetSettings (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.resetSettings).toBeDefined();
    });
  });
  describe('saveSettings (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.saveSettings).toBeDefined();
    });
  });
  describe('testConnection (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.testConnection).toBeDefined();
    });
  });
  describe('testSmsConnection (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.testSmsConnection).toBeDefined();
    });
  });
});
