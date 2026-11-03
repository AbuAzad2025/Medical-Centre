import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/super_admin/queue_settings.js');
});

describe('queue_settings.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('boolSelect (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.boolSelect).toBeDefined();
    });
  });
  describe('collectSettings (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.collectSettings).toBeDefined();
    });
  });
  describe('csrfToken (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.csrfToken).toBeDefined();
    });
  });
  describe('intInput (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.intInput).toBeDefined();
    });
  });
  describe('loadSettings (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loadSettings).toBeDefined();
    });
  });
  describe('saveBtn (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.saveBtn).toBeDefined();
    });
  });
  describe('tbody (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.tbody).toBeDefined();
    });
  });
});
