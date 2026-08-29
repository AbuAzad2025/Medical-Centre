import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  loadScript('static/js/security.js');
});

describe('security.js', () => {
  describe('InputValidator', () => {
    it('validateEmail accepts valid email', () => {
      const { InputValidator } = require('../../static/js/security.js');
      const v = new InputValidator();
      expect(v.validateEmail('test@example.com')).toBe(true);
    });
    it('validateEmail rejects invalid email', () => {
      const { InputValidator } = require('../../static/js/security.js');
      const v = new InputValidator();
      expect(v.validateEmail('notanemail')).toBe(false);
    });
    it('validatePhone accepts valid phone', () => {
      const { InputValidator } = require('../../static/js/security.js');
      const v = new InputValidator();
      expect(v.validatePhone('+971501234567')).toBe(true);
    });
    it('validatePhone rejects invalid phone', () => {
      const { InputValidator } = require('../../static/js/security.js');
      const v = new InputValidator();
      expect(v.validatePhone('abc')).toBe(false);
    });
    it('sanitizeString escapes HTML', () => {
      const { InputValidator } = require('../../static/js/security.js');
      const v = new InputValidator();
      expect(v.sanitizeString('<b>test</b>')).toBe('&lt;b&gt;test&lt;/b&gt;');
    });
  });

  describe('SecurityManager', () => {
    it('checkPasswordStrength returns score 5 for strong password', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('Strong@Pass1');
      expect(r.score).toBe(5);
    });
    it('checkPasswordStrength returns score 0 for empty password', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('');
      expect(r.score).toBe(0);
    });
    it('checkPasswordStrength provides feedback for weak password', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('abc');
      expect(r.feedback.length).toBeGreaterThan(0);
    });
    it('sanitizeInput removes script tags', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = '<script>alert("xss")</script>';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('<script>');
    });
    it('sanitizeInput removes javascript: protocol', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = 'javascript:alert(1)';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('javascript:');
    });
    it('sanitizeInput removes onerror handler', () => {
      const { SecurityManager } = require('../../static/js/security.js');
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = 'x onerror=alert(1)';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('onerror=');
    });
  });
});
