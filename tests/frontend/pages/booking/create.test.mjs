import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/booking/create.js');
});

describe('create.js', () => {
  describe('__M (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.__M).toBeDefined();
    });
  });
  describe('loadDoctors (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loadDoctors).toBeDefined();
    });
  });
  describe('loadSmartSlots (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loadSmartSlots).toBeDefined();
    });
  });
  describe('loadTimes (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loadTimes).toBeDefined();
    });
  });
  describe('presetDoctorId (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.presetDoctorId).toBeDefined();
    });
  });
  describe('presetTime (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.presetTime).toBeDefined();
    });
  });
});
