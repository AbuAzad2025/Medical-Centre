import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/login.js');
});

describe('login.js', () => {
  describe('caps (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.caps).toBeDefined();
    });
  });
  describe('loginForm (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.loginForm).toBeDefined();
    });
  });
  describe('pwd (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.pwd).toBeDefined();
    });
  });
  describe('toggle (window)', () => {
    it('is exposed on window', () => {
      expect(typeof window.toggle).toBeDefined();
    });
  });
});
